"""Auto-generated importability test for augur_internal."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_augur_internal_importable():
    """Verify that augur_internal can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.augur_internal

    assert src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.augur_internal is not None
