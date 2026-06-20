"""Auto-generated importability test for formatters."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_formatters_importable():
    """Verify that formatters can be imported without errors."""
    import src.logging.formatters

    assert src.logging.formatters is not None
