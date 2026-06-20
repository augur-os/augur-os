"""Auto-generated importability test for daily_logger."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_daily_logger_importable():
    """Verify that daily_logger can be imported without errors."""
    import src.lib.knowledge.daily_logger

    assert src.lib.knowledge.daily_logger is not None
