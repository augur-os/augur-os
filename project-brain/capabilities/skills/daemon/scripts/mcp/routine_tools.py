"""ADR-727 list-routines MCP tool."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from skills.daemon.scripts.routine_discovery import Routine, discover_all_routines

from . import logger

try:
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:

    def tool_annotations(annotations: dict) -> dict:
        return annotations


_CACHE_TTL_SECONDS = 60
_cache: dict[str, Any] = {"routines": None, "fetched_at": 0.0}


def _cache_clear() -> None:
    _cache["routines"] = None
    _cache["fetched_at"] = 0.0


def _fresh_discover() -> list[Routine]:
    return discover_all_routines()


def _get_routines_cached() -> list[Routine]:
    now = time.time()
    if _cache["routines"] is not None and now - float(_cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        return _cache["routines"]
    routines = _fresh_discover()
    _cache["routines"] = routines
    _cache["fetched_at"] = now
    return routines


async def list_routines(
    source_kind: str = "",
    spawn_kind: str = "",
    status: str = "",
) -> str:
    """List background routines, optionally filtered."""

    routines = _get_routines_cached()
    if source_kind:
        routines = [routine for routine in routines if routine.source_kind == source_kind]
    if spawn_kind:
        routines = [routine for routine in routines if routine.spawn_kind == spawn_kind]
    if status:
        routines = [routine for routine in routines if routine.status == status]
    return json.dumps(
        {
            "success": True,
            "routines": [asdict(routine) for routine in routines],
        },
        indent=2,
        default=str,
    )


def register_routine_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register background-routine MCP tools."""

    @mcp.tool(
        name="list-routines",
        annotations=tool_annotations(
            {
                "title": "List Background Routines",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_routines_tool(
        source_kind: str = "",
        spawn_kind: str = "",
        status: str = "",
    ) -> str:
        metrics.track_tool("list_routines", skill="daemon")
        try:
            return await list_routines(source_kind=source_kind, spawn_kind=spawn_kind, status=status)
        except Exception as exc:
            logger.error("Failed to list routines: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)}, indent=2)

    logger.info("Registered list-routines MCP tool")
