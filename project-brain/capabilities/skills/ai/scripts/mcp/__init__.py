"""MCP tools for ai skill.

Exposes AI bridge orchestration capabilities plus shared command discovery
runtime used by `/commands`.
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from src.lib.frontmatter_utils import load_skill_frontmatter

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.ai")


def _get_cli_agents_file() -> Path:
    """Return the writable CLI agents config in the vault config root."""
    from src.config.paths import get_vault_config_dir

    return get_vault_config_dir() / "ai" / "cli_agents.yaml"


def _read_skill_frontmatter(skill_md: Path) -> dict[str, Any]:
    """Read YAML frontmatter from a SKILL.md file."""
    return load_skill_frontmatter(skill_md)


def _build_skill_dashboard_path(skill_id: str, frontmatter: dict[str, Any], has_dashboard: bool) -> str | None:
    """Build the mounted dashboard route for a skill when possible."""
    if not has_dashboard:
        return None
    hub_id = frontmatter.get("x-augur-hub")
    if not isinstance(hub_id, str) or not hub_id.strip():
        return None
    return f"/{hub_id.strip()}/{skill_id}"


def _coerce_client_filter(clients: str | list[str] | None) -> list[str] | None:
    """Normalize dashboard and CLI client filters into a sync-status list."""
    if clients is None:
        return None
    if isinstance(clients, str):
        return [client.strip() for client in clients.split(",") if client.strip()] or None
    return [str(client).strip() for client in clients if str(client).strip()] or None


def _build_command_entry(cmd: Any) -> dict[str, Any]:
    # Canonical impl lives in the shared command_listing module (deferred import
    # keeps module-load lightweight, matching this file's existing pattern).
    from src.plugins.command_listing import build_command_entry

    return build_command_entry(cmd)


def _render_commands_payload() -> dict[str, Any]:
    """Return grouped slash commands, auto loop commands, and non-command skills.

    Thin wrapper over the shared ``command_listing.render_commands_payload`` so
    the ``list-commands`` tool and ``aug discover --commands`` cannot drift apart.
    """
    from src.plugins.command_listing import render_commands_payload

    return render_commands_payload()


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register ai tools with the MCP server."""
    logger.info("Registering ai MCP tools...")

    @mcp.tool(
        name="get-ai-status",
        annotations=tool_annotations(
            {
                "title": "Get AI Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_ai_status_tool() -> str:
        """Get current status of the AI skill.

        Returns status of agent orchestration, crew management, and offload routing.

        Returns:
            str: JSON with skill status
        """
        metrics.track_tool("get_ai_status", skill="ai")
        return json.dumps(
            {
                "skill": "ai",
                "status": "active",
                "version": "1.0.0",
            },
            indent=2,
        )

    @mcp.tool(
        name="list-commands",
        annotations=tool_annotations(
            {
                "title": "List Commands",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_commands_tool() -> str:
        """Return grouped slash command data from distributed skill metadata."""
        metrics.track_tool("list_commands", skill="ai")
        return json.dumps(_render_commands_payload(), indent=2)

    @mcp.tool(
        name="list-client-skills",
        annotations=tool_annotations(
            {
                "title": "List Client-Native Skills",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_client_skills_tool(clients: str | None = None) -> str:
        """Discover client-native skills across configured IDE clients."""
        metrics.track_tool("list_client_skills", skill="ai")
        from skills.ai.scripts.ops.client_discovery import discover_client_skills

        client_list = [c.strip() for c in clients.split(",")] if clients else None
        results = discover_client_skills(clients=client_list)
        return json.dumps(
            {"success": True, "count": len(results), "skills": results},
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="get-sync-status",
        annotations=tool_annotations(
            {
                "title": "Get Sync Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_sync_status_tool(
        clients: str | list[str] | None = None,
        preset: str | None = None,
    ) -> str:
        """Get Augur sync status for each configured client target."""
        metrics.track_tool("get_sync_status", skill="ai")
        from skills.ai.scripts.ops.sync_status import get_sync_status

        # Dashboard callers pass preset="device" to request the default client set.
        _ = preset
        client_list = _coerce_client_filter(clients)
        result = get_sync_status(clients=client_list)
        return json.dumps(
            {"success": True, "clients": result},
            indent=2,
            default=str,
        )

    _SKILL_DIR = Path(__file__).resolve().parents[2]  # ai/
    _CATALOG_FILE = _SKILL_DIR / "augur" / "config" / "agentic_tools.yaml"

    @mcp.tool(
        name="manage-tools-catalog",
        annotations=tool_annotations(
            {
                "title": "Manage Agentic Tools Catalog",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def manage_tools_catalog_tool(action: str = "read", data: str = "") -> str:
        """Read or update the agentic tools comparison catalog.

        Args:
            action: 'read' to fetch catalog, 'update' to overwrite with new data
            data: JSON string of catalog data (required for 'update' action)

        Returns:
            str: JSON catalog data on read, or JSON success/error on update
        """
        import yaml

        metrics.track_tool("manage_tools_catalog", skill="ai")

        if action == "read":
            try:
                if not _CATALOG_FILE.exists():
                    return json.dumps({})
                with open(_CATALOG_FILE, "r") as f:
                    catalog = yaml.safe_load(f) or {}
                return json.dumps(catalog)
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif action == "update":
            if not data:
                return json.dumps({"success": False, "error": "data is required for update action"})
            try:
                new_data = json.loads(data)
                _CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(_CATALOG_FILE, "w") as f:
                    yaml.safe_dump(new_data, f, sort_keys=False, allow_unicode=True)
                return json.dumps({"success": True})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})

        else:
            return json.dumps({"error": f"Unknown action: {action}. Use 'read' or 'update'."})

    @mcp.tool(
        name="manage-cli-agents",
        annotations=tool_annotations(
            {
                "title": "Manage CLI Agent Configurations",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def manage_cli_agents_tool(action: str = "list", agent_id: str = "", config_data: str = "") -> str:
        """Read or update CLI agent launch configurations.

        Args:
            action: 'list', 'upsert', or 'delete'
            agent_id: agent key for upsert/delete
            config_data: JSON object with cmd/cwd/env for upsert

        Returns:
            str: JSON response
        """
        import yaml

        metrics.track_tool("manage_cli_agents", skill="ai")
        cli_agents_file = _get_cli_agents_file()

        try:
            if cli_agents_file.exists():
                with open(cli_agents_file, "r") as f:
                    current = yaml.safe_load(f) or {}
            else:
                current = {}
            agents = current.get("agents") or {}
            if not isinstance(agents, dict):
                agents = {}
        except Exception as e:
            return json.dumps({"success": False, "error": f"Failed to read CLI configs: {e}"})

        if action == "list":
            return json.dumps({"success": True, "agents": agents}, indent=2)

        if action == "upsert":
            if not agent_id:
                return json.dumps({"success": False, "error": "agent_id is required for upsert"})
            if not config_data:
                return json.dumps({"success": False, "error": "config_data is required for upsert"})

            try:
                parsed = json.loads(config_data)
            except json.JSONDecodeError:
                return json.dumps({"success": False, "error": "config_data must be valid JSON"})

            if not isinstance(parsed, dict):
                return json.dumps({"success": False, "error": "config_data must be a JSON object"})

            cmd = parsed.get("cmd")
            if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) and x for x in cmd):
                return json.dumps({"success": False, "error": "config_data.cmd must be a non-empty string array"})

            cwd = parsed.get("cwd", ".")
            if not isinstance(cwd, str) or not cwd:
                return json.dumps({"success": False, "error": "config_data.cwd must be a non-empty string"})

            env = parsed.get("env", {})
            if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
                return json.dumps({"success": False, "error": "config_data.env must be an object of string key/value pairs"})

            agents[agent_id] = {
                "cmd": cmd,
                "cwd": cwd,
                "env": env,
            }

            try:
                cli_agents_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cli_agents_file, "w") as f:
                    yaml.safe_dump({"agents": agents}, f, sort_keys=False, allow_unicode=True)
                return json.dumps({"success": True, "action": "upsert", "agent_id": agent_id, "message": "Agent saved", "config": parsed}, indent=2)
            except Exception as e:
                return json.dumps({"success": False, "error": f"Failed to write CLI configs: {e}"})

        if action == "delete":
            if not agent_id:
                return json.dumps({"success": False, "error": "agent_id is required for delete"})
            if agent_id not in agents:
                return json.dumps({"success": False, "error": f"agent '{agent_id}' not found"})

            try:
                del agents[agent_id]
                cli_agents_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cli_agents_file, "w") as f:
                    yaml.safe_dump({"agents": agents}, f, sort_keys=False, allow_unicode=True)
                return json.dumps({"success": True, "action": "delete", "agent_id": agent_id}, indent=2)
            except Exception as e:
                return json.dumps({"success": False, "error": f"Failed to write CLI configs: {e}"})

        return json.dumps({"success": False, "error": f"Unknown action: {action}. Use 'list', 'upsert', or 'delete'."})

    @mcp.tool(
        name="list-agent-capabilities",
        annotations=tool_annotations(
            {
                "title": "List Agent Capabilities",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_agent_capabilities_tool(limit: int = 50) -> str:
        """List all skill capabilities by scanning SKILL.md files.

        Discovers skills across all plugin bundles and extracts
        name, description, and capabilities metadata.

        Args:
            limit: Maximum number of skills to return (default: 50)

        Returns:
            str: JSON with agent capabilities list
        """
        metrics.track_tool("list_agent_capabilities", skill="ai")

        from src.plugins.skill_discovery import discover_all_skills

        project_root = Path(__file__).resolve().parents[5]
        capabilities: list[dict] = []

        for record in sorted(discover_all_skills(), key=lambda item: item.name):
            skill_dir = record.path
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"

            name = record.name or skill_dir.name
            description = record.description or ""
            caps = list(record.capabilities[:10]) if record.capabilities else []
            has_dashboard = (skill_dir / "augur" / "dashboard").is_dir()
            frontmatter = _read_skill_frontmatter(skill_md) if skill_md.exists() else {}
            dashboard_path = _build_skill_dashboard_path(skill_dir.name, frontmatter, has_dashboard)

            if isinstance(frontmatter.get("name"), str) and frontmatter.get("name"):
                name = frontmatter["name"]

            if not description and skill_md.exists():
                try:
                    content = skill_md.read_text(encoding="utf-8")
                    lines = content.split("\n")
                    for line in lines[1:]:
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("---"):
                            description = line
                            break
                except Exception:
                    pass

            capabilities.append({
                "skillId": skill_dir.name,
                "name": name,
                "bundle": record.plugin or record.layer or "augur",
                "description": description,
                "capabilities": caps,
                "hasDashboard": has_dashboard,
                "dashboardPath": dashboard_path,
                "path": os.path.relpath(skill_dir, project_root),
            })

        return json.dumps(
            {"data": capabilities[:limit], "count": len(capabilities)},
            indent=2,
        )

    logger.info("AI MCP tools registered successfully")


def register_subcommands(subparsers: Any) -> None:
    """Register `aug sync <artifact>` (ADR-260 CLI subcommand surface).

    Regenerating agent/client artifacts lives in `skills.ai.scripts.sync_agents`,
    invoked today as `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync <artifact>`.
    Agents repeatedly reach for the shorter `aug sync` (it is also a recurring
    `cli-tool-unreachable` friction finding), so expose it here. The handler
    shells out to the canonical module so its parser/behavior stays the single
    source of truth.
    """
    parser = subparsers.add_parser(
        "sync",
        help="Regenerate Augur agent/client artifacts (commands | agents | all | ...)",
    )
    parser.add_argument(
        "artifact",
        nargs="?",
        default="all",
        help="Artifact family to sync (default: all)",
    )
    parser.add_argument(
        "client",
        nargs="?",
        default="all",
        help="Optional client filter (default: all)",
    )
    parser.set_defaults(func=_run_sync_cli)


def _run_sync_cli(args: Any, remaining: Any) -> int:
    import os
    import subprocess
    import sys as _sys
    from pathlib import Path

    here = Path(__file__).resolve()
    shared_vault = here.parents[4]
    project_root = shared_vault.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p
        for p in (
            str(project_root),
            str(shared_vault),
            str(project_root / "src" / "mcp"),
            env.get("PYTHONPATH", ""),
        )
        if p
    )
    cmd = [
        _sys.executable,
        "-m",
        "skills.ai.scripts.sync_agents",
        "sync",
        args.artifact,
        args.client,
    ]
    cmd += list(remaining or [])
    return subprocess.call(cmd, cwd=str(project_root), env=env)


__all__ = ["register_tools", "register_subcommands"]
