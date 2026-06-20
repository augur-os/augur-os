"""Tests for auto-vault-hygiene scan/fix protocol."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "vault_hygiene_ops.py"
_SPEC = importlib.util.spec_from_file_location("vault_hygiene_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-vault-hygiene"


def test_scan_no_vault(tmp_path: Path) -> None:
    """scan returns clean when vault doesn't exist."""
    with patch.object(mod, "_get_vault", return_value=tmp_path / "nonexistent"):
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert result.health == "verified"


def test_get_vault_uses_project_yaml_path(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    vault = tmp_path / "configured-vault"
    project.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )

    assert mod._get_vault(project) == vault


def test_scan_missing_configured_vault_summary_includes_path(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    vault = tmp_path / "configured-vault"
    project.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )

    result = mod.scan(_ctx(project, difficulty=1))

    assert result.issues == [
        {
            "file": str(vault),
            "message": f"configured vault path does not exist: {vault}",
            "severity": "info",
            "kind": "environment",
        }
    ]
    assert str(vault) in result.summary


def test_scan_missing_configured_vault_d0_summary_only(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    vault = tmp_path / "configured-vault"
    project.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )

    result = mod.scan(_ctx(project, difficulty=0))

    assert result.issues == []
    assert result.severity == "info"
    assert str(vault) in result.summary


def test_scan_d1_cross_reference_uses_configured_vault_only(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "repo"
    configured_vault = tmp_path / "configured-vault"
    discovered_vault = tmp_path / "discovered-vault"
    skill_dir = project / "skills" / "brain"
    skill_dir.mkdir(parents=True)
    configured_vault.mkdir()
    discovered_vault.mkdir()
    (project / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {configured_vault}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUGUR_VAULT", str(discovered_vault))

    def _poison_get_skill_vault_dir(_skill_name: str) -> Path:
        raise AssertionError("scan should not use discovery-backed get_skill_vault_dir")

    with (
        patch("src.config.paths.get_project_root", return_value=project),
        patch("src.config.paths.get_skills_dir", return_value=project / "skills"),
        patch("src.config.paths.get_all_client_skill_dirs", return_value=[]),
        patch("src.config.paths.get_skill_vault_dir", side_effect=_poison_get_skill_vault_dir),
        patch.object(mod, "check_git_health", return_value=[]),
    ):
        result = mod.scan(_ctx(project, difficulty=1))

    assert all("discovered-vault" not in issue.get("message", "") for issue in result.issues)


def test_scan_d0_hardening_reports(tmp_path: Path) -> None:
    """d0 detects hardening-reports in vault."""
    vault = tmp_path / "vault"
    _write(vault / "core" / "hardening-reports" / "report.json", "{}")

    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path, difficulty=0))
    hardening = [i for i in result.issues if "hardening-reports" in i.get("message", "")]
    assert len(hardening) == 1


def test_scan_d1_config_yaml_issue(tmp_path: Path) -> None:
    """d1 detects config.yaml alongside .md files."""
    vault = tmp_path / "vault"
    _write(vault / "core" / "browse" / "config.yaml", "key: value\n")
    _write(vault / "core" / "browse" / "notes.md", "# Notes\n")

    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path, difficulty=1))
    config_issues = [i for i in result.issues if "config.yaml" in i.get("message", "")]
    assert len(config_issues) == 1


def test_scan_respects_reserved_roots_and_ignores_git_metadata(tmp_path: Path) -> None:
    """Valid structural roots and git internals are not vault cleanup findings."""
    vault = tmp_path / "vault"
    (vault / ".git" / "objects" / "pack").mkdir(parents=True)
    (vault / ".git" / "objects" / "pack" / "pack-large.pack").write_text(
        "x" * 1_000_001,
        encoding="utf-8",
    )
    (vault / ".augur-reserved").write_text("custom\nwiki\n", encoding="utf-8")
    (vault / "custom").mkdir()
    _write(vault / "custom" / "note.md", "# Custom\n")
    (vault / "wiki").mkdir()
    _write(vault / "wiki" / "overview.md", "# Wiki\n")
    (vault / "_drafts").mkdir()
    _write(vault / "_drafts" / "README.md", "# Drafts\n")
    (vault / "skills").mkdir()
    _write(vault / "skills" / "README.md", "# Skills\n")

    with (
        patch.object(mod, "_get_vault", return_value=vault),
        patch.object(mod, "check_git_health", return_value=[]),
    ):
        result = mod.scan(_ctx(tmp_path, difficulty=1))

    issue_text = "\n".join(f"{i.get('file')}: {i.get('message')}" for i in result.issues)
    assert "custom" not in issue_text
    assert "wiki:" not in issue_text
    assert "_drafts" in issue_text
    # Post-ADR-771 a bare skills/ root is retired (content lives in
    # capabilities/skills) — it must now be flagged.
    assert "skills: orphan vault dir" in issue_text
    assert "pack-large.pack" not in issue_text


def test_obsidian_first_root_allowlist_accepts_drafts_archive_config(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    for root in ("drafts", "archive", "config", "memory", "notes", "sources", "wiki", "skills", "inbox"):
        (vault / root).mkdir(parents=True)
    (vault / ".git").mkdir()
    monkeypatch.setattr(mod, "_get_vault", lambda project_root=None: vault)
    monkeypatch.setattr(mod, "check_git_health", lambda vault: [])

    result = mod.scan(_ctx(tmp_path, difficulty=1))

    assert all(issue["file"] != "_drafts" for issue in result.issues)
    assert all(issue["file"] != "drafts" for issue in result.issues)
    assert all(issue["file"] != "archive" for issue in result.issues)
    assert all(issue["file"] != "config" for issue in result.issues)
    # Post-ADR-771 the flat memory/ root is retired (knowledge/memory) and
    # must be flagged like the other legacy names.
    assert any(issue["file"] == "memory" for issue in result.issues)


def test_vault_hygiene_flags_mapped_skill_roots_at_top_level(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo"
    skills = project / "skills"
    vault = tmp_path / "vault"
    (skills / "apple").mkdir(parents=True)
    (vault / "apple").mkdir(parents=True)
    _write(vault / "apple" / "README.md", "# Apple\n")
    (vault / ".git").mkdir()

    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills])
    monkeypatch.setattr("src.config.paths.get_skills_dir", lambda: skills)
    monkeypatch.setattr("src.config.paths.get_all_client_skill_dirs", lambda: [skills])
    monkeypatch.setattr(mod, "_get_vault", lambda project_root=None: vault)
    monkeypatch.setattr(mod, "check_git_health", lambda vault: [])

    result = mod.scan(_ctx(project, difficulty=1))

    assert "apple" in {issue["file"] for issue in result.issues}


def test_vault_hygiene_flags_legacy_underscore_roots(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    for root in ("_drafts", "_system"):
        (vault / root).mkdir(parents=True)
        _write(vault / root / "README.md", f"# {root}\n")
    (vault / ".git").mkdir()
    monkeypatch.setattr(mod, "_get_vault", lambda project_root=None: vault)
    monkeypatch.setattr(mod, "check_git_health", lambda vault: [])

    result = mod.scan(_ctx(tmp_path, difficulty=1))

    issue_files = {issue["file"] for issue in result.issues}
    assert "_drafts" in issue_files
    assert "_system" in issue_files


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"kind": "actionable", "message": "test"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_fix_d0_report_only(tmp_path: Path) -> None:
    """d0 produces report only — no fixes applied."""
    result = mod.fix(_ctx(tmp_path, difficulty=0), [{"kind": "maintenance", "message": "info only"}])
    assert result.success is True
    assert "No actionable" in result.summary
    assert result.fix_type == "report"


def test_fix_d0_does_not_mutate_actionable_or_structural_issues(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    empty_dir = vault / "skill" / "empty"
    misplaced = vault / "finance-notes.md"
    empty_dir.mkdir(parents=True)
    _write(misplaced, "# Finance\n")
    (tmp_path / "skills" / "finance").mkdir(parents=True)
    issues = [
        {"file": "skill/empty", "message": "empty directory", "kind": "maintenance"},
        {"file": "finance-notes.md", "message": "misplaced root file", "kind": "misplaced_file"},
        {"file": "core/hardening-reports", "message": "hardening-reports/ in vault", "kind": "actionable"},
    ]

    with (
        patch.object(mod, "_get_vault", return_value=vault),
        patch("src.config.paths.get_skills_dir", return_value=tmp_path / "skills"),
        patch.object(mod.subprocess, "run", side_effect=AssertionError("d0 must not run mutating commands")),
    ):
        result = mod.fix(_ctx(tmp_path, difficulty=0), issues)

    assert result.success is True
    assert result.fix_type == "report"
    assert any(action.get("action") == "report" for action in result.actions)
    assert empty_dir.exists()
    assert misplaced.exists()
    assert not (vault / "finance" / "finance-notes.md").exists()


def test_fix_d1_no_actionable(tmp_path: Path) -> None:
    """d1 with only maintenance issues applies no fixes."""
    vault = tmp_path / "vault"
    vault.mkdir()
    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.fix(_ctx(tmp_path, difficulty=1), [{"kind": "maintenance", "message": "info only"}])
    assert result.success is True
    assert "No actionable" in result.summary


# --- Misplaced root files tests ---


def test_scan_d0_misplaced_root_file(tmp_path: Path) -> None:
    """d0 detects files sitting directly in vault root."""
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(vault / "stray-notes.md", "# Stray\n")

    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path, difficulty=0))
    misplaced = [i for i in result.issues if i.get("kind") == "misplaced_file"]
    assert len(misplaced) == 1
    assert "stray-notes.md" in misplaced[0]["message"]


def test_fix_moves_misplaced_root_file(tmp_path: Path) -> None:
    """fix() moves a misplaced root file to a matching skill dir."""
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(vault / "finance-notes.md", "# Finance\n")
    # Create a skills dir with a matching skill
    skills_dir = tmp_path / "skills" / "finance"
    skills_dir.mkdir(parents=True)

    issues = [{"file": "finance-notes.md", "kind": "misplaced_file", "message": "misplaced root file"}]
    with patch.object(mod, "_get_vault", return_value=vault), \
         patch("src.config.paths.get_skills_dir", return_value=tmp_path / "skills"):
        result = mod.fix(_ctx(tmp_path, difficulty=1), issues)
    assert result.success is True
    assert (vault / "finance" / "finance-notes.md").exists()
    assert not (vault / "finance-notes.md").exists()
    assert any("move_misplaced" in str(a) for a in result.actions)


# --- Empty directory removal tests ---


def test_fix_removes_empty_dirs(tmp_path: Path) -> None:
    """fix() removes empty directories."""
    vault = tmp_path / "vault"
    empty_dir = vault / "some-skill" / "empty-sub"
    empty_dir.mkdir(parents=True)

    issues = [{"file": "some-skill/empty-sub", "message": "empty directory", "kind": "maintenance"}]
    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.fix(_ctx(tmp_path, difficulty=1), issues)
    assert result.success is True
    assert not empty_dir.exists()
    assert any("remove_empty_dir" in str(a) for a in result.actions)


# --- Permission fix tests ---


@pytest.mark.skipif(os.name == "nt", reason="Windows chmod does not expose POSIX executable bits")
def test_scan_d1_executable_data_file(tmp_path: Path) -> None:
    """d1 detects executable permission on data files."""
    vault = tmp_path / "vault"
    data_file = vault / "skill" / "notes.md"
    _write(data_file, "# Notes\n")
    data_file.chmod(0o755)

    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path, difficulty=1))
    perm_issues = [i for i in result.issues if i.get("kind") == "permission_fix"]
    assert len(perm_issues) >= 1
    assert "executable" in perm_issues[0]["message"]


@pytest.mark.skipif(os.name == "nt", reason="Windows chmod does not expose POSIX executable bits")
def test_fix_corrects_file_permissions(tmp_path: Path) -> None:
    """fix() removes executable bits from data files."""
    import stat as stat_mod
    vault = tmp_path / "vault"
    data_file = vault / "skill" / "notes.md"
    _write(data_file, "# Notes\n")
    data_file.chmod(0o755)

    issues = [{"file": "skill/notes.md", "kind": "permission_fix", "message": "executable permission"}]
    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.fix(_ctx(tmp_path, difficulty=1), issues)
    assert result.success is True
    actual_perms = stat_mod.S_IMODE(data_file.stat().st_mode)
    assert actual_perms == 0o644


# --- ADR-474 git health check tests ---


def test_check_git_health_no_git(tmp_path: Path) -> None:
    """check_git_health detects missing .git directory."""
    vault = tmp_path / "vault"
    vault.mkdir()

    issues = mod.check_git_health(vault)
    assert len(issues) == 1
    assert "not a git repo" in issues[0]["message"]
    assert issues[0]["severity"] == "warning"


def test_check_git_health_missing_gitignore(tmp_path: Path) -> None:
    """check_git_health detects missing .gitignore."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".git").mkdir()

    with patch.object(mod, "_run_git", return_value=(True, "")):
        issues = mod.check_git_health(vault)

    gitignore_issues = [i for i in issues if ".gitignore" in i.get("file", "")]
    assert len(gitignore_issues) == 1
    assert "no .gitignore" in gitignore_issues[0]["message"]


def test_check_git_health_incomplete_gitignore(tmp_path: Path) -> None:
    """check_git_health detects incomplete .gitignore patterns."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".git").mkdir()
    (vault / ".gitignore").write_text(".DS_Store\n__pycache__/\n")

    with patch.object(mod, "_run_git", return_value=(True, "")):
        issues = mod.check_git_health(vault)

    gitignore_issues = [i for i in issues if ".gitignore" in i.get("file", "")]
    assert len(gitignore_issues) == 1
    assert "missing patterns" in gitignore_issues[0]["message"]


def test_check_git_health_complete_gitignore(tmp_path: Path) -> None:
    """check_git_health passes with complete .gitignore."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".git").mkdir()
    (vault / ".gitignore").write_text(".DS_Store\n__pycache__/\n*.pyc\n._*\n_cache/\n_config/\n")

    with patch.object(mod, "_run_git", return_value=(True, "")):
        issues = mod.check_git_health(vault)

    gitignore_issues = [i for i in issues if ".gitignore" in i.get("file", "")]
    assert len(gitignore_issues) == 0


def test_check_git_health_uncommitted(tmp_path: Path) -> None:
    """check_git_health detects uncommitted changes."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".git").mkdir()
    (vault / ".gitignore").write_text(".DS_Store\n__pycache__/\n*.pyc\n._*\n_cache/\n_config/\n")

    def mock_git(vault_path, *args):
        cmd = " ".join(args)
        if "status --porcelain" in cmd:
            return True, " M file1.md\n M file2.md"
        return True, ""

    with patch.object(mod, "_run_git", side_effect=mock_git):
        issues = mod.check_git_health(vault)

    uncommitted = [i for i in issues if "uncommitted" in i.get("message", "")]
    assert len(uncommitted) == 1
    assert "2 uncommitted" in uncommitted[0]["message"]


def test_fix_reports_vault_commit_failure(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".git").mkdir()
    issues = [{"file": "vault-wide", "message": "2 uncommitted changes in vault", "kind": "maintenance"}]

    def _fake_run(args, **_kwargs):
        if args[:2] == ["git", "add"]:
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if args[:2] == ["git", "commit"]:
            return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "nothing staged"})()
        raise AssertionError(f"unexpected command: {args}")

    with (
        patch.object(mod, "_get_vault", return_value=vault),
        patch.object(mod.subprocess, "run", side_effect=_fake_run),
    ):
        result = mod.fix(_ctx(tmp_path, difficulty=1), issues)

    assert result.success is False
    assert {"action": "vault_commit", "success": False} in result.actions
    assert "vault git commit failed" in result.summary


def test_fix_reports_config_migration_failure(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    migrate_script = tmp_path / "scripts" / "vault_hygiene" / "migrate_config.py"
    _write(migrate_script, "raise SystemExit(1)\n")
    issues = [{"file": "skill/config.yaml", "message": "config.yaml alongside .md files", "kind": "actionable"}]

    def _fake_run(args, **_kwargs):
        assert args[:2] == ["python3", str(migrate_script)]
        return type("Result", (), {"returncode": 1, "stdout": "failed stdout", "stderr": "failed stderr"})()

    with (
        patch.object(mod, "_get_vault", return_value=vault),
        patch.object(mod.subprocess, "run", side_effect=_fake_run),
    ):
        result = mod.fix(_ctx(tmp_path, difficulty=1), issues)

    assert result.success is False
    assert any(a.get("action") == "migrate_config" and a.get("success") is False for a in result.actions)
    assert "config migration failed" in result.summary


def test_fix_reports_git_gc_failure(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".git").mkdir(parents=True)
    issues = [{"file": ".git", "message": ".git dir is 120MB — running git gc recommended", "kind": "actionable"}]

    def _fake_run(args, **_kwargs):
        assert args == ["git", "gc", "--aggressive"]
        return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "gc failed"})()

    with (
        patch.object(mod, "_get_vault", return_value=vault),
        patch.object(mod.subprocess, "run", side_effect=_fake_run),
    ):
        result = mod.fix(_ctx(tmp_path, difficulty=1), issues)

    assert result.success is False
    assert {"action": "git_gc", "success": False} in result.actions
    assert "vault git gc failed" in result.summary


def test_check_git_health_unpushed(tmp_path: Path) -> None:
    """check_git_health detects unpushed commits."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".git").mkdir()
    (vault / ".gitignore").write_text(".DS_Store\n__pycache__/\n*.pyc\n._*\n_cache/\n_config/\n")

    def mock_git(vault_path, *args):
        cmd = " ".join(args)
        if "status --porcelain" in cmd:
            return True, ""
        if "@{u}..HEAD" in cmd:
            return True, "abc1234 commit1\ndef5678 commit2"
        return True, ""

    with patch.object(mod, "_run_git", side_effect=mock_git):
        issues = mod.check_git_health(vault)

    unpushed = [i for i in issues if "unpushed" in i.get("message", "")]
    assert len(unpushed) == 1
    assert "2 unpushed" in unpushed[0]["message"]


def test_fix_binary_eviction_preserves_existing_destination_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    src = vault / "skill" / "photo.png"
    _write(src, "binary from vault")
    documents_dir = tmp_path / "Documents" / "skill"
    existing_dest = documents_dir / "photo.png"
    _write(existing_dest, "existing document")
    issues = [{"file": "skill/photo.png", "message": "binary file in vault", "kind": "binary_eviction"}]

    def _fake_run(args, **_kwargs):
        if args[:2] == ["git", "add"]:
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if args[:2] == ["git", "commit"]:
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError(f"unexpected command: {args}")

    with (
        patch.object(mod, "_get_vault", return_value=vault),
        patch("src.config.paths.get_documents_dir", return_value=tmp_path / "Documents"),
        patch.object(mod.subprocess, "run", side_effect=_fake_run),
    ):
        result = mod.fix(_ctx(tmp_path, difficulty=2), issues)

    assert result.success is True
    assert existing_dest.read_text(encoding="utf-8") == "existing document"
    unique_dest = documents_dir / "photo-1.png"
    assert unique_dest.read_text(encoding="utf-8") == "binary from vault"
    assert not src.exists()


def test_fix_binary_eviction_handles_non_skill_top_dir(tmp_path: Path) -> None:
    """Binaries in legitimate vault content dirs that are NOT skills (meetings,
    notes, finance, voice-memos) must evict — mirrored under Documents — instead
    of erroring on skill-name validation. Regression for the eviction crash."""
    vault = tmp_path / "vault"
    src = vault / "meetings" / "rec.m4a"
    _write(src, "audio bytes")
    issues = [{"file": "meetings/rec.m4a", "message": "binary file in vault", "kind": "binary_eviction"}]

    def _ok(args, **_kwargs):
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with (
        patch.object(mod, "_get_vault", return_value=vault),
        patch("src.config.paths.get_documents_dir", return_value=tmp_path / "Documents"),
        patch.object(mod.subprocess, "run", side_effect=_ok),
    ):
        result = mod.fix(_ctx(tmp_path, difficulty=2), issues)

    assert result.success is True
    assert (tmp_path / "Documents" / "meetings" / "rec.m4a").read_text(encoding="utf-8") == "audio bytes"
    assert not src.exists()


def test_canonical_brain_root_files_not_misplaced(tmp_path: Path) -> None:
    """Canonical brain root files (BRAIN.yaml + standard brain files) live AT the
    vault root and must never be flagged as misplaced; a genuinely loose root
    file still is. Regression for the auto-vault-hygiene misplaced_file FP."""
    vault = tmp_path / "vault"
    vault.mkdir()
    for name in mod.CANONICAL_ROOT_FILES:
        _write(vault / name, "x\n")
    _write(vault / "stray-note.md", "loose\n")  # genuinely misplaced
    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path, difficulty=1))
    misplaced = {i["file"] for i in result.issues if i.get("kind") == "misplaced_file"}
    assert "stray-note.md" in misplaced
    assert misplaced.isdisjoint(mod.CANONICAL_ROOT_FILES)


# --- Brain skeleton + skill-asset awareness (ADR-771) ---


def test_scan_skill_owned_binary_not_flagged(tmp_path: Path) -> None:
    """Binary assets inside skill dirs (capabilities/skills, skills) are skill-owned."""
    vault = tmp_path / "vault"
    _write(vault / "capabilities" / "skills" / "resume-tailor" / "templates" / "reference.docx", "bin")
    _write(vault / "skills" / "legacy-skill" / "asset.png", "bin")
    _write(vault / "notes" / "photo.png", "bin")

    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path))

    binary_files = [i["file"] for i in result.issues if i.get("kind") == "binary_eviction"]
    assert "notes/photo.png" in binary_files
    assert not any("reference.docx" in f for f in binary_files)
    assert not any("asset.png" in f for f in binary_files)


def test_scan_brain_skeleton_dirs_not_flagged(tmp_path: Path) -> None:
    """In a brain root (BRAIN.yaml), skeleton dirs are neither orphan nor empty findings.

    Skeleton contract is the 8-entry _SKELETON_DIRS in src/lib/brain_manifest.py
    (ADR-811 fed-folder rule pruned plans/, specs/ and other unfed stubs, commit
    26c5e82d4); ex-skeleton dirs like plans/ are now legitimately flagged.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "BRAIN.yaml").write_text("schema_version: 1\n")
    skeleton_dirs = ("capabilities/skills", "knowledge/wiki", "decisions/adrs", "config")
    for rel in skeleton_dirs:
        (vault / rel).mkdir(parents=True)
    (vault / "plans").mkdir()  # pruned from the skeleton by ADR-811 — now a real finding
    (vault / "stray-empty").mkdir()

    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path))

    messages = [(i["file"], i["message"]) for i in result.issues]
    empty_flagged = [f for f, m in messages if m == "empty directory"]
    assert "stray-empty" in empty_flagged
    assert "plans" in empty_flagged  # ex-skeleton dirs are flagged again
    for skeleton in skeleton_dirs:
        assert skeleton not in empty_flagged, skeleton
    orphan_flagged = [f for f, m in messages if "orphan vault dir" in m]
    for top in ("capabilities", "knowledge", "decisions", "config"):
        assert top not in orphan_flagged, top


def test_scan_and_fix_cache_junk(tmp_path: Path) -> None:
    """OS/cache junk (gitignore-invisible) is flagged and removed at d1."""
    vault = tmp_path / "vault"
    _write(vault / "notes" / "real-note.md", "# keep\n")
    (vault / "notes" / ".DS_Store").write_text("junk")
    pycache = vault / "drafts" / "staging" / "r1" / "skills" / "x" / "__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "m.cpython-312.pyc").write_bytes(b"\x00")

    with patch.object(mod, "_get_vault", return_value=vault):
        result = mod.scan(_ctx(tmp_path))
    junk = [i for i in result.issues if i.get("kind") == "cache_junk"]
    assert {i["file"] for i in junk} == {
        "notes/.DS_Store",
        "drafts/staging/r1/skills/x/__pycache__/m.cpython-312.pyc",
    }

    with patch.object(mod, "_get_vault", return_value=vault):
        fix_result = mod.fix(_ctx(tmp_path, difficulty=1), junk)
    assert fix_result.success is True
    assert not (vault / "notes" / ".DS_Store").exists()
    assert not pycache.exists()
    assert (vault / "notes" / "real-note.md").exists()
