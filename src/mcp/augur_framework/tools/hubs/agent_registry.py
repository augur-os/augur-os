"""Agent registry tool — expose project + plugin agents to the dashboard.

ADR-464: Reads the canonical plugins/agents/registry.json and returns all
agents with their roles, models, tiers, and sync status across clients.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server import Server

logger = logging.getLogger(__name__)


def _read_registry() -> dict:
    """Read registry.json from the project root."""
    from src.config.paths import get_project_root

    registry_path = get_project_root() / "plugins" / "agents" / "registry.json"
    if not registry_path.exists():
        return {"schema": "2.0", "agents": {}}

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"schema": "2.0", "agents": {}}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read registry.json: {e}")
        return {"schema": "2.0", "agents": {}}


def _get_sync_status() -> dict[str, list[str]]:
    """Check which client agent dirs exist and list their agents."""
    from src.config.paths import get_project_root

    root = get_project_root()
    client_dirs = {
        "claude-code": root / ".claude" / "agents",
        "gemini": root / ".gemini" / "agents",
        "codex": root / ".codex" / "agents",
        "cursor": root / ".cursor" / "agents",
    }

    status: dict[str, list[str]] = {}
    for client, path in client_dirs.items():
        if path.is_dir():
            status[client] = sorted(f.stem for f in path.glob("*.md"))
        else:
            status[client] = []

    return status


def _build_response() -> dict:
    """Build the agent registry response."""
    registry = _read_registry()
    sync_status = _get_sync_status()
    agents_raw = registry.get("agents", {})

    agents = []
    for agent_id, data in sorted(agents_raw.items()):
        agents.append(
            {
                "id": agent_id,
                "role": data.get("role", "executor"),
                "defaultModel": data.get("defaultModel", "sonnet"),
                "tools": data.get("tools", []),
                "master_client": data.get("master_client", "claude-code"),
                "source": data.get("source", "project"),
                "plugin": data.get("plugin"),
                "description": data.get("description", ""),
                "tiers": list(data.get("tiers", {}).keys()),
                "hasMcpServers": bool(data.get("mcp_servers")),
                "hasIsolation": bool(data.get("isolation")),
            }
        )

    return {
        "schema": registry.get("schema", "2.0"),
        "agents": agents,
        "total": len(agents),
        "by_source": {
            "project": sum(1 for a in agents if a["source"] == "project"),
            "plugin": sum(1 for a in agents if a["source"] == "plugin"),
        },
        "sync_status": {client: len(names) for client, names in sync_status.items()},
    }


def register_tools(mcp: Server, interceptor=None, metrics=None) -> None:
    """Register agent-registry tool."""

    @mcp.tool(name="agent-registry")
    async def agent_registry() -> dict:
        """List all registered agents with their roles, models, tiers, and sync status.

        Returns the canonical project/plugin agent registry plus cross-client
        sync status for Claude Code, Gemini, Codex, and Cursor.
        """
        return _build_response()
