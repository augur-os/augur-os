"""Auto-generated importability test for crew_parser."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_crew_parser_importable():
    """Verify that crew_parser can be imported without errors."""
    import src.lib.ai.crew_parser

    assert src.lib.ai.crew_parser is not None
