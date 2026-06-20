"""Auto-generated importability test for git_safety."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_git_safety_importable():
    """Verify that git_safety can be imported without errors."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.fixers.git_safety")
    assert mod is not None
