"""Auto-generated importability test for models."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_models_importable():
    """Verify that models can be imported without errors."""
    import src.mcp.augur_core.tools.core.models

    assert src.mcp.augur_core.tools.core.models is not None
