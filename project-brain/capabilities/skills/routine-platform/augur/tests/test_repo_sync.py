"""Tests for auto-repo-sync classification behavior."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import make_test_ctx


def _load_module():
    module_file = Path(__file__).resolve().parents[2] / "scripts" / "repo_sync.py"
    spec = importlib.util.spec_from_file_location("repo_sync", module_file)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["repo_sync"] = mod
    spec.loader.exec_module(mod)
    return mod


repo_sync = _load_module()


def test_scan_d0_reports_unpushed_without_creating_issue(tmp_path: Path):
    ctx = make_test_ctx(tmp_path, difficulty=0)
    with (
        patch.object(repo_sync, "_git_status", return_value=""),
        patch.object(repo_sync, "_git_unpushed", return_value="abc123 test commit"),
        patch.object(repo_sync, "_get_vault_path", return_value=None),
    ):
        result = repo_sync.scan(ctx)

    assert result.issues == []
    assert "unpushed commit" in result.summary


def test_scan_d1_marks_unpushed_commits_manual(tmp_path: Path):
    ctx = make_test_ctx(tmp_path, difficulty=1)
    with (
        patch.object(repo_sync, "_git_status", return_value=""),
        patch.object(repo_sync, "_git_unpushed", return_value="abc123 test commit"),
        patch.object(repo_sync, "_get_vault_path", return_value=None),
    ):
        result = repo_sync.scan(ctx)

    assert len(result.issues) == 1
    assert result.issues[0]["type"] == "unpushed_commits"
    assert result.issues[0]["kind"] == "manual"


def test_fix_skips_project_push_without_upstream(tmp_path: Path):
    ctx = make_test_ctx(tmp_path, difficulty=2)
    issues = [
        {
            "type": "uncommitted_changes",
            "count": 1,
            "detail": " M skills/rag/evals/rank.json",
            "kind": "actionable",
        }
    ]

    with (
        patch.object(repo_sync, "_git_commit", return_value="committed"),
        patch.object(repo_sync, "_get_vault_path", return_value=None),
        patch.object(repo_sync, "_git_has_upstream", return_value=False),
        patch.object(repo_sync, "_git_push", side_effect=AssertionError("push should be skipped")),
    ):
        result = repo_sync.fix(ctx, issues)

    assert result.success is True
    assert result.changes == ["Committed staged changes"]
    assert {"action": "push", "success": True, "skipped": True, "reason": "no_upstream"} in result.actions


def test_fix_does_not_push_project_when_only_vault_issue_exists(tmp_path: Path):
    ctx = make_test_ctx(tmp_path, difficulty=2)
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    issues = [
        {
            "type": "vault_unpushed",
            "count": 1,
            "detail": "abc123 vault commit",
            "repo": "vault",
            "kind": "manual",
        }
    ]
    push_calls: list[Path] = []

    def _fake_push(path: Path) -> bool:
        push_calls.append(path)
        return True

    with (
        patch.object(repo_sync, "_get_vault_path", return_value=vault_path),
        patch.object(repo_sync, "_git_has_upstream", return_value=True),
        patch.object(repo_sync, "_git_push", side_effect=_fake_push),
    ):
        result = repo_sync.fix(ctx, issues)

    assert result.success is True
    assert result.changes == ["Pushed vault to remote"]
    assert push_calls == [vault_path]


def test_get_vault_path_uses_project_yaml_and_ignores_env_discovery(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo"
    configured_vault = tmp_path / "configured-vault"
    env_vault = tmp_path / "env-vault"
    project.mkdir()
    configured_vault.mkdir()
    env_vault.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {configured_vault}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUGUR_VAULT", str(env_vault))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert repo_sync._get_vault_path(project) == configured_vault


def test_scan_reports_configured_missing_vault_without_private_discovery(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo"
    configured_vault = tmp_path / "configured-vault"
    env_vault = tmp_path / "env-vault"
    project.mkdir()
    env_vault.mkdir()
    (env_vault / ".git").mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {configured_vault}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUGUR_VAULT", str(env_vault))
    ctx = make_test_ctx(project, difficulty=1)

    with (
        patch.object(repo_sync, "_git_status", return_value=""),
        patch.object(repo_sync, "_git_unpushed", return_value=""),
    ):
        result = repo_sync.scan(ctx)

    assert str(configured_vault) in result.summary
    assert str(env_vault) not in result.summary
    assert result.issues == [
        {
            "type": "configured_vault_missing",
            "path": str(configured_vault),
            "repo": "vault",
            "kind": "maintenance",
            "detail": f"Configured vault path does not exist: {configured_vault}",
        }
    ]


def test_scan_d0_summarizes_missing_configured_vault_without_issue(tmp_path: Path):
    project = tmp_path / "repo"
    configured_vault = tmp_path / "configured-vault"
    project.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {configured_vault}\n",
        encoding="utf-8",
    )
    ctx = make_test_ctx(project, difficulty=0)

    with (
        patch.object(repo_sync, "_git_status", return_value=""),
        patch.object(repo_sync, "_git_unpushed", return_value=""),
    ):
        result = repo_sync.scan(ctx)

    assert result.issues == []
    assert result.severity == "info"
    assert str(configured_vault) in result.summary


def test_fix_uses_ctx_project_root_derived_vault_path(tmp_path: Path):
    project = tmp_path / "repo"
    vault_path = tmp_path / "configured-vault"
    project.mkdir()
    vault_path.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault_path}\n",
        encoding="utf-8",
    )
    ctx = make_test_ctx(project, difficulty=2)
    issues = [
        {
            "type": "vault_unpushed",
            "count": 1,
            "detail": "abc123 vault commit",
            "repo": "vault",
            "kind": "manual",
        }
    ]
    push_calls: list[Path] = []

    def _fake_push(path: Path) -> bool:
        push_calls.append(path)
        return True

    with (
        patch.object(repo_sync, "_git_has_upstream", return_value=True),
        patch.object(repo_sync, "_git_push", side_effect=_fake_push),
    ):
        result = repo_sync.fix(ctx, issues)

    assert result.success is True
    assert push_calls == [vault_path]


def test_fix_reports_vault_commit_failure(tmp_path: Path):
    project = tmp_path / "repo"
    vault_path = tmp_path / "configured-vault"
    project.mkdir()
    vault_path.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault_path}\n",
        encoding="utf-8",
    )
    ctx = make_test_ctx(project, difficulty=1)
    issues = [
        {
            "type": "vault_uncommitted",
            "count": 1,
            "detail": " M note.md",
            "repo": "vault",
            "kind": "actionable",
        }
    ]

    with patch.object(repo_sync, "_git_commit", return_value="error"):
        result = repo_sync.fix(ctx, issues)

    assert result.success is False
    assert {"action": "vault_commit", "success": False} in result.actions
    assert "vault git commit failed" in result.summary


def test_fix_summary_is_failure_focused_when_project_commit_succeeds_and_vault_commit_fails(tmp_path: Path):
    project = tmp_path / "repo"
    vault_path = tmp_path / "configured-vault"
    project.mkdir()
    vault_path.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault_path}\n",
        encoding="utf-8",
    )
    ctx = make_test_ctx(project, difficulty=1)
    issues = [
        {
            "type": "uncommitted_changes",
            "count": 1,
            "detail": " M skills/rag/evals/rank.json",
            "kind": "actionable",
        },
        {
            "type": "vault_uncommitted",
            "count": 1,
            "detail": " M note.md",
            "repo": "vault",
            "kind": "actionable",
        },
    ]

    def _fake_commit(path: Path, _message: str) -> str:
        return "committed" if path == project else "error"

    with patch.object(repo_sync, "_git_commit", side_effect=_fake_commit):
        result = repo_sync.fix(ctx, issues)

    assert result.success is False
    assert "Committed staged changes" in result.changes
    assert {"action": "vault_commit", "success": False} in result.actions
    assert result.summary.startswith("Fix failed:")
    assert "vault git commit failed" in result.summary
