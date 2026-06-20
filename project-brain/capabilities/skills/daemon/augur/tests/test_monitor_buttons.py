"""Auto-generated importability test for monitor_buttons."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_monitor_buttons_importable():
    """Verify that monitor_buttons can be imported without errors."""
    import importlib

    mod = importlib.import_module("skills.daemon.scripts.monitor_buttons")
    assert mod is not None


def test_project_root_from_shared_vault_skill_root(tmp_path):
    """Fallback path resolution handles project-brain skill roots."""
    from skills.daemon.scripts import monitor_buttons

    skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon"
    assert monitor_buttons._project_root_from_skill_root(skill_root) == tmp_path
