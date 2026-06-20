"""Auto-generated importability test for baseline."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_baseline_importable():
    """Verify that baseline can be imported without errors."""
    import src.lib.capabilities.baseline

    assert src.lib.capabilities.baseline is not None
