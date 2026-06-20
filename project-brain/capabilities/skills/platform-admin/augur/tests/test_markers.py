"""Auto-generated importability test for markers."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_markers_importable():
    """Verify that markers can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.platform-admin.scripts.ops.markers")
    assert mod is not None


def test_prune_resolved_markers_scans_shared_vault_skills(tmp_path):
    """Auto-loop marker pruning should include project-brain skill files."""
    import importlib

    mod = importlib.import_module("skills.platform-admin.scripts.ops.markers")
    target = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "scripts" / "tool.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "# TODO_CLEANUP(auto-dead-api): stale generated marker\nprint('keep')\n",
        encoding="utf-8",
    )

    pruned = mod._prune_stale_auto_markers(tmp_path)

    assert [p.replace("\\", "/") for p in pruned] == ["project-brain/capabilities/skills/demo/scripts/tool.py (1 marker(s))"]
    assert "TODO_CLEANUP" not in target.read_text(encoding="utf-8")
