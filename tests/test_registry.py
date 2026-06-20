"""Auto-generated importability test for registry."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_registry_importable():
    """Verify that registry can be imported without errors."""
    import src.plugins.registry

    assert src.plugins.registry is not None
