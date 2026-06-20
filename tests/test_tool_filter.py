"""Auto-generated importability test for tool_filter."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_tool_filter_importable():
    """Verify that tool_filter can be imported without errors."""
    import src.mcp.augur_shared.tool_filter

    assert src.mcp.augur_shared.tool_filter is not None
