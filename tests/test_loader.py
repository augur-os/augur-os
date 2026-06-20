"""Auto-generated importability test for loader."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_loader_importable():
    """Verify that loader can be imported without errors."""
    import src.plugins.loader

    assert src.plugins.loader is not None
