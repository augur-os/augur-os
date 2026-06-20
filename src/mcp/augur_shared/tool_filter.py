"""MCP Tool Filter - Filter registered tools based on configuration.

This module provides a wrapper to filter MCP tools based on the
mcp_tools.yaml configuration file. Disabled tools are simply not
registered with the MCP server.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp")


def _get_enabled_tools() -> set[str]:
    """Load enabled tools from configuration."""
    try:
        from src.mcp.augur_shared.compat import get_enabled_tools

        return get_enabled_tools()
    except Exception as e:
        logger.warning(f"Failed to load tool config, enabling all: {e}")
        return set()  # Empty set means no filtering


def _is_tool_enabled(tool_name: str) -> bool:
    """Check if a tool is enabled."""
    try:
        from src.mcp.augur_shared.compat import is_tool_enabled

        return is_tool_enabled(tool_name)
    except Exception:
        return True  # Enable by default if config unavailable


class FilteredToolDecorator:
    """A decorator factory that filters tool registration based on config."""

    def __init__(self, original_tool_decorator: Callable):
        self._original = original_tool_decorator
        self._enabled_tools: set[str] | None = None
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy load enabled tools."""
        if not self._loaded:
            self._enabled_tools = _get_enabled_tools()
            self._loaded = True

    def __call__(self, name: str | None = None, **kwargs: Any):
        """Decorate a tool function, potentially skipping registration."""

        def decorator(func: Callable):
            tool_name = name or func.__name__

            # Check if tool is enabled
            if not _is_tool_enabled(tool_name):
                logger.info(f"Tool '{tool_name}' disabled by config, skipping registration")

                # Return a no-op async function that returns an error message
                async def disabled_tool(*args, **kwargs):
                    return f"Tool '{tool_name}' is disabled. Enable it in the MCP Config dashboard."

                return disabled_tool

            # Tool is enabled, register normally
            return self._original(name=name, **kwargs)(func)

        return decorator


def create_filtered_mcp(mcp_instance):
    """
    Wrap an MCP instance to filter tools based on configuration.

    Args:
        mcp_instance: The FastMCP instance to wrap

    Returns:
        The same instance with tool decorator wrapped
    """
    # Store original tool decorator
    original_tool = mcp_instance.tool

    # Create filtered decorator
    filtered_tool = FilteredToolDecorator(original_tool)

    # Replace with filtered version
    mcp_instance.tool = filtered_tool

    return mcp_instance


def filter_existing_tools(mcp_instance) -> dict[str, Any]:
    """
    Remove already-registered tools that are disabled.

    Call this AFTER all tools are registered to filter based on config.

    Args:
        mcp_instance: The FastMCP instance

    Returns:
        dict with count of filtered tools per category
    """
    enabled_tools = _get_enabled_tools()

    # If no config found (empty set), don't filter anything
    if not enabled_tools:
        # Check if config file exists - if so, empty means filter all static
        try:
            from src.mcp.augur_shared.compat import get_mcp_config_path

            config_path = get_mcp_config_path()
            if not config_path.exists():
                logger.info("No MCP tools config found, all tools enabled")
                return {"enabled": -1, "disabled": 0, "filtered": False}
        except Exception:
            return {"enabled": -1, "disabled": 0, "filtered": False}

    # Get all registered tools
    if not hasattr(mcp_instance, '_tools'):
        return {"enabled": -1, "disabled": 0, "filtered": False}

    len(mcp_instance._tools)
    tools_to_remove: list[str] = []

    for tool_name in list(mcp_instance._tools.keys()):
        if tool_name not in enabled_tools:
            # For tools not in the enabled_tools set, check is_tool_enabled()
            # This properly handles unknown tools (returns True) and configured tools
            if not _is_tool_enabled(tool_name):
                tools_to_remove.append(tool_name)

    for tool_name in tools_to_remove:
        del mcp_instance._tools[tool_name]
        logger.info(f"Filtered out disabled tool: {tool_name}")

    return {
        "enabled": len(mcp_instance._tools),
        "disabled": len(tools_to_remove),
        "filtered": True,
        "removed": tools_to_remove,
    }
