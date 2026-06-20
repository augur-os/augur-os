"""Auto-generated importability test for mcp_sdk."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_mcp_sdk_importable():
    """Verify that mcp_sdk can be imported without errors."""
    import src.mcp.augur_shared.mcp_sdk

    assert src.mcp.augur_shared.mcp_sdk is not None
