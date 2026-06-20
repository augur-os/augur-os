"""Auto-generated importability test for dev_clean."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_dev_clean_importable():
    """Verify that dev_clean can be imported without errors."""
    import importlib
    mod = importlib.import_module("dev_clean")
    assert mod is not None


def test_dev_clean_discovers_checkout_root():
    """dev-clean must operate on the checkout root, not project-brain."""
    import importlib
    mod = importlib.import_module("dev_clean")

    assert mod.REPO_ROOT == PROJECT_ROOT
    assert (mod.REPO_ROOT / "project.yaml").is_file()
    assert (mod.REPO_ROOT / "pyproject.toml").is_file()
    assert mod.REPO_ROOT.name != "project-brain"
