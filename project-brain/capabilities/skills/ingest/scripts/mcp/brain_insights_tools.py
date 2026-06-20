from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from src.config.paths import get_runtime_dir
from skills.ingest.scripts.brain_insights import build_brain_insights
from src.lib.ingest.inbox_store import InboxStore

from ._shared import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _store_root() -> "Path":
    return get_runtime_dir() / "brain" / "inbox"


def _store() -> InboxStore:
    return InboxStore(_store_root())


async def brain_insights_impl() -> str:
    return json.dumps(build_brain_insights(store=_store()))


def register_brain_insights_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    @mcp.tool(
        name="brain-insights",
        annotations=tool_annotations(
            {
                "title": "Brain Insights",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def brain_insights_tool() -> str:
        if metrics:
            metrics.track_tool("brain_insights", skill="ingest")
        return await brain_insights_impl()
