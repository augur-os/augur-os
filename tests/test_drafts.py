"""Auto-generated importability test for drafts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_drafts_importable():
    """Verify that drafts can be imported without errors."""
    import src.lib.capabilities.drafts

    assert src.lib.capabilities.drafts is not None
