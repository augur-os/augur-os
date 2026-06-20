"""Auto-generated importability test for job_manager."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_job_manager_importable():
    """Verify that job_manager can be imported without errors."""
    import src.mcp.augur_shared.job_manager

    assert src.mcp.augur_shared.job_manager is not None
