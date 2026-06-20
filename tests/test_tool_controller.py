"""Auto-generated importability test for tool_controller."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_tool_controller_importable():
    """Verify that tool_controller can be imported without errors."""
    import src.mcp.augur_shared.tool_controller

    assert src.mcp.augur_shared.tool_controller is not None
