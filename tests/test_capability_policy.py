"""Auto-generated importability test for capability_policy."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_capability_policy_importable():
    """Verify that capability_policy can be imported without errors."""
    import src.mcp.augur_framework.tools.hubs.capability_policy

    assert src.mcp.augur_framework.tools.hubs.capability_policy is not None
