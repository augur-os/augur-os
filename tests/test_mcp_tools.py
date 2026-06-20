"""Auto-generated importability test for mcp_tools."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_mcp_tools_importable():
    """Verify that mcp_tools can be imported without errors."""
    import src.config.mcp_tools

    assert src.config.mcp_tools is not None
