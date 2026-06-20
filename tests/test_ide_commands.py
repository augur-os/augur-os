"""Auto-generated importability test for ide_commands."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_ide_commands_importable():
    """Verify that ide_commands can be imported without errors."""
    import src.lib.ai.ide_commands

    assert src.lib.ai.ide_commands is not None
