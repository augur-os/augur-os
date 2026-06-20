"""
MCP Management tool implementations.

These tools handle MCP server configuration, diagnostics, and context switching.
"""

import asyncio
import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from src.config.paths import get_project_root
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.config import get_config_dir
from src.mcp.augur_shared.logging import get_entity_logger
from src.mcp.augur_shared.safe_subprocess import safe_run as subprocess_run  # nosec B404

from .mcp_diagnostics import build_mcp_diagnostics_summary, count_api_routes

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

# Project root for script paths
# mcp_management.py -> infrastructure -> augur_mcp -> mcp -> src -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


# =============================================================================
# Pydantic Input Models
# =============================================================================


class GetMcpDiagnosticsInput(BaseModel):
    """Input for get-mcp-diagnostics MCP tool."""

    model_config = ConfigDict(extra="forbid")
    include_processes: bool = Field(True, description="Include running MCP process information")
    include_configs: bool = Field(True, description="Include IDE configuration status")


class GetApiRouteStatsInput(BaseModel):
    """Input for get-api-route-stats MCP tool."""

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Tool Registration
# =============================================================================


def register_mcp_management_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register MCP Management tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="test-mcp-connection",
        annotations=tool_annotations(
            {
                "title": "Test MCP Connection",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def test_mcp_connection_tool() -> str:
        """Test MCP server connection for onboarding/debugging.

        Returns:
            str: JSON with connection status
        """
        metrics.track_tool("test_mcp_connection")

        try:
            # Simple ping test - if we got here, connection is working
            return json.dumps(
                {
                    "ok": True,
                    "success": True,
                    "message": "MCP server connection successful",
                    "timestamp": datetime.now().isoformat(),
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"MCP connection test failed: {e}", exc_info=True)
            return json.dumps(
                {"ok": False, "success": False, "message": "MCP server connection test failed", "error": str(e)}
            )

    @mcp.tool(
        name="list-mcp-tools",
        annotations=tool_annotations(
            {
                "title": "List MCP Tools",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_mcp_tools_tool(action: str = "list", include_disabled: bool = True) -> str:
        """List all available MCP tools or get summary.

        Args:
            action: 'list' for simple list, 'summary' for full detailed config
            include_disabled: Whether to include disabled tools

        Returns:
            str: JSON with tools list or summary object
        """
        metrics.track_tool("list_mcp_tools")

        try:
            # ADR-260: Try assembled_tool_config.json first, fall back to YAML
            config_path = get_config_dir() / "dashboard" / "generated" / "assembled_tool_config.json"
            if not config_path.exists():
                config_path = get_config_dir() / "dashboard" / "mcp_tool_groups.yaml"
            if not config_path.exists():
                config_path = get_config_dir() / "mcp_tool_groups.yaml"
            tool_groups: dict[str, list[str]] = {}
            core_tools: list[str] = []

            if config_path.exists():
                with open(config_path) as f:
                    if config_path.suffix == ".json":
                        config = json.load(f) or {}
                    else:
                        config = yaml.safe_load(f) or {}
                    if not isinstance(config, dict):
                        config = {}
                    tool_groups = config.get("tool_groups", {})
                    if not isinstance(tool_groups, dict):
                        tool_groups = {}
                    core_tools = config.get("core_tools", [])
                    if not isinstance(core_tools, list):
                        core_tools = []

            # Build tools list and map from YAML config
            tools_list: list[dict[str, Any]] = []
            tools_map: dict[str, dict[str, Any]] = {}
            categories: dict[str, dict[str, Any]] = {}

            # Process core_tools first (simple list of tool names)
            for tool_name in core_tools:
                if not tool_name or not isinstance(tool_name, str):
                    continue
                tool_info = {
                    "name": tool_name,
                    "enabled": True,
                    "category": "core",
                }
                tools_list.append(tool_info)
                tools_map[tool_name] = {"enabled": True, "category": "core"}

            # Process tool_groups (each group is a list of tool names)
            for group_name, group_tools in tool_groups.items():
                category = _map_group_to_category(group_name)

                # group_tools is a list of tool name strings
                if not isinstance(group_tools, list):
                    continue

                for tool_name in group_tools:
                    if not tool_name or not isinstance(tool_name, str):
                        continue
                    # Handle tool names with comments (e.g., "search-documents          # RAG search")
                    tool_name = tool_name.split("#")[0].strip() if "#" in str(tool_name) else tool_name
                    if not tool_name:
                        continue
                    # Skip tools already added from core_tools to avoid duplicates
                    if tool_name in tools_map:
                        continue
                    tool_info = {
                        "name": tool_name,
                        "enabled": True,
                        "category": category,
                    }
                    tools_list.append(tool_info)
                    tools_map[tool_name] = {"enabled": True, "category": category}

            # Build categories for summary
            for tool_name, tool_data in tools_map.items():
                cat = tool_data["category"]
                if cat not in categories:
                    categories[cat] = {
                        "enabled": True,
                        "description": _get_category_description(cat),
                        "recommended": cat in ["core", "context"],
                        "tools_total": 0,
                        "tools_enabled": 0,
                        "tools": [],
                    }
                categories[cat]["tools_total"] += 1
                categories[cat]["tools_enabled"] += 1
                categories[cat]["tools"].append(tool_name)

            if action == "summary":
                # Return rich summary structure expected by McpConfigPage
                return json.dumps(
                    {
                        "version": "1.0.0",
                        "last_updated": datetime.now().isoformat(),
                        "active_preset": "auto",
                        "total_tools": len(tools_list),
                        "enabled_tools": len(tools_list),
                        "presets": {
                            "minimal": {"description": "Essential core tools only", "categories": ["core"]},
                            "standard": {
                                "description": "Standard tools for most tasks",
                                "categories": ["core", "context"],
                            },
                            "full": {
                                "description": "All available tools enabled",
                                "categories": list(categories.keys()),
                            },
                            "auto": {"description": "Auto-configured based on usage", "categories": []},
                        },
                        "categories": (
                            categories
                            if categories
                            else {
                                "core": {
                                    "enabled": True,
                                    "description": "Core system tools",
                                    "recommended": True,
                                    "tools_total": len(tools_list),
                                    "tools_enabled": len(tools_list),
                                    "tools": list(tools_map.keys()),
                                }
                            }
                        ),
                        "tools": tools_list,
                        "tools_config": tools_map,
                    },
                    indent=2,
                )

            return json.dumps({"tools": tools_list}, indent=2)

        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}", exc_info=True)
            return json.dumps({"error": str(e), "tools": []})


def _map_group_to_category(group_name: str) -> str:
    """Map YAML group names to UI category names."""
    group_mapping = {
        "BRAIN_DATA": "context",
        "BRAIN_BUGS": "diagnostics",
        "BRAIN_INTEL": "context",
        "WORKFORCE_CHAINS": "execution",
        "WORKFORCE_SELF_UPDATE": "self-update",
        "SETTINGS_MGMT": "settings",
        "core_tools": "core",
    }
    return group_mapping.get(group_name, "core")


def _categorize_tool(tool_name: str) -> str:
    """Categorize a tool based on its name."""
    name_lower = tool_name.lower()

    # Domain tools
    if any(x in name_lower for x in ["skill", "chain", "workflow", "sprint"]):
        return "execution"
    if any(x in name_lower for x in ["agent", "route", "ide", "prompt"]):
        return "agents"
    if any(x in name_lower for x in ["doctor", "health", "symptom", "medication"]):
        return "domain"
    if any(x in name_lower for x in ["interview", "job", "career", "company"]):
        return "domain"
    # ADR-Track-3a: dynamic vault-skill heuristic instead of hardcoded names.
    try:
        from src.mcp.augur_shared.skill_registry import is_known_skill

        for token in name_lower.split("-"):
            if token and is_known_skill(token):
                return "domain"
    except Exception:
        pass
    if any(x in name_lower for x in ["recipe", "reading"]):
        return "domain"

    # Infrastructure tools
    if any(x in name_lower for x in ["mcp", "config", "context", "switch"]):
        return "context"
    if any(x in name_lower for x in ["rag", "memory", "document", "search"]):
        return "context"
    if any(x in name_lower for x in ["job", "task", "background", "queue"]):
        return "background-jobs"
    if any(x in name_lower for x in ["diagnostic", "test", "log", "metric"]):
        return "diagnostics"
    if any(x in name_lower for x in ["rollback", "undo", "revert"]):
        return "rollback"
    if any(x in name_lower for x in ["train", "learn", "teach"]):
        return "training"
    if any(x in name_lower for x in ["self-update", "update", "upgrade"]):
        return "self-update"

    return "core"


def _get_category_description(category: str) -> str:
    """Get description for a tool category."""
    descriptions = {
        "core": "Core system tools for basic operations",
        "context": "Context and memory management tools",
        "execution": "Workflow and skill execution tools",
        "agents": "Agent management and IDE integration",
        "domain": "Domain-specific tools tied to user-facing skills",
        "background-jobs": "Background job and task management",
        "diagnostics": "System diagnostics and monitoring",
        "rollback": "Undo and rollback operations",
        "training": "Learning and training tools",
        "self-update": "Self-update and maintenance tools",
        "settings": "Settings and configuration management",
    }
    return descriptions.get(category, f"{category.title()} tools")


def register_mcp_management_tools_extended(
    mcp: "FastMCP",
    mcp_tool_interceptor,
    metrics,
) -> None:
    """Register additional MCP Management tools (configure, context switching, diagnostics)."""

    @mcp.tool(
        name="configure-mcp-server",
        annotations=tool_annotations(
            {
                "title": "Configure MCP Server",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def configure_mcp_server_tool(ide: str = "cursor") -> str:
        """Configure MCP server for IDE.

        Args:
            ide: IDE name (default: cursor)

        Returns:
            str: JSON with configuration status
        """
        metrics.track_tool("configure_mcp_server")

        try:
            from src.config.paths import get_project_brain_skills_dir
            from src.mcp.augur_shared.config import get_project_root

            # Run setup script
            result = await asyncio.to_thread(
                subprocess_run,  # nosec B603
                [
                    "python3",
                    str(get_project_brain_skills_dir(PROJECT_ROOT) / "ai" / "scripts" / "setup_cursor_mcp.py"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "AUGUR_ROOT": str(get_project_root())},
            )

            if result.returncode != 0 and result.stderr and "Warning" not in result.stderr:
                return json.dumps(
                    {"ok": False, "success": False, "error": result.stderr or "Failed to configure MCP server"}
                )

            return json.dumps(
                {"ok": True, "success": True, "message": f"MCP server configured for {ide}", "ide": ide}, indent=2
            )

        except Exception as e:
            logger.error(f"Failed to configure MCP: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e), "statusCode": 200})

    @mcp.tool(
        name="switch-mcp-context",
        annotations=tool_annotations(
            {
                "title": "Switch MCP Context",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def switch_mcp_context_tool(current_page: str, preloaded: bool = False) -> str:
        """Switch active MCP tools based on dashboard page context.

        Args:
            current_page: Current dashboard page (e.g., "/brain", "/workforce")
            preloaded: Whether tools were preloaded on hover

        Returns:
            str: JSON with switch results
        """
        metrics.track_tool("switch_mcp_context")

        try:
            from src.mcp.augur_shared.context_manager import get_context_manager

            # Get context manager instance
            ctx_mgr = get_context_manager(mcp)

            # Perform context switch
            result = await ctx_mgr.switch_context(target_page=current_page, preloaded=preloaded)

            logger.info(f"Context switched to {current_page}", extra={"result": result})

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Context switch failed: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e), "current_page": current_page, "statusCode": 200})

    @mcp.tool(
        name="preload-mcp-context",
        annotations=tool_annotations(
            {
                "title": "Preload MCP Context",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def preload_mcp_context_tool(target_page: str) -> str:
        """Preload tools for a page (called on hover).

        Args:
            target_page: Page to preload tools for

        Returns:
            str: JSON with preload status
        """
        metrics.track_tool("preload_mcp_context")

        try:
            from src.mcp.augur_shared.context_manager import get_context_manager

            # Get context manager instance
            ctx_mgr = get_context_manager(mcp)

            # Preload context
            await ctx_mgr.preload_context(target_page)

            result = {"success": True, "target_page": target_page, "message": "Context preloaded"}

            logger.debug(f"Context preloaded for {target_page}")

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Context preload failed: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e), "target_page": target_page, "statusCode": 200})

    @mcp.tool(
        name="get-mcp-context-stats",
        annotations=tool_annotations(
            {
                "title": "Get MCP Context Stats",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_mcp_context_stats_tool() -> str:
        """Get context manager performance statistics.

        Returns:
            str: JSON with performance metrics
        """
        metrics.track_tool("get_mcp_context_stats")

        try:
            from src.mcp.augur_shared.context_manager import get_context_manager

            # Get context manager instance
            ctx_mgr = get_context_manager(mcp)

            # Get stats
            stats = ctx_mgr.get_stats()

            return json.dumps(stats, indent=2)

        except Exception as e:
            logger.error(f"Failed to get context stats: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="discover-augur",
        annotations=tool_annotations(
            {
                "title": "Discover Augur",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def discover_augur(
        tier: str | None = None,
        hub: str | None = None,
    ) -> str:
        """Discover Augur capabilities, tools, and current focus context.

        Returns a structured manifest of skills, hubs, and tools scoped to the
        inferred or explicit hub. Replaces /focus — context is inferred from
        signals (dashboard page, CLI usage, git) automatically.

        Args:
            tier: Filter tools by tier (public, standard, internal). Default: all.
            hub: Explicit hub override. Default: inferred from signals.
        """
        metrics.track_tool("discover_augur", hub=hub, tier=tier)

        try:
            from src.mcp.augur_framework.tools.domain.discovery import assemble_manifest
            from src.mcp.augur_shared.config import get_runtime_dir

            runtime_dir = get_runtime_dir()

            # Use per-session focus state when available (ADR-254 §1.2)
            session_id = f"mcp-{os.getpid()}"
            manifest = assemble_manifest(
                runtime_dir,
                hub=hub,
                tier=tier,
                session_id=session_id,
            )
            return json.dumps(manifest, indent=2, default=str)

        except Exception as e:
            logger.error(f"discover-augur failed: {e}", exc_info=True)
            return json.dumps({"error": str(e), "statusCode": 200})

    @mcp.tool(
        name="get-mcp-diagnostics",
        annotations=tool_annotations(
            {
                "title": "Get MCP Diagnostics",
                "readOnlyHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_mcp_diagnostics(
        # MCP tool no-arg input model default is introspected by the SDK.
        params: GetMcpDiagnosticsInput = GetMcpDiagnosticsInput(),  # noqa: B008
    ) -> str:
        """Get MCP runtime diagnostics and health status.

        Returns information about MCP server configuration, connected clients,
        and process status. Useful for agents to self-diagnose connection issues.
        """
        try:
            diagnostics = await asyncio.to_thread(
                build_mcp_diagnostics_summary,
                include_processes=params.include_processes,
                include_configs=params.include_configs,
                project_root=Path(get_project_root()).resolve(),
            )
            return json.dumps(diagnostics, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool(
        name="get-api-route-stats",
        annotations=tool_annotations(
            {
                "title": "Get API Route Stats",
                "readOnlyHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_api_route_stats(
        params: GetApiRouteStatsInput = GetApiRouteStatsInput(),  # noqa: B008 — MCP tool no-arg input model default is introspected by the SDK
    ) -> str:
        """Return lightweight API route statistics for browse/system views."""
        del params
        try:
            return json.dumps(
                count_api_routes(Path(get_project_root()).resolve()),
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)


def register_all_mcp_management_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor,
    metrics,
) -> None:
    """Register all MCP Management tools (main entry point)."""
    register_mcp_management_tools(mcp, mcp_tool_interceptor, metrics)
    register_mcp_management_tools_extended(mcp, mcp_tool_interceptor, metrics)


__all__ = [
    "register_mcp_management_tools",
    "register_mcp_management_tools_extended",
    "register_all_mcp_management_tools",
]
