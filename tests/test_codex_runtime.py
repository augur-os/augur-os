"""Auto-generated importability test for codex_runtime."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_codex_runtime_importable():
    """Verify that codex_runtime can be imported without errors."""
    import src.cli_config.codex_runtime

    assert src.cli_config.codex_runtime is not None
