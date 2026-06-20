"""Auto-generated importability test for local_backend_config."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_local_backend_config_importable():
    """Verify that local_backend_config can be imported without errors."""
    import src.lib.extraction.local_backend_config

    assert src.lib.extraction.local_backend_config is not None
