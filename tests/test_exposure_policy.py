"""Auto-generated importability test for exposure_policy."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_exposure_policy_importable():
    """Verify that exposure_policy can be imported without errors."""
    import src.lib.capabilities.exposure_policy

    assert src.lib.capabilities.exposure_policy is not None
