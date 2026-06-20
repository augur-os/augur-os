"""Platform Admin dashboard read-only MCP tools — cached/saved data for GET routes."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._shared import _run_python_script_async, tool_annotations


def register_dashboard_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register platform-admin dashboard read-only tools."""

    @mcp.tool(
        name="get-adaptive-growth",
        annotations=tool_annotations(
            {
                "title": "Get Adaptive Growth Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_adaptive_growth_tool() -> str:
        """Return cached adaptive growth data from the platform-admin vault."""
        metrics.track_tool("get_adaptive_growth", skill="platform-admin")
        from ._loaders import _load_adaptive_growth
        return json.dumps(
            await asyncio.to_thread(_load_adaptive_growth),
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="get-ci-matrix",
        annotations=tool_annotations(
            {
                "title": "Get CI Matrix",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_ci_matrix_tool() -> str:
        """Detect changed files and return the CI test matrix (delegates to ci_change_detector)."""
        metrics.track_tool("get_ci_matrix", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/ci_change_detector.py",
            ["--all"],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-dev-backup-status",
        annotations=tool_annotations(
            {
                "title": "Get Backup Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_dev_backup_status_tool() -> str:
        """Return the latest data backup status from the backup script."""
        metrics.track_tool("get_dev_backup_status", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/data_backup.py",
            ["status"],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-dev-dependencies",
        annotations=tool_annotations(
            {
                "title": "Get Dev Dependencies",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_dev_dependencies_tool() -> str:
        """Return the dependency graph from the platform-admin vault."""
        metrics.track_tool("get_dev_dependencies", skill="platform-admin")
        from ._loaders import _load_dependencies
        return json.dumps(
            await asyncio.to_thread(_load_dependencies),
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="get-nightly-checks",
        annotations=tool_annotations(
            {
                "title": "Get Nightly Checks Results",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_nightly_checks_tool() -> str:
        """Return the latest nightly check results from the platform-admin vault."""
        metrics.track_tool("get_nightly_checks", skill="platform-admin")
        from ._loaders import _load_nightly_checks
        return json.dumps(
            await asyncio.to_thread(_load_nightly_checks),
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="get-release-plan",
        annotations=tool_annotations(
            {
                "title": "Get Release Plan",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_release_plan_tool() -> str:
        """Return a release dry-run preview for the next release."""
        metrics.track_tool("get_release_plan", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/release.py",
            ["platform-admin", "--patch", "--dry-run", "--skip-tests"],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-runbooks",
        annotations=tool_annotations(
            {
                "title": "Get Runbooks",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_runbooks_tool() -> str:
        """Return all available incident runbooks."""
        metrics.track_tool("get_runbooks", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/platform-admin/scripts/incident_runbooks.py",
            ["--json"],
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-compliance-status",
        annotations=tool_annotations(
            {
                "title": "Get Compliance Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_compliance_status_tool() -> str:
        """Return plugin compliance validation results."""
        metrics.track_tool("get_compliance_status", skill="platform-admin")
        result = await _run_python_script_async(
            "project-brain/capabilities/skills/validator/scripts/validate_plugin_compliance.py",
        )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(
        name="get-security-report",
        annotations=tool_annotations(
            {
                "title": "Get Security Report",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_security_report_tool() -> str:
        """Return the latest security audit report from Documents/reports/security/."""
        metrics.track_tool("get_security_report", skill="platform-admin")
        from ._loaders import _load_security_report
        return json.dumps(
            await asyncio.to_thread(_load_security_report),
            indent=2,
            default=str,
        )

    @mcp.tool(
        name="verify-dashboard-mounts",
        annotations=tool_annotations(
            {
                "title": "Verify Dashboard Mounts",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def verify_dashboard_mounts_tool() -> str:
        """Verify that all plugin dashboard page mounts have matching source files."""
        metrics.track_tool("verify_dashboard_mounts", skill="platform-admin")
        from ._loaders import _verify_dashboard_mounts
        return json.dumps(
            await asyncio.to_thread(_verify_dashboard_mounts),
            indent=2,
            default=str,
        )
