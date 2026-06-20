"""Auto-generated importability test for document_understanding."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_document_understanding_importable():
    """Verify that document_understanding can be imported without errors."""
    import src.lib.index.document_understanding

    assert src.lib.index.document_understanding is not None
