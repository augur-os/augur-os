"""Tests for auto-life-hub-coverage."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "life_hub_coverage_ops.py"
_SPEC = importlib.util.spec_from_file_location("life_hub_coverage_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_detects_life_hub_stale_refs(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "channels" / "SKILL.md",
        "---\nname: channels\nx-augur-hub: life\n---\n"
        "Canonical store in `augur/data/notes/`.\n"
        "Legacy fetch path: `plugins/admin/skills/channels/scripts/fetch_patch.py`\n",
    )

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["path"] == "project-brain/capabilities/skills/channels/SKILL.md"


def test_fix_rewrites_life_hub_refs(tmp_path: Path) -> None:
    target = tmp_path / "project-brain" / "capabilities" / "skills" / "apple" / "SKILL.md"
    _write(
        target,
        "---\nname: apple\nx-augur-hub: life\n---\n"
        "Canonical store in `augur/data/notes/`.\n"
        "Per-skill note directories: `plugins/*/skills/*/augur/data/notes/`\n"
        "Legacy verify path: `plugins/admin/skills/channels/scripts/verify_patch.py`\n",
    )

    scan = mod.scan(OpsContext(project_root=tmp_path))
    fixed = mod.fix(OpsContext(project_root=tmp_path), scan.issues)

    assert isinstance(fixed, FixResult)
    assert fixed.success is True
    updated = target.read_text(encoding="utf-8")
    assert 'get_skill_data_dir("<skill>") / "notes/"' in updated
    assert "project-brain/capabilities/skills/channels/scripts/verify_patch.py" in updated
    assert "augur/data/notes/" not in updated
    assert "plugins/admin/skills/channels/scripts/verify_patch.py" not in updated


def test_scan_ignores_non_life_hub_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "save" / "SKILL.md",
        "---\nname: save\nx-augur-hub: command\n---\n"
        "Canonical store in `augur/data/notes/`.\n",
    )

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert result.issues == []
