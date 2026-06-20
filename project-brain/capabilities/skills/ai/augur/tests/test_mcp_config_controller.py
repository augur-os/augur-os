"""Auto-generated importability test for mcp_config_controller."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


def test_mcp_config_controller_importable():
    """Verify that mcp_config_controller can be imported without errors."""
    import importlib
    mod = importlib.import_module("src.lib.ai.mcp_config_controller")
    assert mod is not None
