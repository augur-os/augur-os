"""Auto-generated importability test for engine_report."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_engine_report_importable():
    """Verify that engine_report can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_report")
    assert mod is not None
