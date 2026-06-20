"""Shared bootstrap for augur-core tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SRC_MCP_DIR = PROJECT_ROOT / "src" / "mcp"
if SRC_MCP_DIR.exists() and str(SRC_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_MCP_DIR))

try:
    import mcp  # noqa: F401
    import mcp.types  # noqa: F401
except ImportError:
    mcp_module = sys.modules.get("mcp")
    if mcp_module is None:
        mcp_module = types.ModuleType("mcp")
        sys.modules["mcp"] = mcp_module

    mcp_types = types.ModuleType("mcp.types")

    class ToolAnnotations(dict):
        pass

    mcp_types.ToolAnnotations = ToolAnnotations
    mcp_module.types = mcp_types
    sys.modules["mcp.types"] = mcp_types
