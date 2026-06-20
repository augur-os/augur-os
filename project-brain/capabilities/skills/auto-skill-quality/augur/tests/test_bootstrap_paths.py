"""Auto-generated importability test for bootstrap_paths."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def test_bootstrap_paths_importable():
    """Verify that bootstrap_paths can be imported without errors."""
    spec = importlib.util.spec_from_file_location("auto_skill_quality_bootstrap_paths", SCRIPTS_DIR / "bootstrap_paths.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod is not None
