"""Auto-generated importability test for artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_artifacts_importable():
    """Verify that artifacts can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.artifacts

    assert src.mcp.augur_framework.tools.infrastructure.artifacts is not None
