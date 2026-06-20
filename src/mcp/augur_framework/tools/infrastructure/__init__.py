"""
Infrastructure/DevOps tools - document operations, skill generation, auditing.

This module contains tools for system maintenance, document indexing, and DevOps.
These tools support the operational infrastructure of Augur.

## Migrated Tools

### Background Job Management (MIGRATED)
- `get-job-status`: Get status of background job
- `cancel-job`: Cancel a running job
- `list-jobs`: List active background jobs

### MCP Management (MIGRATED)
- `test-mcp-connection`: Test MCP server connection
- `list-mcp-tools`: List all available MCP tools
- `configure-mcp-server`: Configure MCP server for IDE
- `switch-mcp-context`: Switch active MCP tools based on page context
- `preload-mcp-context`: Preload tools for a page
- `get-mcp-context-stats`: Get context manager performance stats
- `get-mcp-diagnostics`: Get MCP runtime diagnostics
- `get-api-route-stats`: Get dashboard API route summary stats

### Performance & Dashboard (MIGRATED)
- `get-system-health`: Get system health metrics
- `get-daily-summary`: Get daily usage summary
- `get-factory-status`: Get factory processing status
- `get-performance-metrics`: Get page performance telemetry
- `save-performance-metric`: Save a page performance metric
- `get-dashboard-data`: Get aggregated dashboard data
- `get-dashboard-groups`: Get dashboard groups configuration

### Configuration & Features (MIGRATED)
- `get-features`: Get feature flags configuration
- `get-chat-session`: Get current chat session state
- `update-chat-session`: Update chat session state
- `clear-system-cache`: Clear Next.js system cache
- `get-intelligence-stats`: Get LLM usage statistics

### Workflow Tools (MIGRATED)
- `get-focused-tools`: Get context-aware tool selection
- `query-audit-log`: Query or log security audit events
- `generate-skill`: Generate a new Augur skill

### Document Operations (MIGRATED)
- `sync-bugs`: Sync bugs from local database to GitHub issues

### File Access Tools
- `file-read`: Read file content with pagination (supports binary mode)
- `file-write`: Write file with atomic writes and backup
- `file-write-binary`: Write binary content (base64-encoded) with atomic writes
- `file-list`: List directory contents with glob patterns
- `file-search`: Search file contents with regex
- `file-read-multi`: Batch read multiple files in parallel
- `file-info`: Get file/directory metadata
- `resolve-asset-path`: Resolve skill asset directory with subfolder suggestion

### Settings Tools (ADR-457)
- `set-config`: Scope-based config writes (layout, nav, LLM, schedules, etc.)
- `get-settings`: Scope-based config reads
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_infrastructure_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register infrastructure tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """
    from ..internal.template_resolver import register_template_tools
    from .artifact_reconcile import register_artifact_reconcile_tools
    from .artifacts import register_artifacts_tools
    from .auto_index_notes import register_auto_index_notes_tools
    from .browse import register_browse_tools
    from .config import register_config_tools
    from .documents import register_document_tools
    from .files import register_file_tools
    from .harness import register_harness_tools
    from .jobs import register_job_tools
    from .local_backends import (
        GetAirplaneLaunchOverridesInput,
        GetLocalBackendStatusInput,
        ListOllamaIntegrationsInput,
        ResolveClientInput,
        SetClientOverrideInput,
        ToggleAirplaneModeInput,
        get_airplane_launch_overrides_impl,
        get_local_backend_status_impl,
        list_available_clients_impl,
        list_ollama_integrations_impl,
        resolve_client_impl,
        set_client_override_impl,
        toggle_airplane_mode_impl,
    )
    from .mcp_management import (
        register_mcp_management_tools,
        register_mcp_management_tools_extended,
    )
    from .paths import register_path_tools
    from .performance import register_performance_tools
    from .pins import register_pin_tools
    from .session_owners import (
        SessionClaimInput,
        SessionReleaseInput,
        SessionStatusInput,
        session_claim_impl,
        session_release_impl,
        session_status_impl,
    )
    from .settings import register_settings_tools
    from .system import register_system_tools
    from .workflow import register_workflow_tools

    # Register job management tools
    register_job_tools(mcp, mcp_tool_interceptor, metrics)

    # Register system operations tools
    register_system_tools(mcp, mcp_tool_interceptor, metrics)

    # Register MCP management tools
    register_mcp_management_tools(mcp, mcp_tool_interceptor, metrics)
    register_mcp_management_tools_extended(mcp, mcp_tool_interceptor, metrics)

    # Register performance and dashboard tools
    register_performance_tools(mcp, mcp_tool_interceptor, metrics)

    # Register configuration and features tools
    register_config_tools(mcp, mcp_tool_interceptor, metrics)

    # Register workflow tools
    register_workflow_tools(mcp, mcp_tool_interceptor, metrics)

    # Register document operations tools
    register_document_tools(mcp, mcp_tool_interceptor, metrics)

    # Register file access tools
    register_file_tools(mcp, mcp_tool_interceptor, metrics)

    # Register path configuration tools
    register_path_tools(mcp, mcp_tool_interceptor, metrics)

    # Register settings tools (scope-based config read/write — ADR-457)
    register_settings_tools(mcp, mcp_tool_interceptor, metrics)

    # Register browse tools (file actions: reveal, open)
    register_browse_tools(mcp, mcp_tool_interceptor, metrics)

    # Register Brain Harness control-plane tools (ADR-552)
    register_harness_tools(mcp, mcp_tool_interceptor, metrics)

    # Register skill-specific operator surfaces
    register_auto_index_notes_tools(mcp, mcp_tool_interceptor, metrics)

    # Register template resolution tools (ADR-450)
    register_template_tools(mcp, mcp_tool_interceptor, metrics)

    # Register HTML artifact, session artifact reconcile, and global pin tools
    # (ADR-723; /keep artifact reconcile spec 2026-06-11)
    register_artifacts_tools(mcp, mcp_tool_interceptor, metrics)
    register_artifact_reconcile_tools(mcp, mcp_tool_interceptor, metrics)
    register_pin_tools(mcp, mcp_tool_interceptor, metrics)

    # Register local backend status tool
    from src.mcp.augur_shared.annotations import tool_annotations

    @mcp.tool(
        name="get-local-backend-status",
        annotations=tool_annotations(
            {
                "title": "Get Local Backend Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_local_backend_status() -> str:
        """Check local LLM backend availability (Ollama) and airplane mode status.

        Returns installation status, server state, available models, readiness,
        airplane mode configuration, and launch command.
        """
        params = GetLocalBackendStatusInput()
        return await get_local_backend_status_impl(params)

    @mcp.tool(
        name="list-ollama-integrations",
        annotations=tool_annotations(
            {
                "title": "List Ollama Integrations",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_ollama_integrations() -> str:
        """List canonical agent integrations exposed by `ollama launch`."""
        params = ListOllamaIntegrationsInput()
        return await list_ollama_integrations_impl(params)

    @mcp.tool(
        name="get-airplane-launch-overrides",
        annotations=tool_annotations(
            {
                "title": "Get Airplane Launch Overrides",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_airplane_launch_overrides(agent_id: str) -> str:
        """Return launch arguments for a supported Ollama agent integration."""
        params = GetAirplaneLaunchOverridesInput(agent_id=agent_id)
        return await get_airplane_launch_overrides_impl(params)

    # Register toggle airplane mode tool
    @mcp.tool(
        name="toggle-airplane-mode",
        annotations=tool_annotations(
            {
                "title": "Toggle Airplane Mode",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def toggle_airplane_mode(
        action: str = "toggle",
    ) -> str:
        """Toggle, enable, disable, or query airplane mode.

        Actions: on, off, toggle, status.
        Persists to preferences.yaml and returns current airplane_mode state.
        Status action also includes a connectivity check.
        """
        params = ToggleAirplaneModeInput(action=action)
        return await toggle_airplane_mode_impl(params)

    @mcp.tool(
        name="session-claim",
        annotations=tool_annotations(
            {
                "title": "Claim Session Ownership",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def session_claim(
        session_id: str,
        surface: str,
        pid: int,
        cli_id: str = "claude",
    ) -> str:
        """Claim one live owner of a CLI session id (ADR-766)."""
        return await session_claim_impl(
            SessionClaimInput(
                session_id=session_id,
                surface=surface,
                pid=pid,
                cli_id=cli_id,
            )
        )

    @mcp.tool(
        name="session-release",
        annotations=tool_annotations(
            {
                "title": "Release Session Ownership",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def session_release(
        session_id: str,
        surface: str,
        pid: int | None = None,
    ) -> str:
        """Release this surface's claim on a session id (ADR-766)."""
        return await session_release_impl(
            SessionReleaseInput(
                session_id=session_id,
                surface=surface,
                pid=pid,
            )
        )

    @mcp.tool(
        name="session-status",
        annotations=tool_annotations(
            {
                "title": "Session Ownership Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def session_status(session_id: str | None = None) -> str:
        """Return live local session owners and reclaim stale entries (ADR-766)."""
        return await session_status_impl(SessionStatusInput(session_id=session_id))

    # Register client routing tools
    @mcp.tool(
        name="resolve-client",
        annotations=tool_annotations(
            {
                "title": "Resolve AI Client",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def resolve_client(action_id: str) -> str:
        """Resolve which AI client should handle the given action.

        Walks the priority chain: airplane > local_flag > override > global > implicit.
        Returns client_id, client_type, model, and source.
        """
        params = ResolveClientInput(action_id=action_id)
        return await resolve_client_impl(params)

    @mcp.tool(
        name="set-client-override",
        annotations=tool_annotations(
            {
                "title": "Set Client Override",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def set_client_override(
        action_id: str,
        client_id: str | None = None,
        clear: bool = False,
    ) -> str:
        """Set or clear a per-action AI client override.

        Persists to client_routing.overrides in preferences.yaml.
        """
        params = SetClientOverrideInput(action_id=action_id, client_id=client_id, clear=clear)
        return await set_client_override_impl(params)

    @mcp.tool(
        name="list-available-clients",
        annotations=tool_annotations(
            {
                "title": "List Available Clients",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_available_clients() -> str:
        """List available AI clients from the integrations registry.

        Returns installed and healthy clients that can be used for action routing.
        """
        return await list_available_clients_impl()


__all__ = ["register_infrastructure_tools"]
