"""Settings tools - scope-based config read/write for dashboard API routes.

Dashboard API routes call these tools with a ``scope`` parameter that maps
to a specific config/state file.  This replaces the broken pattern of
calling ``file-write`` with scope params (file-write expects path + content).

ADR-457: Dedicated MCP Tools.

## Tools

- ``set-config``: Write config data by scope (layout presets, nav order, LLM, etc.)
- ``get-settings``: Read config data by scope

Split into submodules by domain:
- ``_helpers``   — path resolution and atomic file I/O
- ``dashboard``  — layout, nav, preferences, LLM config, UI state
- ``schedules``  — schedule/cron CRUD
- ``bridge``     — AI bridge connections, scan, refresh
- ``remote``     — remote provider execute, scan, audit, usage, OAuth
- ``plugins``    — plugin/skill install, export, import, onboarding, wizard
- ``system``     — telemetry, self-heal, insights, feedback, MCP usage
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger

# Re-export helpers so tests can monkeypatch settings internals through the
# canonical infrastructure settings module.
from ._helpers import (
    _get_config_dir,
    _get_project_root,
    _get_state_dir,
    _read_json,
    _read_yaml,
    _write_json,
    _write_yaml,
)
from .bridge import (
    _handle_bridge_connection_create,
    _handle_bridge_connection_delete,
    _handle_bridge_refresh,
    _handle_bridge_scan,
    _read_bridge_connections,
    _read_bridge_summary,
)
from .dashboard import (
    _handle_cli_upload,
    _handle_dashboard_remove,
    _handle_dashboard_toggle,
    _handle_default_cli,
    _handle_focus_state,
    _handle_hub_notes,
    _handle_layout_presets,
    _handle_layout_reset,
    _handle_llm_config,
    _handle_llm_config_write,
    _handle_nav_order_update,
    _handle_preferences,
    _handle_skill_nav_toggle,
    _handle_skill_set_enabled,
    _handle_skill_uninstall,
    _handle_usage_stats,
    _read_activity_summary,
    _read_dashboard_groups,
    _read_debug_routes,
    _read_default_cli,
    _read_hub_notes,
    _read_layout_presets,
    _read_layout_snapshot,
    _read_llm_config,
    _read_nav_order,
    _read_plugin_data,
    _read_preferences,
    _read_skill_nav,
    _read_usage_stats,
    _read_workflows,
)
from .plugins import (
    _handle_analyze_placement,
    _handle_onboarding_complete,
    _handle_onboarding_test,
    _handle_plugin_dependencies,
    _handle_plugin_export,
    _handle_plugin_install,
    _handle_plugin_uninstall,
    _handle_skill_export,
    _handle_skill_import,
    _handle_wizard_sources_combine,
    _handle_wizard_sources_extract,
    _read_analyze_placement,
    _read_plugin_dependencies,
    _read_plugin_dependency_tree,
)
from .remote import (
    _handle_remote_audit_clear,
    _handle_remote_execute,
    _handle_remote_oauth_callback,
    _handle_remote_provider_delete,
    _handle_remote_provider_test,
    _handle_remote_provider_update,
    _handle_remote_providers_update,
    _handle_remote_scan,
    _handle_remote_usage_record,
    _read_remote_audit,
    _read_remote_provider,
    _read_remote_providers,
    _read_remote_scan,
    _read_remote_usage,
)
from .schedules import (
    _handle_schedule_create,
    _handle_schedule_delete,
    _handle_schedule_run_now,
    _handle_schedule_update,
    _read_schedule_history,
    _read_schedules,
)
from .system import (
    _handle_agent_rules_sync,
    _handle_agent_telemetry_record,
    _handle_insights_accept,
    _handle_insights_dismiss,
    _handle_mcp_tool_usage,
    _handle_prepare_execution,
    _handle_prepare_task,
    _handle_prompt_feedback,
    _handle_self_heal_event,
    _read_adaptive_growth_backlogs,
    _read_adaptive_growth_summary,
    _read_insights_context,
    _read_mcp_tool_usage,
    _read_prompt_feedback,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp.settings")


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class SetConfigInput(BaseModel):
    """Input for the set-config tool.

    The ``scope`` field determines which config file is written.
    Additional scope-specific fields are passed through via ``extra='allow'``.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    scope: str = Field(
        ...,
        description=(
            "Config scope to write. One of: preferences, layout-presets, layout-reset, "
            "nav-order-update, skill-nav-toggle, dashboard-toggle, dashboard-remove, "
            "default-cli, llm-config, llm-config-write, schedule-create, schedule-update, "
            "schedule-delete, bridge-connection-create, bridge-connection-delete, cli-upload, "
            "agent-rules-sync, prompt-feedback, bridge-scan, bridge-refresh, "
            "insights-dismiss, insights-accept, mcp-tool-usage, "
            "remote-execute, remote-scan, remote-audit-clear, remote-usage-record, "
            "remote-providers-update, remote-provider-update, remote-provider-delete, "
            "remote-provider-test, remote-oauth-callback"
        ),
        min_length=1,
    )
    key: str | None = Field(default=None, description="Config key (for key-value scopes like preferences)")
    value: Any = Field(
        default=None,
        description="Config value (for key-value scopes like preferences)",
        json_schema_extra={
            "anyOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "boolean"},
                {"type": "object"},
                {"type": "array"},
                {"type": "null"},
            ]
        },
    )


class GetSettingsInput(BaseModel):
    """Input for the get-settings tool.

    The ``scope`` field determines which config file is read.
    Additional scope-specific fields are passed through via ``extra='allow'``.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    scope: str = Field(
        ...,
        description=(
            "Config scope to read. One of: preferences, layout-presets, nav-order, "
            "nav-visibility, skill-nav, dashboard-groups, default-cli, llm-config, llm, "
            "schedules, schedule-history, bridge-connections, prompt-feedback, "
            "bridge-summary, insights-context, debug-routes, mcp-tool-usage, "
            "remote-providers, remote-provider, remote-usage, remote-audit, remote-scan"
        ),
        min_length=1,
    )
    key: str | None = Field(default=None, description="Optional key to filter results")


# ---------------------------------------------------------------------------
# Scope dispatch tables
# ---------------------------------------------------------------------------

_WRITE_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    # dashboard
    "preferences": _handle_preferences,
    "layout-presets": _handle_layout_presets,
    "layout-reset": _handle_layout_reset,
    "nav-order-update": _handle_nav_order_update,
    "skill-nav-toggle": _handle_skill_nav_toggle,
    "dashboard-toggle": _handle_dashboard_toggle,
    "dashboard-remove": _handle_dashboard_remove,
    "default-cli": _handle_default_cli,
    "llm-config": _handle_llm_config,
    "llm-config-write": _handle_llm_config_write,
    "hub-notes": _handle_hub_notes,
    "usage-stats": _handle_usage_stats,
    "focus-state": _handle_focus_state,
    "skill-set-enabled": _handle_skill_set_enabled,
    "skill-uninstall": _handle_skill_uninstall,
    "cli-upload": _handle_cli_upload,
    # schedules
    "schedule-create": _handle_schedule_create,
    "schedule-update": _handle_schedule_update,
    "schedule-delete": _handle_schedule_delete,
    "schedule-run-now": _handle_schedule_run_now,
    # bridge
    "bridge-connection-create": _handle_bridge_connection_create,
    "bridge-connection-delete": _handle_bridge_connection_delete,
    "bridge-scan": _handle_bridge_scan,
    "bridge-refresh": _handle_bridge_refresh,
    # remote
    "remote-execute": _handle_remote_execute,
    "remote-scan": _handle_remote_scan,
    "remote-audit-clear": _handle_remote_audit_clear,
    "remote-usage-record": _handle_remote_usage_record,
    "remote-providers-update": _handle_remote_providers_update,
    "remote-provider-update": _handle_remote_provider_update,
    "remote-provider-delete": _handle_remote_provider_delete,
    "remote-provider-test": _handle_remote_provider_test,
    "remote-oauth-callback": _handle_remote_oauth_callback,
    # plugins / skills / wizard
    "plugin-install": _handle_plugin_install,
    "plugin-uninstall": _handle_plugin_uninstall,
    "plugin-export": _handle_plugin_export,
    "plugin-dependencies": _handle_plugin_dependencies,
    "skill-import": _handle_skill_import,
    "skill-export": _handle_skill_export,
    "analyze-placement": _handle_analyze_placement,
    "onboarding-complete": _handle_onboarding_complete,
    "onboarding-test": _handle_onboarding_test,
    "wizard-sources-combine": _handle_wizard_sources_combine,
    "wizard-sources-extract": _handle_wizard_sources_extract,
    # system
    "agent-telemetry-record": _handle_agent_telemetry_record,
    "self-heal-event": _handle_self_heal_event,
    "prepare-execution": _handle_prepare_execution,
    "prepare-task": _handle_prepare_task,
    "agent-rules-sync": _handle_agent_rules_sync,
    "prompt-feedback": _handle_prompt_feedback,
    "insights-dismiss": _handle_insights_dismiss,
    "insights-accept": _handle_insights_accept,
    "mcp-tool-usage": _handle_mcp_tool_usage,
}

_READ_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    # dashboard
    "preferences": _read_preferences,
    "layout-presets": _read_layout_presets,
    "nav-order": _read_nav_order,
    "nav-visibility": _read_skill_nav,
    "skill-nav": _read_skill_nav,
    "dashboard-groups": _read_dashboard_groups,
    "default-cli": _read_default_cli,
    "llm-config": _read_llm_config,
    "llm": _read_llm_config,
    "hub-notes": _read_hub_notes,
    "usage-stats": _read_usage_stats,
    "activity-summary": _read_activity_summary,
    "layout-snapshot": _read_layout_snapshot,
    "workflows": _read_workflows,
    "plugin-data": _read_plugin_data,
    "debug-routes": _read_debug_routes,
    # schedules
    "schedules": _read_schedules,
    "schedule-history": _read_schedule_history,
    # bridge
    "bridge-connections": _read_bridge_connections,
    "bridge-summary": _read_bridge_summary,
    # remote
    "remote-providers": _read_remote_providers,
    "remote-provider": _read_remote_provider,
    "remote-usage": _read_remote_usage,
    "remote-audit": _read_remote_audit,
    "remote-scan": _read_remote_scan,
    # plugins / skills / wizard
    "plugin-dependencies": _read_plugin_dependencies,
    "plugin-dependency-tree": _read_plugin_dependency_tree,
    "analyze-placement": _read_analyze_placement,
    # system
    "prompt-feedback": _read_prompt_feedback,
    "insights-context": _read_insights_context,
    "mcp-tool-usage": _read_mcp_tool_usage,
    "adaptive-growth-summary": _read_adaptive_growth_summary,
    "adaptive-growth-backlogs": _read_adaptive_growth_backlogs,
}


# ---------------------------------------------------------------------------
# Public implementation functions
# ---------------------------------------------------------------------------


async def set_config_impl(params: SetConfigInput | dict[str, Any]) -> str:
    """Write config data identified by *scope*.

    Args:
        params: SetConfigInput or dict containing ``scope`` (required)
                and scope-specific fields.

    Returns:
        JSON string with result.
    """
    if isinstance(params, BaseModel):
        all_params = params.model_dump()
    else:
        all_params = params

    scope = all_params.get("scope")
    if not scope:
        return json.dumps({"success": False, "error": "Missing required 'scope' parameter"})

    handler = _WRITE_HANDLERS.get(scope)
    if handler is None:
        return json.dumps(
            {
                "success": False,
                "error": f"Unknown scope: '{scope}'",
                "available_scopes": sorted(_WRITE_HANDLERS.keys()),
            }
        )

    try:
        result = handler(all_params)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error("set-config scope=%s failed: %s", scope, e, exc_info=True)
        return json.dumps({"success": False, "error": str(e)})


async def get_settings_impl(params: GetSettingsInput | dict[str, Any]) -> str:
    """Read config data identified by *scope*.

    Args:
        params: GetSettingsInput or dict containing ``scope`` (required)
                and optional filtering fields.

    Returns:
        JSON string with settings data.
    """
    if isinstance(params, BaseModel):
        all_params = params.model_dump()
    else:
        all_params = params

    scope = all_params.get("scope")
    if not scope:
        return json.dumps({"success": False, "error": "Missing required 'scope' parameter"})

    handler = _READ_HANDLERS.get(scope)
    if handler is None:
        return json.dumps(
            {
                "success": False,
                "error": f"Unknown scope: '{scope}'",
                "available_scopes": sorted(_READ_HANDLERS.keys()),
            }
        )

    try:
        result = handler(all_params)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error("get-settings scope=%s failed: %s", scope, e, exc_info=True)
        return json.dumps({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_settings_tools(
    mcp: FastMCP,
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """Register set-config and get-settings tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="set-config",
        annotations=tool_annotations(
            {
                "title": "Set Config by Scope",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def set_config_tool(params: SetConfigInput) -> str:
        """Write configuration data by scope.

        Handles dashboard settings writes: layout presets, nav ordering,
        skill visibility, LLM config, schedules, bridge connections, etc.

        The ``scope`` parameter determines which config file is targeted.
        Additional fields are scope-specific (e.g. ``preset`` for layout-presets,
        ``config`` for llm-config).

        Args:
            params: SetConfigInput with scope and scope-specific fields

        Returns:
            str: JSON with write result
        """
        metrics.track_tool("set_config")
        return await set_config_impl(params)

    @mcp.tool(
        name="get-settings",
        annotations=tool_annotations(
            {
                "title": "Get Settings by Scope",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_settings_tool(params: GetSettingsInput) -> str:
        """Read configuration/settings data by scope.

        Handles dashboard settings reads: layout presets, nav order,
        skill visibility, LLM config, schedules, bridge connections, etc.

        The ``scope`` parameter determines which config file is read.

        Args:
            params: GetSettingsInput with scope and optional key

        Returns:
            str: JSON with settings data
        """
        metrics.track_tool("get_settings")
        return await get_settings_impl(params)


__all__ = [
    "SetConfigInput",
    "GetSettingsInput",
    "set_config_impl",
    "get_settings_impl",
    "register_settings_tools",
    # Re-exported helpers for test monkeypatching of settings internals.
    "_get_config_dir",
    "_get_project_root",
    "_get_state_dir",
    "_read_json",
    "_read_yaml",
    "_write_json",
    "_write_yaml",
]
