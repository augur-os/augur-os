"""Auto-generated importability test for reconciliation."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_reconciliation_importable():
    """Verify that reconciliation can be imported without errors."""
    import src.lib.capabilities.reconciliation

    assert src.lib.capabilities.reconciliation is not None
