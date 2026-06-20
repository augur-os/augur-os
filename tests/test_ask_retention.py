"""Auto-generated importability test for ask_retention."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_ask_retention_importable():
    """Verify that ask_retention can be imported without errors."""
    import src.mcp.augur_core.tools.core.ask_retention

    assert src.mcp.augur_core.tools.core.ask_retention is not None
