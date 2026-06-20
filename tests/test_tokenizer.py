"""Auto-generated importability test for tokenizer."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_tokenizer_importable():
    """Verify that tokenizer can be imported without errors."""
    import src.lib.tokenizer

    assert src.lib.tokenizer is not None
