"""Vault sync MCP tools (read status + one-click commit→pull→push)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_READ_ONLY = {"destructiveHint": False, "idempotentHint": True, "openWorldHint": False, "readOnlyHint": True}
_WRITE = {"destructiveHint": False, "idempotentHint": False, "openWorldHint": True, "readOnlyHint": False}


def register_vault_sync_tools(mcp: FastMCP, mcp_tool_interceptor: Callable, metrics: Any) -> None:
    """Register vault-sync-status (read) and vault-sync (write)."""

    @mcp.tool(name="vault-sync-status", annotations={"title": "Vault Sync Status", **_READ_ONLY})
    @mcp_tool_interceptor
    async def vault_sync_status_tool() -> str:
        """Report whether the vault repo has uncommitted or unpushed changes."""
        metrics.track_tool("vault_sync_status")
        from src.lib.vault_sync import vault_sync_status

        return json.dumps(vault_sync_status(), indent=2)

    @mcp.tool(name="vault-sync", annotations={"title": "Vault Sync", **_WRITE})
    @mcp_tool_interceptor
    async def vault_sync_tool() -> str:
        """Commit, pull, and push the vault repo (no force; surfaces conflicts)."""
        metrics.track_tool("vault_sync")
        from src.lib.vault_sync import vault_sync_run

        return json.dumps(vault_sync_run(), indent=2)
