"""
Background job management tool implementations.

These tools manage async operations like transcription, scraping, and batch processing.
"""

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from src.mcp.augur_shared.annotations import tool_annotations

from .models import CancelJobInput, GetJobStatusInput


def register_job_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register background job management tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="get-job-status",
        annotations=tool_annotations(
            {
                "title": "Get Background Job Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_job_status_tool(params: GetJobStatusInput) -> str:
        """Get the status of a background job.

        Use this to check progress of async operations like transcription,
        scraping, or batch generation.

        Args:
            params: GetJobStatusInput with job_id

        Returns:
            str: JSON with job status, progress, and result if complete
        """
        from src.mcp.augur_shared.job_manager import get_job_status

        metrics.track_tool("get_job_status")
        result = get_job_status(params.job_id)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="cancel-job",
        annotations=tool_annotations(
            {
                "title": "Cancel Background Job",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def cancel_job_tool(params: CancelJobInput) -> str:
        """Cancel a running background job.

        Args:
            params: CancelJobInput with job_id

        Returns:
            str: JSON with cancellation result
        """
        from src.mcp.augur_shared.job_manager import cancel_job

        metrics.track_tool("cancel_job")
        result = cancel_job(params.job_id)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="list-jobs",
        annotations=tool_annotations(
            {
                "title": "List Active Background Jobs",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_jobs_tool() -> str:
        """List all active and recent background jobs.

        Shows running jobs, their progress, and recent completions.

        Returns:
            str: JSON with list of jobs and their statuses
        """
        from src.mcp.augur_shared.job_manager import list_active_jobs

        metrics.track_tool("list_jobs")
        result = list_active_jobs()
        return json.dumps(result, indent=2)


__all__ = ["register_job_tools"]
