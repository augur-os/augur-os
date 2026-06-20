"""Auto-generated importability test for mcp_config_controller."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_mcp_config_controller_importable():
    """Verify that mcp_config_controller can be imported without errors."""
    import src.lib.ai.mcp_config_controller

    assert src.lib.ai.mcp_config_controller is not None
