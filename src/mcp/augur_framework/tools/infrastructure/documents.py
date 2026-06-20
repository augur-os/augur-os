"""
Document Operations tool implementations.

These tools handle bug syncing to GitHub.
"""

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from src.lib.staged_skill_catalog import find_skill_file
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.config import get_project_root
from src.mcp.augur_shared.logging import get_entity_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

# Project root for path resolution
PROJECT_ROOT = get_project_root()


# =============================================================================
# Pydantic Input Models
# =============================================================================


class SyncBugsInput(BaseModel):
    """Input for syncing bugs to GitHub."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    force: bool = Field(default=False, description="Force sync even if recently synced")


# =============================================================================
# Tool Registration
# =============================================================================


def register_document_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register Document Operations tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="sync-bugs",
        annotations=tool_annotations(
            {
                "title": "Sync Bugs to GitHub",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def sync_bugs_tool(
        force: bool = False,
        title: str = "",
        description: str = "",
        source: str = "dashboard_ui",
        priority: str = "P2",
        stack_trace: str = "",
        metadata: dict | None = None,
    ) -> str:
        """Sync bugs from local database to GitHub issues, or file a new bug.

        Args:
            force: Force sync even if recently synced
            title: Bug title (for filing a new bug)
            description: Bug description (for filing a new bug)
            source: Bug source (default: dashboard_ui)
            priority: Bug priority (default: P2)
            stack_trace: Stack trace if available
            metadata: Additional metadata dict

        Returns:
            str: JSON with sync results
        """
        metrics.track_tool("sync_bugs")

        try:
            import importlib.util as _ilu

            _script = find_skill_file(PROJECT_ROOT, "advisor", "scripts", "analytics", "sync_bugs_to_github.py")
            if _script is None:
                raise FileNotFoundError("advisor sync_bugs_to_github.py not found in live or staged skills")

            _spec = _ilu.spec_from_file_location("sync_bugs_to_github", _script)
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            sync_bugs = _mod.sync_bugs

            result = sync_bugs(force=force)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to sync bugs: {e}")
            return json.dumps({"success": False, "error": str(e), "synced": 0})


__all__ = ["register_document_tools"]
