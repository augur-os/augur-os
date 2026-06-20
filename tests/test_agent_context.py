"""Auto-generated importability test for agent_context."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_agent_context_importable():
    """Verify that agent_context can be imported without errors."""
    import src.mcp.augur_shared.agent_context

    assert src.mcp.augur_shared.agent_context is not None
