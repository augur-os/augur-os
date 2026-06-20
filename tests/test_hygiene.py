"""Auto-generated importability test for hygiene."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_hygiene_importable():
    """Verify that hygiene can be imported without errors."""
    import src.mcp.augur_core.tools.core.hygiene

    assert src.mcp.augur_core.tools.core.hygiene is not None
