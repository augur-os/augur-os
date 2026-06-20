"""Auto-generated importability test for background_routines."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_background_routines_importable():
    """Verify that background_routines can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.browse.background_routines

    assert src.mcp.augur_framework.tools.infrastructure.browse.background_routines is not None
