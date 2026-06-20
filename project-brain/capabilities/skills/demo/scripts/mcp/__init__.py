from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# NOTE: submodule imports are intentionally lazy (inside register_tools) rather
# than at module top-level. plugin_tools.py loads this file in full package
# context (where relative imports work), but cli_plugins.py (ADR-260 subcommand
# discovery) loads it bare via spec_from_file_location with no parent package —
# top-level relative imports raise there. Keeping the module top-level
# import-free lets it load cleanly in both contexts.


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    from .demo_tools import register_demo_tools

    register_demo_tools(mcp, mcp_tool_interceptor, metrics)


__all__ = ["register_tools"]
