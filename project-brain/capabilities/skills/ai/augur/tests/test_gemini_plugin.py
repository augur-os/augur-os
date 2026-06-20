"""Auto-generated importability test for gemini_plugin."""
from __future__ import annotations

import sys
from pathlib import Path

import importlib

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MCP_SRC = PROJECT_ROOT / "src" / "mcp"
if str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))


def test_gemini_plugin_importable():
    """Verify that gemini_plugin can be imported without errors."""
    mod = importlib.import_module("skills.ai.scripts.sync_agents.adapters.gemini_plugin")
    assert mod is not None
