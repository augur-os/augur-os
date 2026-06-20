"""Auto-generated importability test for product."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_product_importable():
    """Verify that product can be imported without errors."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.fixers.product")
    assert mod is not None


def test_scaffold_action_uses_browse_skills_category():
    """Auto-scaffolded skill actions must target a real Browse category."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.fixers.product")

    action_yaml = mod._scaffold_action("routine-vault", {"hub": "adaptive"})

    assert "\n  skills:\n" in action_yaml
    assert "\n  routine-vault:\n" not in action_yaml
