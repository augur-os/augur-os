"""Auto-generated importability test for scheduled_executions."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_scheduled_executions_importable():
    """Verify that scheduled_executions can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions

    assert src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions is not None
