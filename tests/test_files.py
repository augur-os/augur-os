"""Auto-generated importability test for files."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_files_importable():
    """Verify that files can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.files

    assert src.mcp.augur_framework.tools.infrastructure.files is not None
