"""Auto-generated importability test for structure_generator."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts" / "skill_generation"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_structure_generator_importable():
    """Verify that structure_generator can be imported without errors."""
    import importlib.util

    module_path = SCRIPTS_DIR / "structure_generator.py"
    spec = importlib.util.spec_from_file_location("structure_generator", module_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod is not None
