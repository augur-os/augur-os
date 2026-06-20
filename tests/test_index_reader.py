"""Auto-generated importability test for index_reader."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_index_reader_importable():
    """Verify that index_reader can be imported without errors."""
    import src.lib.index.index_reader

    assert src.lib.index.index_reader is not None
