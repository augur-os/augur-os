"""Auto-generated importability test for cli_detect."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_cli_detect_importable():
    """Verify that cli_detect can be imported without errors."""
    import src.lib.ai.cli_detect

    assert src.lib.ai.cli_detect is not None
