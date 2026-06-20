from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# NOTE: submodule imports are intentionally lazy (inside register_tools / the
# subcommand handler) rather than at module top-level. plugin_tools.py loads
# this file in full package context (where relative imports work), but
# cli_plugins.py (ADR-260 subcommand discovery) loads it bare via
# spec_from_file_location with no parent package — top-level relative imports
# raise there and would silently drop our `aug wiki` subcommand. Keeping the
# module top-level import-free lets it load cleanly in both contexts.


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    from .wiki_tools import register_wiki_tools

    register_wiki_tools(mcp, mcp_tool_interceptor, metrics)


def register_subcommands(subparsers: Any) -> None:
    """Register `aug wiki` (ADR-260 CLI subcommand surface).

    wiki is a vault-tier bundle (config/system/mcp_servers.yaml
    monolith_exclusions), so its MCP tools are NOT in the in-process monolith
    that `aug` builds — only the dashboard connects to the wiki bundle server.
    This subcommand gives every CLI agent session a first-class one-shot for
    wiki read-only ops without standing up the bundle. Mirrors the graph
    skill's `aug graph <verb>` pattern.
    """
    wiki = subparsers.add_parser(
        "wiki", help="Read-only wiki ops from the CLI (status | list | search)"
    )
    wiki_sub = wiki.add_subparsers(dest="wiki_verb")
    wiki_sub.add_parser("status", help="Wiki structure, backlog, coverage, index status")
    wiki_list = wiki_sub.add_parser("list", help="List wiki pages")
    wiki_list.add_argument("--hub", default="", help="Filter by hub")
    wiki_search = wiki_sub.add_parser("search", help="Search wiki pages by content")
    wiki_search.add_argument("query", help="Search query")
    wiki.set_defaults(func=_run_wiki_cli)


def _ensure_skill_paths() -> None:
    """Self-bootstrap sys.path for handlers that run in the bare cli_plugins load
    context (project root + src/mcp are on path, but not project-brain). __file__
    is the real on-disk path .../project-brain/capabilities/skills/wiki/scripts/mcp/__init__.py.
    """
    import sys
    from pathlib import Path

    here = Path(__file__).resolve()
    shared_vault = here.parents[4]
    project_root = shared_vault.parent
    for candidate in (
        str(project_root),
        str(shared_vault),
        str(project_root / "src" / "mcp"),
    ):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


def _run_wiki_cli(args: Any, remaining: Any) -> int:
    import json

    verb = getattr(args, "wiki_verb", None)
    if not verb:
        print(json.dumps({"error": "no verb", "verbs": ["status", "list", "search"]}, indent=2))
        return 2

    _ensure_skill_paths()
    from skills.wiki.scripts.mcp.wiki_tools import _get_wiki_pages, build_wiki_status

    try:
        if verb == "status":
            payload = build_wiki_status()
        elif verb == "list":
            pages = _get_wiki_pages().list_pages(hub=getattr(args, "hub", "") or None)
            payload = {"success": True, "pages": pages, "count": len(pages)}
        elif verb == "search":
            matches = _get_wiki_pages().search(getattr(args, "query", "") or "", tags=None)
            payload = {"success": True, "matches": matches, "count": len(matches)}
        else:
            payload = {"error": f"unknown verb: {verb}"}
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(payload, indent=2, default=str))
    return 0


__all__ = ["register_tools", "register_subcommands"]
