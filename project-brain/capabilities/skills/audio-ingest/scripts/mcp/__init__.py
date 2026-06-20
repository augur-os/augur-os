"""audio-ingest MCP tool registration."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from .tools_audio import register

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    """Register audio-ingest MCP tools."""
    register(mcp, mcp_tool_interceptor, metrics)


__all__ = ["register_tools"]
