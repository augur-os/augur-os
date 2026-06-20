"""Auto-generated importability test for pins."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_pins_importable():
    """Verify that pins can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.pins

    assert src.mcp.augur_framework.tools.infrastructure.pins is not None
