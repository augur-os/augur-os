"""Importability test for src/scripts/export-skill.py.

The filename uses a hyphen so it cannot be imported with the regular
`import src.scripts.export-skill` syntax (hyphens are invalid in Python
identifiers). This test loads it via importlib instead, the same pattern
peer tests use for hyphenated module paths.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_export_skill_importable():
    """Verify that src/scripts/export-skill.py loads without errors."""
    module_path = PROJECT_ROOT / "src" / "scripts" / "export-skill.py"
    assert module_path.exists(), f"export-skill.py missing at {module_path}"
    spec = importlib.util.spec_from_file_location("export_skill", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_skill"] = module
    spec.loader.exec_module(module)
    assert module is not None
