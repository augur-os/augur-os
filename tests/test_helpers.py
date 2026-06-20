"""Auto-generated importability test for helpers."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_helpers_importable():
    """Verify that helpers can be imported without errors."""
    import src.mcp.augur_core.tools.core.helpers

    assert src.mcp.augur_core.tools.core.helpers is not None
