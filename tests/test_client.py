"""Auto-generated importability test for client."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_client_importable():
    """Verify that client can be imported without errors."""
    import src.lib.ai.client

    assert src.lib.ai.client is not None
