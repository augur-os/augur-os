"""Auto-generated importability test for token_estimator."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_token_estimator_importable():
    """Verify that token_estimator can be imported without errors."""
    import src.lib.ai.token_estimator

    assert src.lib.ai.token_estimator is not None
