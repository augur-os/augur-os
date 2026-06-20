"""Auto-generated importability test for base."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_base_importable():
    """Verify that base can be imported without errors."""
    import src.cli_config.adapters.base

    assert src.cli_config.adapters.base is not None
