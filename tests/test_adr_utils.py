"""Auto-generated importability test for adr_utils."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_adr_utils_importable():
    """Verify that adr_utils can be imported without errors."""
    import src.lib.adr_utils

    assert src.lib.adr_utils is not None


def test_normalize_adr_status_handles_non_string():
    """Non-string statuses (e.g. malformed YAML frontmatter) must not crash."""
    from src.lib.adr_utils import normalize_adr_status

    assert normalize_adr_status(123) == "Other"
    assert normalize_adr_status(None) == "Other"
    assert normalize_adr_status(True) == "Other"
