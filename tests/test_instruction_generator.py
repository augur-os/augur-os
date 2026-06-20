"""Auto-generated importability test for instruction_generator."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_instruction_generator_importable():
    """Verify that instruction_generator can be imported without errors."""
    import src.lib.ai.instruction_generator

    assert src.lib.ai.instruction_generator is not None
