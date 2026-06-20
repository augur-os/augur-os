from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# NOTE: submodule imports are intentionally lazy (inside register_tools / the
# subcommand handler) rather than at module top-level. plugin_tools.py loads
# this file in full package context (where `from .url_tools import ...` works),
# but cli_plugins.py (ADR-260 subcommand discovery) loads it bare via
# spec_from_file_location with no parent package — top-level relative imports
# raise there and would silently drop our `aug note-url` subcommand. Keeping the
# module top-level import-free lets it load cleanly in both contexts.


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any = None,
) -> None:
    from .inbox_tools import register_inbox_tools
    from .brain_insights_tools import register_brain_insights_tools
    from .note_classification_tools import register_note_classification_tools
    from .tools_enrich import register_enrich_tools
    from .url_tools import register_url_tools

    register_inbox_tools(mcp, mcp_tool_interceptor, metrics)
    register_brain_insights_tools(mcp, mcp_tool_interceptor, metrics)
    register_url_tools(mcp, mcp_tool_interceptor, metrics)
    register_enrich_tools(mcp, mcp_tool_interceptor, metrics)
    register_note_classification_tools(mcp, mcp_tool_interceptor, metrics)


def register_subcommands(subparsers: Any) -> None:
    """Register `aug note-url` (ADR-260 CLI subcommand surface).

    ingest is a vault-tier bundle (config/system/mcp_servers.yaml
    monolith_exclusions), so its MCP tools are NOT in the in-process monolith
    that `aug` builds — only the dashboard connects to the ingest bundle server.
    This subcommand gives every CLI agent session a first-class one-shot for the
    `/note <url>` flow without standing up the bundle, by calling note_url_impl
    in-process. Mirrors the graph skill's `aug graph <verb>` pattern.
    """
    parser = subparsers.add_parser(
        "note-url",
        help="Fetch a URL's full prose and save a note card (used by /note <url>)",
    )
    parser.add_argument("--url", required=True, help="URL to capture")
    parser.add_argument(
        "--tags", default="[]", help="JSON list of tags, e.g. '[\"a\",\"b\"]'"
    )
    parser.add_argument("--note", default="", help="Optional capture note")
    parser.set_defaults(func=_run_note_url_cli)


def _ensure_skill_paths() -> None:
    """Self-bootstrap sys.path for handlers that run in the bare cli_plugins load
    context (project root + src/mcp are on path, but not project-brain). __file__
    is the real on-disk path .../project-brain/capabilities/skills/ingest/scripts/mcp/__init__.py.
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


def _run_note_url_cli(args: Any, remaining: Any) -> int:
    import asyncio
    import json

    _ensure_skill_paths()
    from skills.ingest.scripts.mcp.url_tools import note_url_impl

    result = asyncio.run(
        note_url_impl(url=args.url, tags=args.tags, note=args.note)
    )
    print(result)
    try:
        return 0 if json.loads(result).get("success") else 1
    except (ValueError, TypeError):
        return 1


__all__ = ["register_tools", "register_subcommands"]
