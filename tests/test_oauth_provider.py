"""Auto-generated importability test for oauth_provider."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_oauth_provider_importable():
    """Verify that oauth_provider can be imported without errors."""
    import src.mcp.augur_shared.oauth_provider

    assert src.mcp.augur_shared.oauth_provider is not None
