"""Importability test for src/scripts/export-skill.py.

The source file uses a hyphen in its filename (CLI-style), so this test
loads it via ``importlib`` rather than the package import path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_SKILL_PATH = PROJECT_ROOT / "src" / "scripts" / "export-skill.py"


def test_export_skill_importable() -> None:
    """Verify that src/scripts/export-skill.py is loadable as a module."""
    assert EXPORT_SKILL_PATH.is_file(), EXPORT_SKILL_PATH
    spec = importlib.util.spec_from_file_location("export_skill", EXPORT_SKILL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module is not None
