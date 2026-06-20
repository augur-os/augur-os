"""Auto-generated importability test for prompt_registry."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_prompt_registry_importable():
    """Verify that prompt_registry can be imported without errors."""
    import src.lib.ai.prompt_registry

    assert src.lib.ai.prompt_registry is not None
