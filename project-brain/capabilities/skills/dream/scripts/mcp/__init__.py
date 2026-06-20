"""MCP tools + CLI subcommands for the dream skill (ADR-744).

Exposes:

- ``register_tools(mcp, mcp_tool_interceptor, metrics)`` — the nine dream MCP
  tools: dream-orphans, dream-stale-pages, dream-merge-candidates,
  dream-dead-citations, dream-cache-gc, dream-report-write, dream-last-report,
  dream-status, dream-config. CLI-default per the surface-decision-matrix;
  routine-callable always.
- ``register_subcommands(subparsers)`` — the ``aug dream <verb>`` CLI surface
  (ADR-260): orphans, stale-pages, merge-candidates, dead-citations, cache-gc,
  report-write, last-report, status, config.

Tier-recompute is **delegated** to ADR-738's existing ``entity-tier-recompute``
tool; dream owns no wrapper for it (spec correction folded in).
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

# Put this skill's own `scripts/` dir on sys.path so MCP-server and CLI entry
# points can both `import aggregators`, `import dead_citations`, etc.
_augur_scripts_dir = str(_AugurPath(__file__).resolve().parent.parent)
if _augur_scripts_dir not in _augur_sys.path:
    _augur_sys.path.insert(0, _augur_scripts_dir)

import json
from datetime import date as _date
from pathlib import Path
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


logger = get_entity_logger("mcp.command.dream")

_READ_ONLY = {"destructiveHint": False, "idempotentHint": True,
              "openWorldHint": False, "readOnlyHint": True}
_WRITE = {"destructiveHint": False, "idempotentHint": True,
          "openWorldHint": False, "readOnlyHint": False}


# ---------------------------------------------------------------------------
# Path-helper resolvers — monkey-patched in tests; production reads paths via
# src.config.paths.
# ---------------------------------------------------------------------------


def _resolve_vault_root() -> Path:
    from src.config.paths import get_vault_dir
    return Path(get_vault_dir())


def _resolve_cache_root() -> Path:
    from src.config.paths import get_cache_dir
    return Path(get_cache_dir())


def _resolve_documents_root() -> Path:
    from src.config.paths import get_documents_dir
    return Path(get_documents_dir())


def _resolve_jobs_root() -> Path:
    from src.config.paths import get_runtime_dir
    return Path(get_runtime_dir()) / "jobs"


def _resolve_report_output_root() -> Path:
    import dream_config as dc  # type: ignore[import-not-found]
    from src.config.paths import get_documents_machine_dir
    cfg = dc.dream_config()
    # output_dir is a subdir name under get_documents_machine_dir('reports')
    subdir = cfg.get("report", {}).get("output_dir", "dream")
    return get_documents_machine_dir("reports") / subdir


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any) -> None:
    """Register the nine dream MCP tools (ADR-744)."""
    logger.info("Registering dream MCP tools...")

    @mcp.tool(name="dream-orphans",
              annotations=tool_annotations({"title": "Dream Orphans", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def dream_orphans_tool(max_timeline_entries: int = 3) -> str:
        """Flag wiki pages with zero inbound graph edges and few timeline entries."""
        metrics.track_tool("dream_orphans", skill="dream")
        import aggregators  # type: ignore[import-not-found]
        return json.dumps(
            aggregators.dream_orphans(
                vault_root=_resolve_vault_root(),
                cache_root=_resolve_cache_root(),
                max_timeline_entries=max_timeline_entries,
            ),
            indent=2,
        )

    @mcp.tool(name="dream-stale-pages",
              annotations=tool_annotations({"title": "Dream Stale Pages", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def dream_stale_pages_tool(gap_days: int = 14) -> str:
        """Flag wiki pages whose compiled truth lags the newest timeline _at:."""
        metrics.track_tool("dream_stale_pages", skill="dream")
        import aggregators  # type: ignore[import-not-found]
        return json.dumps(
            aggregators.dream_stale_pages(
                vault_root=_resolve_vault_root(),
                gap_days=gap_days,
            ),
            indent=2,
        )

    @mcp.tool(name="dream-merge-candidates",
              annotations=tool_annotations({"title": "Dream Merge Candidates", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def dream_merge_candidates_tool() -> str:
        """Surface high-similarity wiki page pairs as merge candidates."""
        metrics.track_tool("dream_merge_candidates", skill="dream")
        import aggregators  # type: ignore[import-not-found]
        return json.dumps(
            aggregators.dream_merge_candidates(vault_root=_resolve_vault_root()),
            indent=2,
        )

    @mcp.tool(name="dream-dead-citations",
              annotations=tool_annotations({"title": "Dream Dead Citations", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def dream_dead_citations_tool() -> str:
        """Flag timeline `_source:` URIs that resolve to nothing."""
        metrics.track_tool("dream_dead_citations", skill="dream")
        import dead_citations  # type: ignore[import-not-found]
        return json.dumps(
            dead_citations.dream_dead_citations(
                vault_root=_resolve_vault_root(),
                cache_root=_resolve_cache_root(),
            ),
            indent=2,
        )

    @mcp.tool(name="dream-cache-gc",
              annotations=tool_annotations({"title": "Dream Cache GC", **_WRITE}))
    @mcp_tool_interceptor
    async def dream_cache_gc_tool(dry_run: bool = False) -> str:
        """Purge rebuildable cache files older than the configured retention."""
        metrics.track_tool("dream_cache_gc", skill="dream")
        import cache_gc  # type: ignore[import-not-found]
        import dream_config as dc  # type: ignore[import-not-found]
        cfg = dc.dream_config().get("cache_gc", {})
        return json.dumps(
            cache_gc.dream_cache_gc(
                cache_root=_resolve_cache_root(),
                retention_days=cfg.get("retention_days", 30),
                paths=cfg.get("paths", []),
                dry_run=dry_run,
            ),
            indent=2,
        )

    @mcp.tool(name="dream-report-write",
              annotations=tool_annotations({"title": "Dream Report Write", **_WRITE}))
    @mcp_tool_interceptor
    async def dream_report_write_tool(phase_results_json: str) -> str:
        """Render per-phase results into <documents>/reports/dream/<YYYY-MM-DD>.md."""
        metrics.track_tool("dream_report_write", skill="dream")
        import dream_report  # type: ignore[import-not-found]
        phase_results = json.loads(phase_results_json)
        path = dream_report.dream_report_write(
            phase_results=phase_results,
            output_root=_resolve_report_output_root(),
        )
        return json.dumps({"path": str(path)}, indent=2)

    @mcp.tool(name="dream-last-report",
              annotations=tool_annotations({"title": "Dream Last Report", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def dream_last_report_tool() -> str:
        """Return the most recent dream report's path + date."""
        metrics.track_tool("dream_last_report", skill="dream")
        import dream_report  # type: ignore[import-not-found]
        return json.dumps(
            dream_report.dream_last_report(output_root=_resolve_report_output_root()),
            indent=2,
        )

    @mcp.tool(name="dream-status",
              annotations=tool_annotations({"title": "Dream Status", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def dream_status_tool(history_limit: int = 10) -> str:
        """Return the latest dream job from the ADR-743 ledger + a bounded history."""
        metrics.track_tool("dream_status", skill="dream")
        return json.dumps(_dream_status_payload(history_limit=history_limit), indent=2)

    @mcp.tool(name="dream-config",
              annotations=tool_annotations({"title": "Dream Config", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def dream_config_tool() -> str:
        """Return the dream skill's parsed config.yaml."""
        metrics.track_tool("dream_config", skill="dream")
        import dream_config as dc  # type: ignore[import-not-found]
        return json.dumps(dc.dream_config(), indent=2)

    logger.info("dream MCP tools registered (9 tools)")


# ---------------------------------------------------------------------------
# CLI subcommand registration — `aug dream <verb>`
# ---------------------------------------------------------------------------


def register_subcommands(subparsers) -> None:
    """Register `aug dream <verb>` (ADR-260)."""
    parser = subparsers.add_parser("dream", help="Overnight synthesis routine — ADR-744")
    sub = parser.add_subparsers(dest="dream_verb")

    p_orphans = sub.add_parser("orphans", help="flag orphan wiki pages")
    p_orphans.add_argument("--max-timeline-entries", type=int, default=3)

    p_stale = sub.add_parser("stale-pages", help="flag pages with lagging compiled truth")
    p_stale.add_argument("--gap-days", type=int, default=14)

    sub.add_parser("merge-candidates", help="surface high-similarity page pairs")
    sub.add_parser("dead-citations", help="flag dead timeline _source: URIs")

    p_gc = sub.add_parser("cache-gc", help="purge rebuildable caches past retention")
    p_gc.add_argument("--dry-run", dest="dry_run", action="store_true")

    p_write = sub.add_parser("report-write", help="write the consolidated dream report")
    p_write.add_argument(
        "--phase-results-json",
        dest="phase_results_json",
        help="JSON-encoded phase results from the routine",
    )

    sub.add_parser("last-report", help="return the most recent dream report")

    p_run = sub.add_parser("run", help="run the dream cycle and record it in the ADR-743 ledger")
    p_run.add_argument("--iterations", type=int, default=1)
    p_run.add_argument("--cache-gc-dry-run", dest="cache_gc_dry_run", action="store_true")

    p_status = sub.add_parser("status", help="latest dream job from the ADR-743 ledger")
    p_status.add_argument("--history-limit", dest="history_limit", type=int, default=10)

    sub.add_parser("config", help="show the dream skill's config.yaml")

    parser.set_defaults(func=_run_dream_cli)


def _run_dream_cli(args, remaining) -> int:
    verb = getattr(args, "dream_verb", None)
    if not verb:
        print(json.dumps(
            {
                "error": "no verb",
                "verbs": ["orphans", "stale-pages", "merge-candidates",
                          "dead-citations", "cache-gc", "report-write",
                          "last-report", "run", "status", "config"],
            },
            indent=2,
        ))
        return 2

    try:
        if verb == "orphans":
            import aggregators  # type: ignore[import-not-found]
            payload = aggregators.dream_orphans(
                vault_root=_resolve_vault_root(),
                cache_root=_resolve_cache_root(),
                max_timeline_entries=args.max_timeline_entries,
            )
        elif verb == "stale-pages":
            import aggregators  # type: ignore[import-not-found]
            payload = aggregators.dream_stale_pages(
                vault_root=_resolve_vault_root(),
                gap_days=args.gap_days,
            )
        elif verb == "merge-candidates":
            import aggregators  # type: ignore[import-not-found]
            payload = aggregators.dream_merge_candidates(vault_root=_resolve_vault_root())
        elif verb == "dead-citations":
            import dead_citations  # type: ignore[import-not-found]
            payload = dead_citations.dream_dead_citations(
                vault_root=_resolve_vault_root(),
                cache_root=_resolve_cache_root(),
            )
        elif verb == "cache-gc":
            import cache_gc  # type: ignore[import-not-found]
            import dream_config as dc  # type: ignore[import-not-found]
            cfg = dc.dream_config().get("cache_gc", {})
            payload = cache_gc.dream_cache_gc(
                cache_root=_resolve_cache_root(),
                retention_days=cfg.get("retention_days", 30),
                paths=cfg.get("paths", []),
                dry_run=getattr(args, "dry_run", False),
            )
        elif verb == "report-write":
            import dream_report  # type: ignore[import-not-found]
            payload_in = json.loads(args.phase_results_json or "{}")
            written = dream_report.dream_report_write(
                phase_results=payload_in,
                output_root=_resolve_report_output_root(),
            )
            payload = {"path": str(written)}
        elif verb == "last-report":
            import dream_report  # type: ignore[import-not-found]
            payload = dream_report.dream_last_report(output_root=_resolve_report_output_root())
        elif verb == "run":
            import dream_run as dr  # type: ignore[import-not-found]
            payload = dr.dream_run(
                vault_root=_resolve_vault_root(),
                cache_root=_resolve_cache_root(),
                report_output_root=_resolve_report_output_root(),
                iterations=args.iterations,
                cache_gc_dry_run=getattr(args, "cache_gc_dry_run", False),
            )
            payload = _with_dream_alias_deprecation(payload)
        elif verb == "status":
            payload = _dream_status_payload(history_limit=args.history_limit)
        elif verb == "config":
            import dream_config as dc  # type: ignore[import-not-found]
            payload = dc.dream_config()
        else:
            print(json.dumps({"error": f"unknown verb {verb!r}"}, indent=2))
            return 2
    except Exception as exc:  # noqa: BLE001 — CLI returns the error rather than crashing
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, indent=2))
        return 1

    print(json.dumps(payload, indent=2, default=str))
    return 0


def _with_dream_alias_deprecation(payload):
    message = "DEPRECATED alias: use /routines run dream. This alias retires after the ADR-758 transition release."
    if isinstance(payload, dict):
        payload = dict(payload)
        payload.setdefault("deprecation", message)
    return payload


def _dream_status_payload(*, history_limit: int) -> dict[str, Any]:
    """Return dream status through the unified ADR-758 routine status view."""
    import dream_status as ds  # type: ignore[import-not-found]

    return ds.dream_status(
        jobs_root=_resolve_jobs_root(),
        history_limit=history_limit,
    )
    return {"deprecation": message, "result": payload}


__all__ = ["register_tools", "register_subcommands"]
