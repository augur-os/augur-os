"""Auto-generated importability test for page_telemetry."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_page_telemetry_importable():
    """Verify that page_telemetry can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.page_telemetry

    assert src.mcp.augur_framework.tools.infrastructure.page_telemetry is not None
