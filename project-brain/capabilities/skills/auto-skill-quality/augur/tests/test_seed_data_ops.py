"""Tests for auto-seed-data scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed_data_ops.py"
_SPEC = importlib.util.spec_from_file_location("seed_data_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-seed-data"


def test_scan_d0_surface(tmp_path: Path) -> None:
    """d0 counts seedable skills without issues."""
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_scan_d1_treats_seed_files_as_healthy_fallback(tmp_path: Path) -> None:
    """d1 accepts packaged seed files because plugin fallback can serve them."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "browse"
    seed_dir = skill_dir / "augur" / "seed"
    seed_dir.mkdir(parents=True)
    _write(seed_dir / "tasks.yaml", "- title: Sample Task\n")
    _write(skill_dir / "SKILL.md", "# Browse\n")

    data_dir = tmp_path / "data" / "browse"
    data_dir.mkdir(parents=True)

    with patch.object(mod, "get_skill_data_dir", return_value=data_dir):
        result = mod.scan(_ctx(tmp_path, difficulty=1))
    needs = [i for i in result.issues if i["type"] == "needs_seeding"]
    assert needs == []


def test_scan_d1_flags_empty_seed_dir(tmp_path: Path) -> None:
    """d1 flags seed directories that have no actual seed files."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "browse"
    seed_dir = skill_dir / "augur" / "seed"
    seed_dir.mkdir(parents=True)
    _write(skill_dir / "SKILL.md", "# Browse\n")

    data_dir = tmp_path / "data" / "browse"
    data_dir.mkdir(parents=True)

    with patch.object(mod, "get_skill_data_dir", return_value=data_dir):
        result = mod.scan(_ctx(tmp_path, difficulty=1))
    needs = [i for i in result.issues if i["type"] == "needs_seeding"]
    assert len(needs) == 1


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(
        _ctx(tmp_path, dry_run=True),
        [{"type": "needs_seeding", "skill_dir": "project-brain/capabilities/skills/browse"}],
    )
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_fix_removes_empty_seed_scaffold_without_creating_legacy_data_dir(tmp_path: Path) -> None:
    """fix removes empty seed scaffolds so fallback status stays honest."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "browse"
    seeds_dir = skill_dir / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)
    _write(seeds_dir / "_seed.yaml", "skill: browse\nversion: 1\n")
    _write(seeds_dir / ".gitkeep", "")
    _write(skill_dir / "SKILL.md", "# Browse\n")

    issues = [{
        "type": "needs_seeding",
        "skill_dir": "project-brain/capabilities/skills/browse",
        "seed_dir": "project-brain/capabilities/skills/browse/assets/seeds",
    }]
    result = mod.fix(_ctx(tmp_path, difficulty=1), issues)
    assert result.success is True
    assert not seeds_dir.exists()
    assert not (skill_dir / "augur" / "data").exists()
    assert len(result.changes) == 4


def test_fix_creates_seed_scaffold_when_no_manifest(tmp_path: Path) -> None:
    """fix scaffolds assets/seeds/ when a skill has empty data but no seed templates."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "empty-skill"
    skill_dir.mkdir(parents=True)
    _write(skill_dir / "SKILL.md", "# Empty Skill\n")

    issues = [{
        "type": "needs_seed_templates",
        "skill_dir": "project-brain/capabilities/skills/empty-skill",
        "data_dir": "data/empty-skill",
    }]
    result = mod.fix(_ctx(tmp_path, difficulty=1), issues)
    assert result.success is True
    assert (skill_dir / "assets" / "seeds" / "_seed.yaml").exists()
    assert (skill_dir / "assets" / "seeds" / ".gitkeep").exists()
    assert len(result.changes) == 2


def test_fix_does_not_write_legacy_data_dir_or_touch_existing_data(tmp_path: Path) -> None:
    """fix does not create source data dirs and preserves existing files."""
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "browse"
    seeds_dir = skill_dir / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)
    _write(seeds_dir / "_seed.yaml", "skill: browse\nversion: 1\n")
    # Pre-existing data file with different content
    _write(skill_dir / "augur" / "data" / "tasks.yaml", "- title: User Data\n")

    issues = [{"type": "needs_seeding", "skill_dir": "project-brain/capabilities/skills/browse"}]
    result = mod.fix(_ctx(tmp_path, difficulty=1), issues)
    assert result.success is True
    assert not (skill_dir / "augur" / "data" / ".gitkeep").exists()
    # Original content preserved
    assert "User Data" in (skill_dir / "augur" / "data" / "tasks.yaml").read_text()
