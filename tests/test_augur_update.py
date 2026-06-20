"""Auto-generated importability test for augur_update."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_augur_update_importable():
    """Verify that augur_update can be imported without errors."""
    import src.scripts.augur_update

    assert src.scripts.augur_update is not None
