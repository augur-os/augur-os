"""
RAG Indexing and Retrieval MCP Tools.

This module is loaded dynamically by the Augur MCP server
via the plugin tool loading system.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

from src.lib.index.incremental import WATCH_CATEGORIES

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register RAG MCP tools by delegating to rag_tools."""
    from .rag_tools import register_tools as register_rag_tools

    register_rag_tools(mcp, mcp_tool_interceptor, metrics)


def register_subcommands(subparsers) -> None:
    """Register `aug rag <verb>` (ADR-260) — headless index sync/status."""
    parser = subparsers.add_parser(
        "rag", help="RAG index sync and status, headless (spec 2026-06-10)"
    )
    sub = parser.add_subparsers(dest="rag_verb")

    p_sync = sub.add_parser("sync", help="incremental sync of watch categories")
    p_sync.add_argument("--full", action="store_true", help="full reindex_all rebuild")
    p_sync.add_argument(
        "--category",
        action="append",
        dest="categories",
        help=f"limit to a category (repeatable); default: {', '.join(WATCH_CATEGORIES)}",
    )

    sub.add_parser("status", help="freshness per category + watcher heartbeat")
    parser.set_defaults(func=_run_rag_cli)


def _run_rag_cli(args, remaining) -> int:
    verb = getattr(args, "rag_verb", None)
    if not verb:
        print(
            json.dumps(
                {"error": "no verb", "verbs": ["sync", "status"]},
                indent=2,
            )
        )
        return 2

    if verb == "sync":
        from src.lib.index.incremental import sync_categories
        from src.lib.index.sync_lock import SyncLockHeld

        categories = set(args.categories or WATCH_CATEGORIES)
        try:
            stats = sync_categories(
                categories, project_root=_get_project_root(), full=args.full
            )
        except SyncLockHeld as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 1
        print(json.dumps({"ok": True, "full": args.full, "stats": stats}))
        return 0

    if verb == "status":
        import yaml

        from src.config.paths import get_rag_dir, get_runtime_dir

        status: dict = {"categories": {}, "watcher": None}
        checksums = get_rag_dir() / "_meta" / "checksums"
        if checksums.is_dir():
            for f in sorted(checksums.glob("*.yaml")):
                try:
                    data = yaml.safe_load(f.read_text()) or {}
                except (yaml.YAMLError, OSError):
                    status["categories"][f.stem] = {"error": "unreadable"}
                    continue
                if not isinstance(data, dict):
                    status["categories"][f.stem] = {"error": "unreadable"}
                    continue
                status["categories"][data.get("category", f.stem)] = {
                    "count": data.get("count"),
                    "indexed_at": data.get("indexed_at"),
                }
        state_file = get_runtime_dir() / "rag_watcher_state.json"
        if state_file.exists():
            try:
                status["watcher"] = json.loads(state_file.read_text())
            except (json.JSONDecodeError, OSError):
                status["watcher"] = {"error": "unreadable state file"}
        print(json.dumps(status, indent=2))
        return 0

    print(json.dumps({"error": f"unknown verb: {verb}"}))
    return 2


def _get_project_root():
    from src.config.paths import get_project_root

    return get_project_root()


__all__ = ["register_tools", "register_subcommands"]
