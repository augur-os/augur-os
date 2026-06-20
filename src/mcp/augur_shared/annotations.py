"""Helpers for MCP tool annotations."""

from __future__ import annotations

from typing import Any

try:
    from mcp.types import ToolAnnotations
except ModuleNotFoundError:

    class ToolAnnotations:  # type: ignore[no-redef]
        """Minimal annotation object for non-server import contexts."""

        def __init__(self, **data: Any) -> None:
            self.__dict__.update(data)


def tool_annotations(data: dict[str, Any]) -> ToolAnnotations:
    """Build ToolAnnotations from a simple dict."""
    return ToolAnnotations(**data)
