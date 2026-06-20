"""Insights-pending MCP tool registration (ADR-078).

Tool: insights-pending — returns count and list of pending daemon insights
filtered by dashboard page, used by the Magic button badge in FloatingChat.
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
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from . import logger, SCRIPTS_DIR

try:
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:

    def tool_annotations(annotations: dict) -> dict:
        return annotations


# Load the sibling impl module by file location: bare `import
# insights_pending_impl` only resolves when daemon/scripts happens to be on
# sys.path, which not every MCP loading context guarantees (the plugin loader
# imports this package directly). Namespaced module name per the
# sys.modules-namespacing discipline (generic names collide across skills).
_impl_path = _AugurPath(__file__).resolve().parent.parent / "insights_pending_impl.py"
_impl_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_daemon_insights_pending_impl", _impl_path
)
if _impl_spec is None or _impl_spec.loader is None:
    raise RuntimeError(f"Unable to load insights_pending_impl from {_impl_path}")
_impl_module = _augur_importlib_util.module_from_spec(_impl_spec)
_augur_sys.modules[_impl_spec.name] = _impl_module
_impl_spec.loader.exec_module(_impl_module)
build_insights_response = _impl_module.build_insights_response

from runtime_paths import get_insights_path


def register_insights_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register insights-pending tool with the MCP server."""

    @mcp.tool(
        name="insights-pending",
        annotations=tool_annotations(
            {
                "title": "Pending Insights",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def insights_pending_tool(page: str | None = None, count_only: bool = False) -> str:
        """Return count and list of pending daemon insights, optionally filtered by page.

        Args:
            page: Dashboard page path to filter by (e.g. '/career', '/health').
                  If omitted, returns all pending insights.
            count_only: Return only the count (empty insights array). The
                dashboard badge uses this — the full pending list can exceed
                1MB and the badge only reads `count`.

        Returns:
            JSON with count and insights array.
        """
        metrics.track_tool("insights_pending", skill="daemon")
        return build_insights_response(
            get_insights_path(), page=page, count_only=count_only
        )

    logger.info("Registered insights-pending MCP tool")
