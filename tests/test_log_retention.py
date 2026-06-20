"""Auto-generated importability test for log_retention."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_log_retention_importable():
    """Verify that log_retention can be imported without errors."""
    import src.config.log_retention

    assert src.config.log_retention is not None
