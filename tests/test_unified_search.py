"""Auto-generated importability test for unified_search."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_unified_search_importable():
    """Verify that unified_search can be imported without errors."""
    import src.lib.index.unified_search

    assert src.lib.index.unified_search is not None
