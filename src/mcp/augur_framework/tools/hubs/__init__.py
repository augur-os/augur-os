"""Hub Tools - Domain-specific vertical functionality"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_hub_tools(mcp: FastMCP, interceptor=None, metrics: Any = None) -> None:
    """Register all hub tools with the MCP server."""
    from .agent_registry import register_tools as register_agent_registry
    from .capabilities import register_tools as register_capabilities
    from .capability_policy import register_tools as register_capability_policy
    from .widgets import register_tools as register_widgets

    register_capabilities(mcp, interceptor=interceptor, metrics=metrics)
    register_capability_policy(mcp, interceptor=interceptor, metrics=metrics)
    register_agent_registry(mcp, interceptor=interceptor, metrics=metrics)
    register_widgets(mcp, interceptor=interceptor, metrics=metrics)


__all__ = ["register_hub_tools"]
