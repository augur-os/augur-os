"""Tests for ADR-443 fix classification — git-aware auto-loop safety.

Covers classify_fix(), _check_git_deletion_history(),
_check_git_recent_modification(), and make_migration_incomplete_issue()
from src.lib.ops_protocol.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import (
    DeletionInfo,
    FixClassification,
    classify_fix,
    make_migration_incomplete_issue,
)


def _make_git_log_output(days_ago: int, commit_msg: str, commit_hash: str = "abc1234") -> str:
    """Build a fake `git log --format=%H %aI %s` output line."""
    deleted_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    iso = deleted_at.isoformat()
    return f"{commit_hash} {iso} {commit_msg}"


def _make_subprocess_router(**routes):
    """Create a side_effect that returns different results based on diff-filter.

    routes: mapping of diff_filter string to (returncode, stdout).
    Use "AMRC" for modification checks, "D" for deletion checks, "" for no filter.
    """
    empty = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def router(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        for flag, (rc, stdout) in routes.items():
            if f"--diff-filter={flag}" in cmd:
                return subprocess.CompletedProcess(args=cmd, returncode=rc, stdout=stdout, stderr="")
        return empty

    return router


class TestClassifyFixRevertingRecentDeletionWithADR:
    """Recent deletion (<= 7 days) with ADR reference -> REVERTING."""

    def test_recent_deletion_with_adr_ref(self):
        deletion_output = _make_git_log_output(
            days_ago=3,
            commit_msg="chore(ADR-400): remove legacy config file",
            commit_hash="deadbeef1234",
        )
        router = _make_subprocess_router(
            AMRC=(0, ""),  # No modification history (file was deleted)
            D=(0, deletion_output + "\n"),  # Deletion found
        )
        with patch("src.lib.ops_protocol.subprocess.run", side_effect=router):
            classification, deletion_info = classify_fix(
                "structural",
                "config/old_config.yaml",
            )

        assert classification is FixClassification.REVERTING
        assert deletion_info is not None
        assert deletion_info.adr_reference == "ADR-400"
        assert deletion_info.commit_hash == "deadbeef1234"
        assert "ADR-400" in deletion_info.commit_message


class TestClassifyFixStructuralOldDeletion:
    """Old deletion (> 7 days) -> STRUCTURAL regardless of ADR ref."""

    def test_old_deletion_is_structural(self):
        deletion_output = _make_git_log_output(
            days_ago=14,
            commit_msg="cleanup: remove deprecated module",
            commit_hash="oldcommit999",
        )
        router = _make_subprocess_router(
            AMRC=(0, ""),  # No modification (deleted file)
            D=(0, deletion_output + "\n"),
        )
        with patch("src.lib.ops_protocol.subprocess.run", side_effect=router):
            classification, deletion_info = classify_fix(
                "structural",
                "src/deprecated_module.py",
            )

        assert classification is FixClassification.STRUCTURAL
        assert deletion_info is not None
        assert deletion_info.commit_hash == "oldcommit999"


class TestClassifyFixSafeNewFile:
    """File never existed in git history -> STRUCTURAL with no deletion info."""

    def test_new_file_never_existed(self):
        router = _make_subprocess_router(
            AMRC=(0, ""),
            D=(0, ""),
        )
        with patch("src.lib.ops_protocol.subprocess.run", side_effect=router):
            classification, deletion_info = classify_fix(
                "structural",
                "src/brand_new_file.py",
            )

        assert classification is FixClassification.STRUCTURAL
        assert deletion_info is None


class TestClassifyFixExistingPathWithDeletionHistory:
    """Existing paths should not be treated as re-creations."""

    def test_existing_directory_ignores_child_deletion_history(self, tmp_path: Path):
        skill_dir = tmp_path / "skills" / "rag"
        skill_dir.mkdir(parents=True)

        deletion_output = _make_git_log_output(
            days_ago=0,
            commit_msg="Implement ADR-539 RAG simplification",
            commit_hash="deadbeef539",
        )
        router = _make_subprocess_router(
            AMRC=(0, ""),
            D=(0, deletion_output + "\n"),
        )
        with patch("src.lib.ops_protocol.subprocess.run", side_effect=router):
            classification, deletion_info = classify_fix(
                "structural",
                "skills/rag",
                project_root=tmp_path,
            )

        assert classification is FixClassification.STRUCTURAL
        assert deletion_info is None


class TestClassifyFixModifiedByUser:
    """File recently modified by user commit -> MODIFIED."""

    def test_user_modification_blocks_fix(self):
        mod_output = _make_git_log_output(
            days_ago=2,
            commit_msg="refactor: rewrite config loader",
            commit_hash="usercommit1",
        )
        router = _make_subprocess_router(
            AMRC=(0, mod_output + "\n"),  # Recent user modification
            D=(0, ""),  # No deletion
        )
        with patch("src.lib.ops_protocol.subprocess.run", side_effect=router):
            classification, mod_info = classify_fix(
                "structural",
                "src/config/loader.py",
            )

        assert classification is FixClassification.MODIFIED
        assert mod_info is not None
        assert mod_info.is_user_change is True
        assert mod_info.commit_hash == "usercommit1"

    def test_autoloop_modification_allows_fix(self):
        mod_output = _make_git_log_output(
            days_ago=1,
            commit_msg="chore(auto): repo-sync auto-commit",
            commit_hash="autocommit1",
        )
        router = _make_subprocess_router(
            AMRC=(0, mod_output + "\n"),  # Recent autoloop modification
            D=(0, ""),  # No deletion
        )
        with patch("src.lib.ops_protocol.subprocess.run", side_effect=router):
            classification, _ = classify_fix(
                "structural",
                "config/generated.yaml",
            )

        assert classification is FixClassification.STRUCTURAL

    def test_old_user_modification_allows_fix(self):
        mod_output = _make_git_log_output(
            days_ago=10,  # Outside 7-day window
            commit_msg="feat: add new module",
            commit_hash="olduser1",
        )
        router = _make_subprocess_router(
            AMRC=(0, mod_output + "\n"),
            D=(0, ""),
        )
        with patch("src.lib.ops_protocol.subprocess.run", side_effect=router):
            classification, _ = classify_fix(
                "structural",
                "src/new_module.py",
            )

        assert classification is FixClassification.STRUCTURAL


class TestMakeMigrationIncompleteIssue:
    """make_migration_incomplete_issue returns correct issue structure."""

    def test_issue_has_adr_and_consumer(self):
        deletion = DeletionInfo(
            deleted_date=datetime.now(timezone.utc) - timedelta(days=2),
            commit_hash="abc123def",
            commit_message="feat(ADR-430): migrate to new schema",
            adr_reference="ADR-430",
        )
        issue = make_migration_incomplete_issue(
            deletion,
            target_path="plugins/career/skills/old-skill/augur.yaml",
            consumer="auto-lint scanner",
            category="fix-classification",
        )

        assert issue["kind"] == "manual"
        assert issue["adr"] == "ADR-430"
        assert "auto-lint scanner" in issue["detail"]
        assert issue["path"] == "plugins/career/skills/old-skill/augur.yaml"
        assert issue["deleted_commit"] == "abc123def"
        assert issue["root_cause_type"] == "manual_debt"
        assert issue["fixability"] == "manual"
