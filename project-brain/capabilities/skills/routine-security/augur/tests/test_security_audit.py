"""Tests for auto-security-audit scan/fix protocol."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

# Ensure scripts can be imported
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import security_audit as mod


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-security-audit"


def test_score_all_clean() -> None:
    assert mod._score([]) == 10.0


def test_score_with_critical() -> None:
    findings = [{"severity": "critical"}, {"severity": "high"}]
    score = mod._score(findings)
    assert score < 8.0


def test_state_blocked() -> None:
    assert mod._state(4.0, True) == "blocked"


def test_state_quarantined() -> None:
    assert mod._state(6.0, False) == "quarantined"


def test_state_approved() -> None:
    assert mod._state(8.0, False) == "approved"


def test_scan_no_skills(tmp_path: Path) -> None:
    """scan returns clean when no skills found."""
    with pytest.MonkeyPatch().context() as m:
        m.setattr(mod, "discover_all_skills", lambda: [])
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "No skills discovered" in result.summary


def test_scan_uses_discovered_skill_path(tmp_path: Path) -> None:
    """scan trusts SkillRecord.path instead of reconstructing by skill name."""
    skill_dir = tmp_path / ".codex" / "skills" / ".system" / "imagegen"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: imagegen\n---\n", encoding="utf-8")
    scanned_paths: list[Path] = []

    def _scan(path: Path, *args, **kwargs) -> list[dict]:
        scanned_paths.append(path)
        return []

    record = SimpleNamespace(
        name="imagegen",
        path=skill_dir,
        tier=2,
        canonical=False,
        source_root="external-client",
        ownership="external",
    )

    with pytest.MonkeyPatch().context() as m:
        m.setattr(mod, "discover_all_skills", lambda: [record])
        m.setattr(mod.s1_prompt_injection, "scan_skill", _scan)
        m.setattr(mod.s2_secret_scanning, "scan_skill", _scan)
        m.setattr(mod.s3_static_analysis, "scan_skill", _scan)
        m.setattr(mod.s4_integrity, "scan_skill", _scan)
        m.setattr(mod.s5_permissions, "scan_skill", _scan)
        m.setattr(mod.tank_integration, "scan_skill_with_tank", _scan)
        result = mod.scan(_ctx(tmp_path))

    assert result.items_scanned == 1
    assert result.issues == []
    assert scanned_paths
    assert set(scanned_paths) == {skill_dir}


def test_scan_info_findings_do_not_degrade_health(tmp_path: Path) -> None:
    """Informational inventory entries are not loop findings."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "clean"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: clean\n---\n", encoding="utf-8")
    record = SimpleNamespace(
        name="clean",
        path=skill_dir,
        tier=0,
        canonical=True,
        source_root="project-brain",
        ownership="augur",
    )
    info_finding = {
        "stage": "S4",
        "category_name": "tree-hash",
        "severity": "info",
        "message": "Tree SHA: abc123",
    }

    with pytest.MonkeyPatch().context() as m:
        m.setattr(mod, "discover_all_skills", lambda: [record])
        m.setattr(mod.s1_prompt_injection, "scan_skill", lambda path: [])
        m.setattr(mod.s2_secret_scanning, "scan_skill", lambda path: [])
        m.setattr(mod.s3_static_analysis, "scan_skill", lambda path: [])
        m.setattr(mod.s4_integrity, "scan_skill", lambda path, is_augur_managed: [info_finding])
        m.setattr(mod.s5_permissions, "scan_skill", lambda path, is_augur_managed: [])
        m.setattr(mod.tank_integration, "scan_skill_with_tank", lambda path: [])
        result = mod.scan(_ctx(tmp_path))

    assert result.issues == []
    assert result.health == "verified"
    assert result.severity == "info"
    assert "all clean" in result.summary


def test_fix_dry_run(tmp_path: Path) -> None:
    """Fix in dry_run mode makes no changes."""
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"skill_name": "test", "state": "blocked"}])
    assert isinstance(result, FixResult)
    assert result.success
    assert "Dry run" in result.summary


def test_fix_d0_report_only(tmp_path: Path) -> None:
    """d0 produces report only."""
    result = mod.fix(_ctx(tmp_path, difficulty=0), [{"skill_name": "test", "state": "blocked"}])
    assert result.success
    assert "No fixes" in result.summary
    assert result.fix_type == "report"


def test_fix_d2_does_not_move_canonical_scripts(tmp_path: Path) -> None:
    """d2 blocking canonical skills writes state but leaves source scripts intact."""
    skill_dir = tmp_path / "skills" / "canonical"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    script = scripts_dir / "run.py"
    script.write_text("print('run')\n", encoding="utf-8")

    issue = {
        "skill_name": "canonical",
        "state": "blocked",
        "score": 0.0,
        "tier": 0,
        "canonical": True,
        "path": str(skill_dir),
    }

    with pytest.MonkeyPatch().context() as m:
        m.setattr(mod, "get_own_data_dir", lambda _f: tmp_path / "security-data")
        result = mod.fix(_ctx(tmp_path, difficulty=2), [issue])

    assert result.success
    assert (skill_dir / ".augur-blocked").exists()
    assert script.exists()
    assert not (skill_dir / "_quarantine" / "run.py").exists()


def test_fix_d2_moves_external_scripts_to_quarantine(tmp_path: Path) -> None:
    """d2 still relocates blocked external skill scripts."""
    skill_dir = tmp_path / "external" / "risky"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    script = scripts_dir / "run.py"
    script.write_text("print('run')\n", encoding="utf-8")

    issue = {
        "skill_name": "risky",
        "state": "blocked",
        "score": 0.0,
        "tier": 2,
        "canonical": False,
        "path": str(skill_dir),
    }

    with pytest.MonkeyPatch().context() as m:
        m.setattr(mod, "get_own_data_dir", lambda _f: tmp_path / "security-data")
        result = mod.fix(_ctx(tmp_path, difficulty=2), [issue])

    assert result.success
    assert (skill_dir / ".augur-blocked").exists()
    assert not script.exists()
    assert (skill_dir / "_quarantine" / "run.py").exists()
