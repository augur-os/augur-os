"""Auto-generated importability test for external_services."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_external_services_importable():
    """Verify that external_services can be imported without errors."""
    import src.lib.external_services

    assert src.lib.external_services is not None
