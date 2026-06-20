"""Auto-generated importability test for llm_retry."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_llm_retry_importable():
    """Verify that llm_retry can be imported without errors."""
    import src.lib.llm_retry

    assert src.lib.llm_retry is not None
