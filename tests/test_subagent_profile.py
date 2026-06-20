"""Auto-generated importability test for subagent_profile."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_subagent_profile_importable():
    """Verify that subagent_profile can be imported without errors."""
    import src.lib.ai.subagent_profile

    assert src.lib.ai.subagent_profile is not None
