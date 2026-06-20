"""Core MCP resources."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

STATIC_DIR = Path(__file__).parent.parent.parent / "augur_shared" / "static_resources"


def register_core_resources(mcp: "FastMCP") -> None:
    """Register core documentation as MCP resources."""

    @mcp.resource("augur://core/mcp-registry", name="core/mcp-registry")
    def get_mcp_registry() -> str:
        """Overview of available MCP servers and integration patterns."""
        registry_file = STATIC_DIR / "mcp-registry.md"
        if registry_file.exists():
            return registry_file.read_text(encoding="utf-8")
        return "MCP Registry documentation not found."
