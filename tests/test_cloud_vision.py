"""Auto-generated importability test for cloud_vision."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_cloud_vision_importable():
    """Verify that cloud_vision can be imported without errors."""
    import src.lib.extraction.cloud_vision

    assert src.lib.extraction.cloud_vision is not None
