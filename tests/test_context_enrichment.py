"""Auto-generated importability test for context_enrichment."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_context_enrichment_importable():
    """Verify that context_enrichment can be imported without errors."""
    import src.mcp.augur_shared.context_enrichment

    assert src.mcp.augur_shared.context_enrichment is not None
