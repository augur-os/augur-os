"""Tests for auto-dir-alignment scan/fix module."""

import importlib.util
from pathlib import Path

import pytest
from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dir_alignment_ops.py"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("dir_alignment_ops", _MODULE_PATH)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name(mod):
    assert mod.name == "auto-dir-alignment"


def test_scan_reports_violations(mod, tmp_path, monkeypatch):
    """d=0 scan finds dirs that don't match skills."""
    from src.lib import dir_alignment

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "career").mkdir()
    (skills / "finance").mkdir()
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills])
    dir_alignment.get_skill_names.cache_clear()

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "career").mkdir()
    (vault / "bad-name").mkdir()
    (vault / ".augur-reserved").write_text("")

    monkeypatch.setattr(mod, "_get_locations", lambda: [dir_alignment.ManagedLocation(path=vault)])

    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["dir_name"] == "bad-name"
    assert result.issues[0]["kind"] == "maintenance"


def test_scan_d2_marks_unknown_dirs_manual(mod, tmp_path, monkeypatch):
    """d=2 is the reserve/scaffold tier, so non-rename dirs require judgment."""
    from src.lib import dir_alignment

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "career").mkdir()
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills])
    dir_alignment.get_skill_names.cache_clear()

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "prompts").mkdir()
    (vault / ".augur-reserved").write_text("")

    monkeypatch.setattr(mod, "_get_locations", lambda: [dir_alignment.ManagedLocation(path=vault)])

    result = mod.scan(_ctx(tmp_path, difficulty=2))

    assert result.issues[0]["kind"] == "manual"


def test_scan_d0_marks_trivial_rename_maintenance(mod, tmp_path, monkeypatch):
    """d=0 reports trivial renames without making them actionable."""
    from src.lib import dir_alignment

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "career").mkdir()
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills])
    dir_alignment.get_skill_names.cache_clear()

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "carer").mkdir()
    (vault / ".augur-reserved").write_text("")

    monkeypatch.setattr(mod, "_get_locations", lambda: [dir_alignment.ManagedLocation(path=vault)])
    monkeypatch.setattr(mod, "find_closest_skill", lambda _: ("career", 0.92))

    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert result.issues[0]["kind"] == "maintenance"


def test_scan_d1_marks_trivial_rename_actionable(mod, tmp_path, monkeypatch):
    """d=1 can fix trivial renames, so those findings become actionable."""
    from src.lib import dir_alignment

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "career").mkdir()
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills])
    dir_alignment.get_skill_names.cache_clear()

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "carer").mkdir()
    (vault / ".augur-reserved").write_text("")

    monkeypatch.setattr(mod, "_get_locations", lambda: [dir_alignment.ManagedLocation(path=vault)])
    monkeypatch.setattr(mod, "find_closest_skill", lambda _: ("career", 0.92))

    result = mod.scan(_ctx(tmp_path, difficulty=1))
    assert result.issues[0]["kind"] == "actionable"


def test_prefix_matches_require_skill_name_boundary(tmp_path, monkeypatch):
    """Short or lexical prefixes must not become destructive rename candidates."""
    from src.lib import dir_alignment

    skills = tmp_path / "skills"
    skills.mkdir()
    for name in ("brainstorming", "dev-build", "consulting-template"):
        (skills / name).mkdir()
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills])
    dir_alignment.get_skill_names.cache_clear()

    assert dir_alignment.find_closest_skill("brain") is None
    assert dir_alignment.find_closest_skill("dev") is None
    assert dir_alignment.find_closest_skill("consulting") == ("consulting-template", 1.0)


def test_scan_no_violations(mod, tmp_path, monkeypatch):
    """d=0 scan with all valid dirs returns clean."""
    from src.lib import dir_alignment

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "career").mkdir()
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills])
    dir_alignment.get_skill_names.cache_clear()

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "career").mkdir()
    (vault / ".augur-reserved").write_text("")

    monkeypatch.setattr(mod, "_get_locations", lambda: [dir_alignment.ManagedLocation(path=vault)])

    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert result.issues == []
    assert result.health == "verified"


def test_fix_dry_run(mod, tmp_path):
    """Fix in dry_run mode does not rename anything."""
    issues = [{"category": "dir-alignment", "detail": "bad -> good", "kind": "actionable", "classification": "trivial-rename", "dir_name": "bad", "closest_skill": "good", "location": str(tmp_path), "path": str(tmp_path / "bad")}]
    result = mod.fix(_ctx(tmp_path, difficulty=1, dry_run=True), issues)
    assert isinstance(result, FixResult)
    assert result.success
    assert "Dry run" in result.summary
