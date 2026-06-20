"""Auto-generated importability test for memory_store."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_memory_store_importable():
    """Verify that memory_store can be imported without errors."""
    import src.lib.knowledge.memory_store

    assert src.lib.knowledge.memory_store is not None
