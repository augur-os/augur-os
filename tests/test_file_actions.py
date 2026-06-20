"""Auto-generated importability test for file_actions."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_file_actions_importable():
    """Verify that file_actions can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.browse.file_actions

    assert src.mcp.augur_framework.tools.infrastructure.browse.file_actions is not None
