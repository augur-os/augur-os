"""Auto-generated importability test for oauth_routes."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_oauth_routes_importable():
    """Verify that oauth_routes can be imported without errors."""
    import src.mcp.augur_shared.oauth_routes

    assert src.mcp.augur_shared.oauth_routes is not None
