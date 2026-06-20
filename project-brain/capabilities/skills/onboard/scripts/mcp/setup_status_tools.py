"""MCP tools for the setup-completeness widget."""

from __future__ import annotations

import json


def _aggregator_imports():
    try:
        from scripts.setup.aggregator import clear_cache, compute_setup_status
    except ImportError:
        from setup.aggregator import clear_cache, compute_setup_status
    return clear_cache, compute_setup_status


def _state_imports():
    try:
        from scripts.setup.state import load_persisted_state, save_skipped
    except ImportError:
        from setup.state import load_persisted_state, save_skipped
    return load_persisted_state, save_skipped


def register_tools(mcp, mcp_tool_interceptor, metrics) -> None:
    @mcp.tool(name="get-setup-status")
    @mcp_tool_interceptor
    async def get_setup_status(skip_cache: bool = False, refresh: bool = False) -> str:
        """Return setup-completeness status for the dashboard widget."""
        if metrics:
            metrics.track_tool("get_setup_status", skill="onboard")
        try:
            _clear_cache, compute_setup_status = _aggregator_imports()
            status = compute_setup_status(skip_cache=bool(skip_cache or refresh))
            return json.dumps(status.to_dict(), default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="set-setup-skipped")
    @mcp_tool_interceptor
    async def set_setup_skipped(item_id: str, skipped: bool = True) -> str:
        """Mark or unmark a setup item as skipped."""
        if metrics:
            metrics.track_tool("set_setup_skipped", skill="onboard")
        try:
            clear_cache, _compute_setup_status = _aggregator_imports()
            load_persisted_state, save_skipped = _state_imports()

            current = list(load_persisted_state().skipped)
            if skipped and item_id not in current:
                current.append(item_id)
            elif not skipped and item_id in current:
                current.remove(item_id)
            saved = save_skipped(current)
            clear_cache()
            return json.dumps({"success": True, "skipped": saved})
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
