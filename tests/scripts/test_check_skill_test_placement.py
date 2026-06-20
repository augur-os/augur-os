"""Tests for scripts/check_skill_test_placement.py — the staged-skill-leak guard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_guard():
    spec = importlib.util.spec_from_file_location(
        "_check_skill_test_placement",
        SCRIPTS_DIR / "check_skill_test_placement.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_check_skill_test_placement"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_repo(
    tmp_path: Path,
    vault_skills: list[str],
    private_skills: list[str],
    staged_skills: list[str] | None = None,
    allowlist: list[str] | None = None,
) -> Path:
    """Build a fake repo tree under tmp_path. Returns the repo root."""
    import json

    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
    for s in vault_skills:
        (repo / "project-brain" / "capabilities" / "skills" / s / "scripts").mkdir(parents=True)
        (repo / "project-brain" / "capabilities" / "skills" / s / "augur" / "tests").mkdir(parents=True)
    private = repo / "_fake_private_vault" / "capabilities" / "skills"
    private.mkdir(parents=True)
    for s in private_skills:
        (private / s).mkdir()
    (repo / "config" / "system").mkdir(parents=True)
    allow_yaml = "allowed_central_tests_with_skill_refs:\n"
    for entry in allowlist or []:
        allow_yaml += f"  - {entry}\n"
    (repo / "config" / "system" / "test_placement_allowlist.yaml").write_text(allow_yaml)
    # Fake release matrix so the guard can classify staged skills
    matrix = {
        "skills": [{"name": s, "release": "r1"} for s in (staged_skills or [])]
        + [{"name": s, "release": "mvp"} for s in vault_skills if s not in (staged_skills or [])]
        + [{"name": s, "release": "r1"} for s in private_skills],
    }
    (repo / "docs" / "generated").mkdir(parents=True)
    (repo / "docs" / "generated" / "skill-release-matrix.json").write_text(json.dumps(matrix))
    return repo


def test_clean_state_returns_zero(tmp_path: Path):
    guard = _load_guard()
    repo = _make_repo(tmp_path, vault_skills=["ingest"], private_skills=["file-manager"])
    # Add a clean repo-level test
    (repo / "tests" / "test_pure_repo_thing.py").write_text("def test_x(): assert True\n")
    result = guard.scan(repo)
    assert result.exit_code == 0
    assert result.violations == []


def test_filename_violation_detected(tmp_path: Path):
    guard = _load_guard()
    # file-manager is treated as staged (r1) — only staged skills trigger the
    # filename rule. MVP-skill filenames in central tests/ are too over-eager
    # to flag (e.g. "test_vault_status" — vault is both a skill and a concept).
    repo = _make_repo(tmp_path, vault_skills=[], private_skills=["file-manager"], staged_skills=["file-manager"])
    (repo / "tests" / "test_file_manager_thing.py").write_text("def test_x(): pass\n")
    result = guard.scan(repo)
    assert result.exit_code == 1
    assert len(result.violations) == 1
    assert "file-manager" in result.violations[0].reason or "file_manager" in result.violations[0].reason


def test_body_import_violation_detected(tmp_path: Path):
    guard = _load_guard()
    repo = _make_repo(tmp_path, vault_skills=["ingest"], private_skills=[])
    (repo / "tests" / "test_imports_skill.py").write_text(
        "from skills.ingest.scripts.wiki import foo\n\ndef test_x(): pass\n"
    )
    result = guard.scan(repo)
    assert result.exit_code == 1
    assert any("ingest" in v.reason for v in result.violations)


def test_body_path_violation_detected(tmp_path: Path):
    guard = _load_guard()
    repo = _make_repo(tmp_path, vault_skills=["ingest"], private_skills=[])
    (repo / "tests" / "test_references_skill_path.py").write_text(
        'X = "project-brain/capabilities/skills/ingest/scripts/wiki.py"\ndef test_x(): pass\n'
    )
    result = guard.scan(repo)
    assert result.exit_code == 1
    assert any("ingest" in v.reason for v in result.violations)


def test_allowlist_exempts_listed_file(tmp_path: Path):
    guard = _load_guard()
    repo = _make_repo(
        tmp_path,
        vault_skills=[],
        private_skills=["file-manager"],
        allowlist=["tests/architecture/test_no_vault_skill_refs.py"],
    )
    (repo / "tests" / "architecture").mkdir(parents=True)
    (repo / "tests" / "architecture" / "test_no_vault_skill_refs.py").write_text(
        'NAMES = ["file-manager"]\ndef test_x(): pass\n'
    )
    result = guard.scan(repo)
    assert result.exit_code == 0
    assert result.violations == []


def test_stale_allowlist_entry_reported(tmp_path: Path):
    guard = _load_guard()
    repo = _make_repo(
        tmp_path,
        vault_skills=[],
        private_skills=[],
        allowlist=["tests/does_not_exist.py"],
    )
    result = guard.scan(repo)
    # Stale entries should be reported as a violation so the allowlist stays clean.
    assert result.exit_code == 1
    assert any("stale allowlist" in v.reason.lower() or "does not exist" in v.reason.lower() for v in result.violations)
