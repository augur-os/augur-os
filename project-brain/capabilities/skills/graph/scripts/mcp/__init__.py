"""MCP tools + CLI subcommands for the graph skill (ADR-738).

Exposes two registration entry points the Augur loader / CLI discover:

- `register_tools(mcp, mcp_tool_interceptor, metrics)` -- the 5 graph MCP tools:
  graph-query, graph-stats, graph-extract, entity-tier-recompute, graph-rebuild.
  CLI-primary per the surface-decision-matrix; browse-exposed, no direct MCP
  client surface unless capability_exposure.yaml opts in.
- `register_subcommands(subparsers)` -- the `aug graph <verb>` CLI surface
  (ADR-260): extract, query, stats, tier-recompute, rebuild.

No model calls. Deterministic typed-edge extraction over the vault.
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

# The MCP server registration path installs a custom importer so `scripts/mcp/*`
# can import sibling `scripts/*` modules; the CLI subcommand discovery path
# (src/cli_plugins.py) does not. Put this skill's own `scripts/` dir on sys.path
# so `import graph_ops` / `import graph_query` resolve under BOTH entry points.
_augur_scripts_dir = str(_AugurPath(__file__).resolve().parent.parent)
if _augur_scripts_dir not in _augur_sys.path:
    _augur_sys.path.insert(0, _augur_scripts_dir)

import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:  # pragma: no cover - fallback for early init / CLI
    import logging as _logging

    def get_entity_logger(name: str):
        return _logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.brain.graph")

_READ_ONLY = {"destructiveHint": False, "idempotentHint": True,
              "openWorldHint": False, "readOnlyHint": True}
_WRITE = {"destructiveHint": False, "idempotentHint": True,
          "openWorldHint": False, "readOnlyHint": False}


def register_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any) -> None:
    """Register the 5 graph MCP tools (ADR-738)."""
    logger.info("Registering graph MCP tools...")

    @mcp.tool(name="graph-query",
              annotations=tool_annotations({"title": "Graph Query", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def graph_query_tool(edge_type: str | None = None, entity: str | None = None) -> str:
        """Query typed edges by edge type and/or entity (matches src or dst)."""
        metrics.track_tool("graph_query", skill="graph")
        import graph_query as gq  # type: ignore[import-not-found]

        return json.dumps([e.__dict__ for e in gq.query(edge_type=edge_type, entity=entity)],
                          indent=2, default=str)

    @mcp.tool(name="graph-stats",
              annotations=tool_annotations({"title": "Graph Stats", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def graph_stats_tool() -> str:
        """Return edge/entity counts, per-type counts, tier distribution, dangling targets."""
        metrics.track_tool("graph_stats", skill="graph")
        import graph_query as gq  # type: ignore[import-not-found]

        return json.dumps(gq.stats(), indent=2, default=str)

    @mcp.tool(name="graph-extract",
              annotations=tool_annotations({"title": "Graph Extract", **_WRITE}))
    @mcp_tool_interceptor
    async def graph_extract_tool(path: str, source_type: str = "unknown") -> str:
        """Run extract -> merge -> cache for one page (the manual/repair path)."""
        metrics.track_tool("graph_extract", skill="graph")
        import graph_ops as go  # type: ignore[import-not-found]

        return json.dumps(go.index_page(path, source_type=source_type), indent=2, default=str)

    @mcp.tool(name="entity-tier-recompute",
              annotations=tool_annotations({"title": "Entity Tier Recompute", **_WRITE}))
    @mcp_tool_interceptor
    async def entity_tier_recompute_tool() -> str:
        """Recompute _entity_tier across all entities and refresh entities.jsonl."""
        metrics.track_tool("entity_tier_recompute", skill="graph")
        import graph_ops as go  # type: ignore[import-not-found]

        return json.dumps({"entities": len(go.recompute_tiers())}, indent=2)

    @mcp.tool(name="graph-rebuild",
              annotations=tool_annotations({"title": "Graph Rebuild", **_WRITE}))
    @mcp_tool_interceptor
    async def graph_rebuild_tool(prune: bool = False, dry_run: bool = False) -> str:
        """One-shot full-vault backfill: extract -> merge -> cache -> recompute tiers."""
        metrics.track_tool("graph_rebuild", skill="graph")
        import graph_rebuild as gr  # type: ignore[import-not-found]

        return json.dumps(gr.rebuild(prune=prune, dry_run=dry_run), indent=2, default=str)

    logger.info("graph MCP tools registered (5 tools)")


def register_subcommands(subparsers) -> None:
    """Register `aug graph <verb>` (ADR-260)."""
    parser = subparsers.add_parser("graph", help="Typed knowledge graph — ADR-738")
    sub = parser.add_subparsers(dest="graph_verb")

    p_extract = sub.add_parser("extract", help="extract->merge->cache for one page")
    p_extract.add_argument("path")
    p_extract.add_argument("--source-type", dest="source_type")

    p_query = sub.add_parser("query", help="query typed edges")
    p_query.add_argument("--type", dest="type")
    p_query.add_argument("--entity", dest="entity")

    sub.add_parser("stats", help="edge/entity/tier counts")
    sub.add_parser("tier-recompute", help="recompute _entity_tier for all entities")

    p_rebuild = sub.add_parser("rebuild", help="one-shot full-vault backfill")
    p_rebuild.add_argument("--prune", action="store_true")
    p_rebuild.add_argument("--dry-run", dest="dry_run", action="store_true")

    parser.set_defaults(func=_run_graph_cli)


def _run_graph_cli(args, remaining) -> int:
    verb = getattr(args, "graph_verb", None)
    if not verb:
        print(json.dumps({"error": "no verb",
                          "verbs": ["extract", "query", "stats", "tier-recompute", "rebuild"]},
                         indent=2))
        return 2
    import graph_ops  # type: ignore[import-not-found]

    return graph_ops.run_cli(verb, args)


__all__ = ["register_tools", "register_subcommands"]
