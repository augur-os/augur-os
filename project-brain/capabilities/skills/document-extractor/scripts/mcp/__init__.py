"""Document-extractor MCP tool registration."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from .tools_extract import register_extract_tools


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    """Register all document-extractor MCP tools."""
    register_extract_tools(mcp, mcp_tool_interceptor, metrics)
