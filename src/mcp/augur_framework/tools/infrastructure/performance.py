"""
Performance and Monitoring tool implementations.

These tools handle system health, performance metrics, and dashboard data retrieval.
"""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

# Project root for dashboard imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


# Lazy import to avoid circular dependencies
def _get_data_dir() -> Path:
    """Get project root from centralized config."""
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()


def _get_runtime_stats_dir() -> Path:
    """Get canonical runtime stats directory."""
    from src.mcp.augur_shared.config import get_runtime_dir

    return get_runtime_dir() / "stats"


# =============================================================================
# Tool Registration
# =============================================================================


def register_performance_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register Performance and Monitoring tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="get-system-health",
        annotations=tool_annotations(
            {
                "title": "Get System Health Metrics",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_system_health_tool(action: str | None = None) -> str:
        """Get system health metrics.

        Args:
            action: Optional action (heal, install, uninstall, status, migrate).
                    When provided, included in the response for the caller.

        Returns:
            str: JSON with system health data from maintenance_status.json
        """
        metrics.track_tool("get_system_health")

        try:
            status_file = _get_runtime_stats_dir() / "maintenance_status.json"

            if not status_file.exists():
                return json.dumps({"success": False, "error": "No status file found (Script has not run yet)"})

            with open(status_file) as f:
                status = json.load(f)

            # When called with an action, include it in the response
            if action:
                status["action"] = action

            return json.dumps(status, indent=2)

        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-daily-summary",
        annotations=tool_annotations(
            {
                "title": "Get Daily Summary",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_daily_summary_tool() -> str:
        """Get daily usage summary.

        Returns:
            str: JSON with usage statistics from usage_summary.json
        """
        metrics.track_tool("get_daily_summary")

        try:
            summary_file = _get_runtime_stats_dir() / "usage_summary.json"

            if not summary_file.exists():
                return json.dumps(
                    {"total_requests": 0, "total_cost": 0, "errors": 0, "by_provider": {}, "by_model": {}}
                )

            with open(summary_file) as f:
                summary = json.load(f)

            return json.dumps(summary, indent=2)

        except Exception as e:
            logger.error(f"Failed to get daily summary: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-factory-status",
        annotations=tool_annotations(
            {
                "title": "Get Factory Processing Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_factory_status_tool() -> str:
        """Get Augur Factory processing status.

        Returns:
            str: JSON with factory status
        """
        metrics.track_tool("get_factory_status")

        try:
            import yaml

            status_file = _get_data_dir() / "factory" / "status.yaml"

            if not status_file.exists():
                return json.dumps({"status": "idle", "message": "Factory not running"})

            with open(status_file) as f:
                status = yaml.safe_load(f)

            return json.dumps(status or {}, indent=2)

        except Exception as e:
            logger.error(f"Failed to get factory status: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-performance-metrics",
        annotations=tool_annotations(
            {
                "title": "Get Performance Metrics",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_performance_metrics_tool() -> str:
        """Get page performance telemetry metrics.

        Returns:
            str: JSON with array of page performance measurements
        """
        metrics.track_tool("get_performance_metrics")

        try:
            from src.mcp.augur_framework.tools.infrastructure.page_telemetry import getPageMetrics

            page_metrics = await asyncio.to_thread(getPageMetrics)

            return json.dumps({"success": True, "data": page_metrics}, indent=2)

        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e), "data": []})

    @mcp.tool(
        name="save-performance-metric",
        annotations=tool_annotations(
            {
                "title": "Save Performance Metric",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def save_performance_metric_tool(
        path: str, metric: str, duration: float, timestamp: str | None = None
    ) -> str:
        """Save a page performance metric.

        Args:
            path: Page path (e.g., "/brain/intelligence")
            metric: Metric name (e.g., "page_load", "render_time")
            duration: Duration in milliseconds
            timestamp: ISO timestamp (defaults to now)

        Returns:
            str: JSON with success status
        """
        metrics.track_tool("save_performance_metric")

        try:
            from datetime import datetime

            from src.mcp.augur_framework.tools.infrastructure.page_telemetry import savePageMetric

            metric_data = {
                "path": path,
                "metric": metric,
                "duration": duration,
                "timestamp": timestamp or datetime.now().isoformat(),
            }

            await asyncio.to_thread(savePageMetric, metric_data)

            return json.dumps({"success": True}, indent=2)

        except Exception as e:
            logger.error(f"Failed to save performance metric: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-dashboard-data",
        annotations=tool_annotations(
            {
                "title": "Get Dashboard Data",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_dashboard_data_tool() -> str:
        """Get aggregated dashboard data.

        Note: This tool returns a minimal fallback since the full dashboard
        data is served by Next.js API routes, not the MCP server.

        Returns:
            str: JSON with dashboard data structure
        """
        metrics.track_tool("get_dashboard_data")

        # The original implementation tried to import TypeScript (lib/api.ts) from Python,
        # which is impossible. Dashboard data is served by Next.js API routes.
        # Return a valid fallback structure to prevent UI errors.
        logger.debug("get-dashboard-data: Returning fallback (use Next.js API routes for full data)")

        return json.dumps(
            {
                "success": True,
                "jobs": [],
                "recipes": [],
                "ideas": [],
                "reading": [],
                "social": {"total": 0},
                "system": {},
                "activities": [],
                "mcp": [],
                "agents": {"counts": {"ready": 0, "drafts": 0, "completed": 0}},
                "note": "Use /api/dashboard Next.js route for full data",
            },
            indent=2,
        )

    @mcp.tool(
        name="get-dashboard-groups",
        annotations=tool_annotations(
            {
                "title": "Get Dashboard Groups",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_dashboard_groups_tool() -> str:
        """Get dashboard groups configuration.

        Returns:
            str: JSON with groups list
        """
        metrics.track_tool("get_dashboard_groups")

        try:
            import yaml
            from src.mcp.augur_shared.config import get_project_root

            # Load page-skills config
            config_path = PROJECT_ROOT / "apps" / "dashboard" / "config" / "page-skills.yaml"
            page_skills_config: dict[str, Any] = {}
            if config_path.exists():
                with open(config_path) as f:
                    page_skills_config = yaml.safe_load(f) or {}

            # Load disabled dashboards
            project_root = get_project_root()
            user_config_path = project_root / "config.yaml"
            disabled_dashboards: set[str] = set()
            if user_config_path.exists():
                with open(user_config_path) as f:
                    user_config = yaml.safe_load(f) or {}
                    disabled_dashboards = set(user_config.get("dashboard_state", {}).get("disabled", []))

            dashboard_groups = page_skills_config.get("dashboard_groups", {})

            groups = [
                {
                    "id": group_id,
                    "description": group.get("description", ""),
                    "removable": group.get("removable", True),
                    "enabled": group_id not in disabled_dashboards,
                    "routes": group.get("routes", []),
                    "skills": group.get("skills", []),
                }
                for group_id, group in dashboard_groups.items()
            ]

            return json.dumps({"groups": groups}, indent=2)

        except Exception as e:
            logger.error(f"Failed to get dashboard groups: {e}", exc_info=True)
            return json.dumps({"error": str(e), "groups": []})


__all__ = ["register_performance_tools"]
