"""Auto-generated importability test for compat."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_compat_importable():
    """Verify that compat can be imported without errors."""
    import src.mcp.augur_shared.compat

    assert src.mcp.augur_shared.compat is not None
