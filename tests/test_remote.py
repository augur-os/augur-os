"""Auto-generated importability test for remote."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_remote_importable():
    """Verify that remote can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.settings.remote

    assert src.mcp.augur_framework.tools.infrastructure.settings.remote is not None
