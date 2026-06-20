"""Auto-generated importability test for launch_inventory."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_launch_inventory_importable():
    """Verify that launch_inventory can be imported without errors."""
    import src.lib.launch_inventory

    assert src.lib.launch_inventory is not None
