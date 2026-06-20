"""Auto-generated importability test for config_fix."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_config_fix_importable():
    """Verify that config_fix can be imported without errors."""
    import src.scripts.config_fix

    assert src.scripts.config_fix is not None
