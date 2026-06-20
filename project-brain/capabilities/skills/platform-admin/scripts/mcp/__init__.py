"""Platform Admin MCP tools for the dev hub."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import logger
from .tools_action import register_action_tools
from .tools_dashboard import register_dashboard_tools


def register_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any) -> None:
    """Register all platform-admin MCP tools."""
    logger.info("Registering platform-admin MCP tools")
    register_action_tools(mcp, mcp_tool_interceptor, metrics)
    register_dashboard_tools(mcp, mcp_tool_interceptor, metrics)
    logger.info("Platform-admin MCP tools registered successfully")


__all__ = ["register_tools"]
