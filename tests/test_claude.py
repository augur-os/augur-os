"""Auto-generated importability test for claude."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_claude_importable():
    """Verify that claude can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude

    assert src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude is not None
