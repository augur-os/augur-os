"""Project-scoped MCP config generation for layered harnesses (ADR-783)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from src.cli_config.manifest import ServerEntry


def generate_project_mcp_json(servers: Sequence[ServerEntry], dest: Path) -> Path:
    """Write a repo-local `.mcp.json` containing only project-scoped servers.

    Entries are written fully resolved (absolute paths, no ``${AUGUR_ROOT}``
    templates): Copilot CLI performs no variable expansion, and Claude only
    expands variables present in the session environment.
    """
    entries = {server.id: _server_payload(server) for server in servers if server.scope == "project"}
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"mcpServers": entries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _server_payload(server: ServerEntry) -> dict[str, object]:
    from src.cli_config.adapters._paths import resolve_entry
    from src.config.paths import get_project_root

    resolved = resolve_entry(server)
    payload: dict[str, object] = {
        "command": resolved.command,
        "args": list(resolved.args),
    }
    if resolved.cwd_required:
        payload["cwd"] = str(get_project_root())
    if resolved.env:
        payload["env"] = dict(resolved.env)
    return payload
