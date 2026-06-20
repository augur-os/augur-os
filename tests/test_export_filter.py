"""Auto-generated importability test for export_filter."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_export_filter_importable():
    """Verify that export_filter can be imported without errors."""
    import src.lib.capabilities.export_filter

    assert src.lib.capabilities.export_filter is not None
