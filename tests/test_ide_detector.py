"""Auto-generated importability test for ide_detector."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_ide_detector_importable():
    """Verify that ide_detector can be imported without errors."""
    import src.lib.ai.ide_detector

    assert src.lib.ai.ide_detector is not None
