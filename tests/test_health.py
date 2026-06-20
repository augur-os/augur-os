"""Auto-generated importability test for health."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_health_importable():
    """Verify that health can be imported without errors."""
    import src.mcp.augur_core.tools.core.health

    assert src.mcp.augur_core.tools.core.health is not None
