"""Auto-generated importability test for codex."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_codex_importable():
    """Verify that codex can be imported without errors."""
    import src.cli_config.adapters.codex

    assert src.cli_config.adapters.codex is not None
