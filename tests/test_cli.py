"""Auto-generated importability test for cli."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_cli_importable():
    """Verify that cli can be imported without errors."""
    import src.cli

    assert src.cli is not None
