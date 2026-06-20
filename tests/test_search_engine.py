"""Auto-generated importability test for search_engine."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_search_engine_importable():
    """Verify that search_engine can be imported without errors."""
    import src.lib.index.search_engine

    assert src.lib.index.search_engine is not None
