"""Auto-generated importability test for symbol_extractor."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_symbol_extractor_importable():
    """Verify that symbol_extractor can be imported without errors."""
    import src.lib.index.symbol_extractor

    assert src.lib.index.symbol_extractor is not None
