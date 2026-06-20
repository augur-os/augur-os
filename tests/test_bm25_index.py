"""Auto-generated importability test for bm25_index."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_bm25_index_importable():
    """Verify that bm25_index can be imported without errors."""
    import src.lib.index.bm25_index

    assert src.lib.index.bm25_index is not None
