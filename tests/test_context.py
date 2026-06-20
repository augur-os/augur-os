"""Auto-generated importability test for context."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_context_importable():
    """Verify that context can be imported without errors.

    Some earlier sweep tests may import other ``src.plugins.*`` submodules
    without touching context, leaving ``src.plugins.context`` unbound as an
    attribute on the cached ``src.plugins`` module. Use importlib to
    force-resolve the submodule object directly rather than relying on
    attribute access on the parent package.
    """
    module = importlib.import_module("src.plugins.context")
    assert module is not None
