"""Auto-generated importability test for skill_scorer."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_skill_scorer_importable():
    """Verify that skill_scorer can be imported without errors."""
    import src.lib.skill_scorer

    assert src.lib.skill_scorer is not None
