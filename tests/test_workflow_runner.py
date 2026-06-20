"""Auto-generated importability test for workflow_runner."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_workflow_runner_importable():
    """Verify that workflow_runner can be imported without errors."""
    import src.scripts.workflow_runner

    assert src.scripts.workflow_runner is not None
