"""Auto-generated importability test for todo_outdated."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_todo_outdated_importable():
    """Verify that todo_outdated can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.platform-admin.scripts.ops.todo_outdated")
    assert mod is not None
