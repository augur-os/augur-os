"""Auto-generated importability test for search."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_search_importable():
    """Verify that search can be imported without errors."""
    import src.lib.knowledge.search

    assert src.lib.knowledge.search is not None
