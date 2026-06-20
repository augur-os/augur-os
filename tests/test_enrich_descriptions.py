"""Auto-generated importability test for enrich_descriptions."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_enrich_descriptions_importable():
    """Verify that enrich_descriptions can be imported without errors."""
    import src.lib.index.enrich_descriptions

    assert src.lib.index.enrich_descriptions is not None
