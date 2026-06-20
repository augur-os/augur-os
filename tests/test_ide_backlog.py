"""Auto-generated importability test for ide_backlog."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_ide_backlog_importable():
    """Verify that ide_backlog can be imported without errors."""
    import src.lib.ai.ide_backlog

    assert src.lib.ai.ide_backlog is not None
