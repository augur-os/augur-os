"""MCP tools and CLI subcommands for the job ledger (ADR-743)."""
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

_augur_job_ledger_dir = str(_AugurPath(__file__).resolve().parent.parent)
if _augur_job_ledger_dir not in _augur_sys.path:
    _augur_sys.path.insert(0, _augur_job_ledger_dir)

import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:  # pragma: no cover
    import logging as _logging

    def get_entity_logger(name: str):
        return _logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.daemon.job_ledger")

_READ_ONLY = {
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
    "readOnlyHint": True,
}
_WRITE = {
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
    "readOnlyHint": False,
}


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register the five jobs-* MCP tools."""
    logger.info("Registering job ledger MCP tools...")

    @mcp.tool(name="jobs-list", annotations=tool_annotations({"title": "Jobs List", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def jobs_list_tool(state: str | None = None, kind: str | None = None) -> str:
        """List ledger jobs with current state; filter by state/kind."""
        metrics.track_tool("jobs_list", skill="daemon")
        import jobs_ops

        return json.dumps(jobs_ops.list_jobs(state=state, kind=kind), indent=2, default=str)

    @mcp.tool(name="jobs-detail", annotations=tool_annotations({"title": "Jobs Detail", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def jobs_detail_tool(job_id: str) -> str:
        """Full meta.json and events.jsonl for one job id."""
        metrics.track_tool("jobs_detail", skill="daemon")
        import jobs_ops

        return json.dumps(jobs_ops.job_detail(job_id), indent=2, default=str)

    @mcp.tool(name="jobs-submit", annotations=tool_annotations({"title": "Jobs Submit", **_WRITE}))
    @mcp_tool_interceptor
    async def jobs_submit_tool(kind: str, name: str, timeout_s: int | None = None) -> str:
        """Register and start a job for a dispatched workflow."""
        metrics.track_tool("jobs_submit", skill="daemon")
        import jobs_ops

        return json.dumps(jobs_ops.submit_job(kind=kind, name=name, timeout_s=timeout_s), indent=2)

    @mcp.tool(name="jobs-cancel", annotations=tool_annotations({"title": "Jobs Cancel", **_WRITE}))
    @mcp_tool_interceptor
    async def jobs_cancel_tool(job_id: str) -> str:
        """Write a cooperative cancel marker for a running job."""
        metrics.track_tool("jobs_cancel", skill="daemon")
        import jobs_ops

        return json.dumps(jobs_ops.cancel_job(job_id), indent=2)

    @mcp.tool(name="jobs-replay", annotations=tool_annotations({"title": "Jobs Replay", **_WRITE}))
    @mcp_tool_interceptor
    async def jobs_replay_tool(job_id: str) -> str:
        """Create a fresh job from a previous job's metadata."""
        metrics.track_tool("jobs_replay", skill="daemon")
        import jobs_ops

        return json.dumps(jobs_ops.replay_job(job_id), indent=2)

    logger.info("job ledger MCP tools registered (5 tools)")


def register_subcommands(subparsers) -> None:
    """Register `aug jobs <verb>`."""
    parser = subparsers.add_parser("jobs", help="File-based job ledger -- ADR-743")
    sub = parser.add_subparsers(dest="jobs_verb")
    p_list = sub.add_parser("list", help="list jobs")
    p_list.add_argument("--state")
    p_list.add_argument("--kind")
    p_detail = sub.add_parser("detail", help="full events for one job")
    p_detail.add_argument("job_id")
    p_cancel = sub.add_parser("cancel", help="request cooperative cancel")
    p_cancel.add_argument("job_id")
    p_replay = sub.add_parser("replay", help="create a fresh job from previous metadata")
    p_replay.add_argument("job_id")
    parser.set_defaults(func=_run_jobs_cli)


def _run_jobs_cli(args, remaining) -> int:
    verb = getattr(args, "jobs_verb", None)
    import jobs_ops

    if verb == "list":
        print(json.dumps(jobs_ops.list_jobs(state=args.state, kind=args.kind), indent=2, default=str))
    elif verb == "detail":
        print(json.dumps(jobs_ops.job_detail(args.job_id), indent=2, default=str))
    elif verb == "cancel":
        print(json.dumps(jobs_ops.cancel_job(args.job_id), indent=2))
    elif verb == "replay":
        print(json.dumps(jobs_ops.replay_job(args.job_id), indent=2))
    else:
        print(json.dumps({"error": "no verb", "verbs": ["list", "detail", "cancel", "replay"]}, indent=2))
        return 2
    return 0


__all__ = ["register_tools", "register_subcommands"]
