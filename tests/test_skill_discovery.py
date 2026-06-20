"""Auto-generated importability test for skill_discovery."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_skill_discovery_importable():
    """Verify that skill_discovery can be imported without errors."""
    import src.plugins.skill_discovery

    assert src.plugins.skill_discovery is not None
