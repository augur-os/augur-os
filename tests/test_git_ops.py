"""Auto-generated importability test for git_ops."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_git_ops_importable():
    """Verify that git_ops can be imported without errors."""
    import src.lib.git_ops

    assert src.lib.git_ops is not None
