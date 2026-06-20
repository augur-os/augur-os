"""Auto-generated importability test for agent_capabilities."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_agent_capabilities_importable():
    """Verify that agent_capabilities can be imported without errors."""
    import src.lib.ai.agent_capabilities

    assert src.lib.ai.agent_capabilities is not None
