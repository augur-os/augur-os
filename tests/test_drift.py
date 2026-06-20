"""Auto-generated importability test for drift."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_drift_importable():
    """Verify that drift can be imported without errors."""
    import src.lib.capabilities.drift

    assert src.lib.capabilities.drift is not None
