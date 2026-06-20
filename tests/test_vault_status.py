"""Auto-generated importability test for vault_status."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_vault_status_importable():
    """Verify that vault_status can be imported without errors."""
    import src.mcp.augur_framework.tools.internal.vault_status

    assert src.mcp.augur_framework.tools.internal.vault_status is not None
