"""Auto-generated importability test for dev."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_dev_importable():
    """Verify that dev can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.browse.dev

    assert src.mcp.augur_framework.tools.infrastructure.browse.dev is not None
