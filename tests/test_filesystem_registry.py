"""Auto-generated importability test for filesystem_registry."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_filesystem_registry_importable():
    """Verify that filesystem_registry can be imported without errors."""
    import src.mcp.augur_shared.adapters.filesystem_registry

    assert src.mcp.augur_shared.adapters.filesystem_registry is not None
