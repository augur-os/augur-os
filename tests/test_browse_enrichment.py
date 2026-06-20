"""Auto-generated importability test for browse_enrichment."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_browse_enrichment_importable():
    """Verify that browse_enrichment can be imported without errors."""
    import src.lib.capabilities.browse_enrichment

    assert src.lib.capabilities.browse_enrichment is not None
