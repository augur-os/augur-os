"""Auto-generated importability test for plugin_utils."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_plugin_utils_importable():
    """Verify that plugin_utils can be imported without errors."""
    import src.mcp.plugin_utils

    assert src.mcp.plugin_utils is not None
