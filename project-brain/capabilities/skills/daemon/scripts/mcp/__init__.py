"""
Data Expiration MCP Tool Implementations.

Tools for checking and managing data expiration across augur files.
Expired items are routed to the reviews system ("Needs Your Attention").

Migrated from augur-mcp/domain/data_expiration.py

This module is loaded dynamically by the Augur MCP server
via the plugin tool loading system.

Sub-modules:
    _expiration  — check-expirations, set-expiry, get-expiry-status
    _notifications — notification feed/manage/dismiss/send/preferences
    _loops — get-daemon-loop-status, get-daemon-loop-history
    _plugin_events — plugin-events-list, plugin-events-acknowledge
    _insights — insights-pending
    routine_tools — list-routines
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
import dataclasses
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Use augur_mcp imports with fallback to standalone
try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.config import get_project_root, get_runtime_dir
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    def get_project_root() -> Path:
        data_dir = os.environ.get("AUGUR_ROOT")
        if data_dir:
            return Path(data_dir)
        return Path.home() / "Projects" / "augur"

    def get_runtime_dir() -> Path:
        runtime_dir = os.environ.get("AUGUR_STATE") or os.environ.get("AUGUR_RUNTIME")
        if runtime_dir:
            return Path(runtime_dir)
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return Path.home() / ".local" / "state" / "augur"


logger = get_entity_logger("mcp.daemon")
_ROUTINE_VERBS = [
    "list",
    "status",
    "run",
    "report",
    "schedule",
    "goal",
    "all",
    "scan-only",
    "orchestrate",
    "pending-escalations",
    "drift",
    "adopt",
    "push",
    "goal-worktree",
    "goal-scan-loop",
    "goal-record-bucket",
    "goal-loop-status",
    "goal-escalate",
    "goal-drain-backlog",
    "goal-consume-finding",
    "goal-run-maintenance",
    "goal-run-inplace",
    "goal-fanout-plan",
    "goal-fanout-report",
]

# Plugin paths
TOOLS_DIR = Path(__file__).parent
SKILL_ROOT = TOOLS_DIR.parent.parent
AUGUR_DIR = SKILL_ROOT / "augur"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runtime_paths import (  # noqa: E402
    get_notification_history_path,
    get_notification_pending_path,
    get_notification_preferences_path,
)


# ============================================================================
# MCP Tool Registration
# ============================================================================


def _import_job_ledger_mcp():
    """Import the job ledger MCP package in both plugin-loader and CLI contexts."""
    try:
        return __import__(
            "scripts.job_ledger.mcp",
            fromlist=["register_tools", "register_subcommands"],
        )
    except ModuleNotFoundError as exc:
        if not str(exc.name or "").startswith("scripts"):
            raise

    return __import__("job_ledger.mcp", fromlist=["register_tools", "register_subcommands"])


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """
    Register Data Expiration tools with the MCP server.

    Delegates to focused sub-modules:
        _expiration — data expiry checking and management
        _notifications — notification feed, preferences, cleanup
        _loops — adaptive loop status and history
    """
    logger.info("Registering daemon MCP tools...")

    from ._expiration import register_expiration_tools
    from ._notifications import register_notification_tools
    from ._loops import register_loop_tools
    from ._plugin_events import register_plugin_event_tools
    from ._insights import register_insights_tools
    from .routine_tools import register_routine_tools
    job_ledger_mcp = _import_job_ledger_mcp()

    register_expiration_tools(mcp, mcp_tool_interceptor, metrics)
    register_notification_tools(mcp, mcp_tool_interceptor, metrics)
    register_loop_tools(mcp, mcp_tool_interceptor, metrics)
    register_plugin_event_tools(mcp, mcp_tool_interceptor, metrics)
    register_insights_tools(mcp, mcp_tool_interceptor, metrics)
    register_routine_tools(mcp, mcp_tool_interceptor, metrics)
    job_ledger_mcp.register_tools(mcp, mcp_tool_interceptor, metrics)

    logger.info("Daemon MCP tools registered successfully")


def register_subcommands(subparsers) -> None:
    """Register daemon skill CLI subcommands."""
    job_ledger_mcp = _import_job_ledger_mcp()

    _register_routine_subcommand(subparsers)
    job_ledger_mcp.register_subcommands(subparsers)


def _register_routine_subcommand(subparsers) -> None:
    """Register `aug a-loops <verb>` for loop orchestration."""
    parser = subparsers.add_parser(
        "a-loops",
        help="Unified loops registry and runner -- ADR-758",
    )
    sub = parser.add_subparsers(dest="routine_verb")

    p_list = sub.add_parser(
        "list",
        help="list every declared loop (grouped table; --json for raw)",
    )
    p_list.add_argument("--json", action="store_true", help="emit raw JSON instead of the table")

    p_status = sub.add_parser(
        "status",
        help="show ledger-derived status for one loop or all loops",
    )
    p_status.add_argument("routine_id", nargs="?", help="loop id to filter")
    p_status.add_argument("--limit", type=int, default=5, help="recent runs per loop")

    p_run = sub.add_parser(
        "run",
        help="run one declared loop",
    )
    p_run.add_argument("routine_id", help="loop id to run")

    p_report = sub.add_parser(
        "report",
        help="show report files for one declared loop",
    )
    p_report.add_argument("routine_id", help="loop id")
    p_report.add_argument("--limit", type=int, default=10, help="maximum reports to return")

    p_schedule = sub.add_parser(
        "schedule",
        help="show schedule seed bindings for one loop or all loops",
    )
    p_schedule.add_argument("routine_id", nargs="?", help="loop id to filter")
    p_schedule.add_argument("--source", default="", help="optional schedule source filter")

    p_goal = sub.add_parser(
        "goal",
        help="run or list goal-oriented loops",
    )
    p_goal.add_argument("goal_id", nargs="?", help="goal id or alias")
    p_goal.add_argument(
        "--max-iterations",
        type=int,
        default=1,
        help="maximum in-session iterations before stopping",
    )
    p_goal.add_argument(
        "--compound-proposal-json",
        type=Path,
        default=None,
        help="evidence-backed compound proposal JSON for the compounding proof gate",
    )
    p_goal.add_argument(
        "--skip-smoke",
        action="store_true",
        help="skip the mutating demo smoke step",
    )
    p_goal.add_argument(
        "--suggest",
        action="store_true",
        help="suggest catalog loop goals from live scan state",
    )
    p_goal.add_argument(
        "--catalog-loop",
        action="store_true",
        help="run a general catalog loop goal in an isolated worktree",
    )
    p_goal.add_argument("--stamp", default="", help="run stamp for the catalog goal branch")
    p_goal.add_argument("--loop-cap", type=int, default=6, help="per-loop iteration cap")
    p_goal.add_argument(
        "--suggest-timeout-seconds",
        type=float,
        default=2.0,
        help="per-loop timeout for --suggest scans",
    )
    p_goal.add_argument("--project-root", type=Path, default=None)
    p_goal.add_argument("--runtime-dir", type=Path, default=None)

    p_all = sub.add_parser(
        "all",
        help="parallel scan-triage + capped fan-out across orchestrator loops (in-session)",
    )
    p_all.add_argument("--dry-run", action="store_true",
                       help="triage only: print the fan-out plan, create nothing")
    p_all.add_argument("--cap", type=int, default=6,
                       help="max concurrent loop worktrees (clamped to registry headroom)")
    p_all.add_argument("--include", default="",
                       help="comma-separated subset of orchestrator loops")
    p_all.add_argument("--exclude", default="",
                       help="comma-separated orchestrator loops to skip")
    p_all.add_argument("--max-iterations", type=int, default=8,
                       help="whole-run iteration budget per loop")
    p_all.add_argument("--loop-cap", type=int, default=6, help="per-loop iteration cap")
    p_all.add_argument("--scan-timeout-seconds", type=float, default=8.0,
                       help="per-loop scan timeout for triage in seconds (default 8.0; values below 0.5 are clamped to 0.5)")

    p_scan = sub.add_parser(
        "scan-only",
        help="scan one loop and apply deterministic mechanical fixes",
    )
    p_scan.add_argument("--loop", required=True, help="loop name to scan")

    p_orchestrate = sub.add_parser(
        "orchestrate",
        help="run one loop through session-bound subagent orchestration",
    )
    p_orchestrate.add_argument("--loop", required=True, help="loop name to orchestrate")

    p_pending = sub.add_parser(
        "pending-escalations",
        help="show or compact queued no-session semantic findings",
    )
    pending_mode = p_pending.add_mutually_exclusive_group()
    pending_mode.add_argument("--show", action="store_true", help="print queue summary")
    pending_mode.add_argument(
        "--clear-stale",
        action="store_true",
        help="drop TTL-expired or malformed queue entries before printing",
    )

    p_drift = sub.add_parser(
        "drift",
        help="report drift between Augur seeds and installed Codex/Claude loops",
    )
    p_drift.add_argument(
        "--source",
        default="all",
        choices=["all", "codex", "claude-remote", "augur-internal"],
        help="restrict report to one surface",
    )

    p_adopt = sub.add_parser(
        "adopt",
        help="adopt installed-surface state into the owning seed file",
    )
    p_adopt.add_argument("routine_id", help="Browse loop id, e.g. codex:codex-dev-loop-testing")

    p_push = sub.add_parser(
        "push",
        help="force-sync seed over installed surface for one loop",
    )
    p_push.add_argument("routine_id", help="Browse loop id")

    # --- ADR-793 atomic goal-op verbs ---

    p_goal_worktree = sub.add_parser(
        "goal-worktree",
        help="resolve a goal and create its isolated worktree",
    )
    p_goal_worktree.add_argument("goal_id", help="goal id or alias")
    p_goal_worktree.add_argument("--stamp", default="", help="run stamp for the goal branch")

    p_goal_scan_loop = sub.add_parser(
        "goal-scan-loop",
        help="scan one loop in the worktree, apply mechanical fixes, return semantic buckets",
    )
    p_goal_scan_loop.add_argument("--loop", required=True, help="loop name to scan")
    p_goal_scan_loop.add_argument("--worktree", required=True, help="worktree path")
    p_goal_scan_loop.add_argument("--budget-used", type=int, default=0, help="iterations already used")
    p_goal_scan_loop.add_argument("--max-iterations", type=int, default=8, help="total iteration budget")
    p_goal_scan_loop.add_argument("--difficulty", type=int, default=0, help="scan difficulty level")

    p_goal_record_bucket = sub.add_parser(
        "goal-record-bucket",
        help="verify the worktree after a subagent applied a bucket fix and commit if green",
    )
    p_goal_record_bucket.add_argument("--worktree", required=True, help="worktree path")
    p_goal_record_bucket.add_argument("--loop", required=True, help="loop name")
    p_goal_record_bucket.add_argument("--auto-command", required=True, help="auto command name")
    p_goal_record_bucket.add_argument("--verify-command", default="", help="optional verify command")

    p_goal_loop_status = sub.add_parser(
        "goal-loop-status",
        help="report a stop verdict for the client's loop (converged/no_op/stalled/exhausted/continue)",
    )
    p_goal_loop_status.add_argument(
        "--prev-fingerprint", default="[]", help="previous residual fingerprint JSON array"
    )
    p_goal_loop_status.add_argument(
        "--current-fingerprint", default="[]", help="current residual fingerprint JSON array"
    )
    p_goal_loop_status.add_argument("--iterations", type=int, required=True, help="iterations completed so far")
    p_goal_loop_status.add_argument("--loop-cap", type=int, required=True, help="per-loop iteration cap")
    p_goal_loop_status.add_argument("--budget-remaining", type=int, required=True, help="remaining whole-run budget")
    p_goal_loop_status.add_argument(
        "--committed-count", type=int, default=None,
        help="verified checkpoints committed so far (lets an empty fingerprint be "
             "distinguished as genuine convergence vs a no-op); omit for legacy behavior",
    )
    p_goal_loop_status.add_argument(
        "--out-of-scope-count", type=int, default=0,
        help="findings dropped as out_of_worktree (foreign to the goal worktree); "
             "with 0 commits this yields the no_op verdict instead of a false converged",
    )

    p_goal_escalate = sub.add_parser(
        "goal-escalate",
        help="enqueue residual findings the loop could not resolve",
    )
    p_goal_escalate.add_argument(
        "--findings-json", default="[]", help="JSON array of finding dicts to escalate"
    )
    p_goal_escalate.add_argument("--runtime-dir", default=None, help="runtime directory override")

    p_goal_drain_backlog = sub.add_parser(
        "goal-drain-backlog",
        help="dequeue the existing backlog filtered to this goal's loops",
    )
    p_goal_drain_backlog.add_argument(
        "--loops", default="", help="comma-separated loop names to filter (empty = all)"
    )
    p_goal_drain_backlog.add_argument("--runtime-dir", default=None, help="runtime directory override")

    p_goal_consume_finding = sub.add_parser(
        "goal-consume-finding",
        help="remove one resolved backlog entry by id",
    )
    p_goal_consume_finding.add_argument("--entry-id", required=True, help="escalation queue entry id")
    p_goal_consume_finding.add_argument("--runtime-dir", default=None, help="runtime directory override")

    p_goal_run_maintenance = sub.add_parser(
        "goal-run-maintenance",
        help="deterministically run a maintenance finding via the command's fix() (no LLM)",
    )
    p_goal_run_maintenance.add_argument("--loop", required=True, help="loop name")
    p_goal_run_maintenance.add_argument("--worktree", required=True, help="worktree path")
    p_goal_run_maintenance.add_argument("--auto-command", required=True, help="maintenance auto command name")
    p_goal_run_maintenance.add_argument(
        "--findings-json", default="[]", help="JSON array of maintenance finding dicts"
    )

    p_goal_run_inplace = sub.add_parser(
        "goal-run-inplace",
        help="ADR-818: run an in-place loop against the live target (no worktree) with surface guardrails",
    )
    p_goal_run_inplace.add_argument("--loop", required=True, help="in-place loop name")
    p_goal_run_inplace.add_argument(
        "--surface", required=True, choices=["repo", "vault", "runtime", "mixed"],
        help="execution surface (picks the guardrail policy)",
    )
    p_goal_run_inplace.add_argument(
        "--difficulty", type=int, default=1,
        help="0=scan+escalate, >=1=aggressive auto-apply (runtime/repo only; vault is gated on ADR-816)",
    )

    p_fanout_plan = sub.add_parser(
        "goal-fanout-plan",
        help="triage orchestrator loops (non-mutating); print the fan-out plan",
    )
    p_fanout_plan.add_argument("--scope", default="orchestrator")
    p_fanout_plan.add_argument("--include", default="")
    p_fanout_plan.add_argument("--exclude", default="")
    p_fanout_plan.add_argument("--cap", type=int, default=6)
    p_fanout_plan.add_argument("--scan-timeout-seconds", type=float, default=8.0)
    p_fanout_plan.add_argument("--max-iterations", type=int, default=8)
    p_fanout_plan.add_argument("--loop-cap", type=int, default=6)

    p_fanout_report = sub.add_parser(
        "goal-fanout-report",
        help="write the honest per-loop rollup for a parallel /a-loops all run",
    )
    p_fanout_report.add_argument("--results-json", required=True,
        help="JSON array of {loop,verdict,branch,residual,committed_checkpoints,out_of_scope} "
             "dicts; a silent driver may be a null or {loop,branch,unreported:true} stub "
             "(its verdict is reconstructed from the worktree)")
    p_fanout_report.add_argument("--stamp", default="")
    p_fanout_report.add_argument("--runtime-dir", default=None)

    parser.set_defaults(func=_run_routine_cli)


def _run_routine_cli(args, remaining) -> int:
    del remaining
    verb = getattr(args, "routine_verb", None)
    if not verb:
        print(json.dumps({"error": "no verb", "verbs": _ROUTINE_VERBS}, indent=2))
        return 2

    try:
        if verb == "list":
            payload = _routine_list_payload()
            if not getattr(args, "json", False):
                print(_render_routine_table(payload))
                return 0
        elif verb == "status":
            payload = _routine_status_payload(
                routine_id=getattr(args, "routine_id", None),
                limit=getattr(args, "limit", 5),
            )
        elif verb == "run":
            payload = _routine_run_payload(getattr(args, "routine_id"))
        elif verb == "report":
            payload = _routine_report_payload(
                getattr(args, "routine_id"),
                limit=getattr(args, "limit", 10),
            )
        elif verb == "schedule":
            payload = _routine_schedule_payload(
                routine_id=getattr(args, "routine_id", None),
                source=getattr(args, "source", ""),
            )
        elif verb == "goal":
            payload = _routine_goal_payload(args)
        elif verb == "all":
            from routine_orchestrator import goal_ops
            plan = goal_ops.op_fanout_plan(
                scope="orchestrator",
                include=[s.strip() for s in args.include.split(",") if s.strip()],
                exclude=[s.strip() for s in args.exclude.split(",") if s.strip()],
                cap=args.cap,
                project_root=str(get_project_root()),
                scan_timeout_seconds=getattr(args, "scan_timeout_seconds", 8.0),
                max_iterations=args.max_iterations,
                loop_cap=args.loop_cap,
            )
            if getattr(args, "dry_run", False):
                payload = plan
            else:
                payload = {
                    "success": False,
                    "error": "no session",
                    "detail": (
                        "aug a-loops all fans out fix-subagents and requires an inline "
                        "AI-client session; run /a-loops all in-session, or use "
                        "--dry-run for the triage plan."
                    ),
                    "plan": plan,
                }
        elif verb == "scan-only":
            result = _load_routine_orchestrator().scan_only(args.loop)
            payload = _routine_result_payload(result)
        elif verb == "orchestrate":
            session = _detect_routine_session()
            surface = _routine_session_surface(session)
            if surface is None:
                print(
                    json.dumps(
                        {
                            "error": "no session detected",
                            "detail": (
                                "aug a-loops orchestrate requires a native AI-client session; "
                                "use scan-only for deterministic runs."
                            ),
                        },
                        indent=2,
                    )
                )
                return 1
            result = _load_routine_orchestrator().orchestrate_run(args.loop, session=session)
            payload = _routine_result_payload(result)
        elif verb == "pending-escalations":
            payload = _pending_escalations_payload(clear_stale=getattr(args, "clear_stale", False))
        elif verb == "drift":
            payload = _routine_drift_payload(source=getattr(args, "source", "all"))
        elif verb == "adopt":
            payload = _routine_adopt_payload(routine_id=getattr(args, "routine_id"))
        elif verb == "push":
            payload = _routine_push_payload(routine_id=getattr(args, "routine_id"))
        elif verb == "goal-worktree":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_worktree(
                goal_id=args.goal_id,
                stamp=args.stamp or _derive_goal_stamp(),
                project_root=str(get_project_root()),
            )
        elif verb == "goal-scan-loop":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_scan_loop(
                loop=args.loop,
                worktree_path=args.worktree,
                budget_used=args.budget_used,
                max_iterations=args.max_iterations,
                difficulty=args.difficulty,
                runtime_dir=str(_resolve_runtime_root()),
            )
        elif verb == "goal-record-bucket":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_record_bucket(
                worktree_path=args.worktree,
                loop=args.loop,
                auto_command=args.auto_command,
                verify_command=args.verify_command or None,
            )
        elif verb == "goal-loop-status":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_loop_status(
                prev_fingerprint=json.loads(args.prev_fingerprint),
                current_fingerprint=json.loads(args.current_fingerprint),
                iterations=args.iterations,
                loop_cap=args.loop_cap,
                budget_remaining=args.budget_remaining,
                committed_count=args.committed_count,
                out_of_scope_count=args.out_of_scope_count,
            )
        elif verb == "goal-escalate":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_escalate(
                findings=json.loads(args.findings_json),
                runtime_dir=args.runtime_dir or str(_resolve_runtime_root()),
            )
        elif verb == "goal-drain-backlog":
            from routine_orchestrator import goal_ops
            loops = [lp.strip() for lp in args.loops.split(",") if lp.strip()] if args.loops else []
            payload = goal_ops.op_drain_backlog(
                loops=loops,
                runtime_dir=args.runtime_dir or str(_resolve_runtime_root()),
            )
        elif verb == "goal-consume-finding":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_consume_finding(
                entry_id=args.entry_id,
                runtime_dir=args.runtime_dir or str(_resolve_runtime_root()),
            )
        elif verb == "goal-run-maintenance":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_run_maintenance(
                loop=args.loop,
                worktree_path=args.worktree,
                auto_command=args.auto_command,
                findings=json.loads(args.findings_json),
            )
        elif verb == "goal-run-inplace":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_run_inplace(
                loop=args.loop,
                surface=args.surface,
                difficulty=args.difficulty,
                project_root=str(get_project_root()),
            )
        elif verb == "goal-fanout-plan":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_fanout_plan(
                scope=args.scope,
                include=[s.strip() for s in args.include.split(",") if s.strip()],
                exclude=[s.strip() for s in args.exclude.split(",") if s.strip()],
                cap=args.cap,
                scan_timeout_seconds=args.scan_timeout_seconds,
                max_iterations=args.max_iterations,
                loop_cap=args.loop_cap,
                project_root=str(get_project_root()),
            )
        elif verb == "goal-fanout-report":
            from routine_orchestrator import goal_ops
            payload = goal_ops.op_fanout_report(
                results=json.loads(args.results_json),
                runtime_dir=args.runtime_dir or str(_resolve_runtime_root()),
                stamp=args.stamp,
            )
        else:
            print(
                json.dumps(
                    {"error": f"unknown verb {verb!r}", "verbs": _ROUTINE_VERBS},
                    indent=2,
                )
            )
            return 2
    except Exception as exc:  # noqa: BLE001 - CLI reports structured errors.
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, indent=2))
        return 1

    print(json.dumps(payload, indent=2, default=str))
    if isinstance(payload, dict) and payload.get("success") is False:
        return 1
    return 0


def _load_routine_orchestrator():
    import routine_orchestrator

    return routine_orchestrator


def _load_routine_registry():
    from routine_orchestrator import registry

    return registry


def _loop_kind_sets() -> tuple[set[str], set[str], set[str]]:
    """(prompt_loops, orchestrator_loops, goals) from the live registry + goal catalog.

    `goal-loop` is the catalog driver, not a bare-name target — excluded.
    """
    registry = _load_routine_registry()
    prompt: set[str] = set()
    orch: set[str] = set()
    for r in registry.list_routines():
        if r.id == "goal-loop":
            continue
        if getattr(r, "execution", "") == "inline-session":
            prompt.add(r.id)
        else:
            orch.add(r.id)
    try:
        from routine_orchestrator import goal_catalog  # type: ignore
    except ImportError:  # pragma: no cover
        goal_catalog = None
    goals = set(getattr(goal_catalog, "GOAL_CATALOG", {})) if goal_catalog else set()
    return prompt, orch, goals


def _rewrite_loop_argv(sub_argv: list[str]) -> tuple[list[str], str | None]:
    """Resolve a bare `a-loops <name>` into the routed verb invocation."""
    if not sub_argv:
        return sub_argv, None
    try:
        from routine_orchestrator.loop_name_resolver import resolve_loop_token  # type: ignore
    except ImportError:  # pragma: no cover
        from loop_name_resolver import resolve_loop_token  # type: ignore
    prompt, orch, goals = _loop_kind_sets()
    decision = resolve_loop_token(
        sub_argv[0],
        verbs=set(_ROUTINE_VERBS),
        prompt_loops=prompt,
        orchestrator_loops=orch,
        goals=goals,
    )
    if decision.kind == "verb":
        return sub_argv, None
    if decision.kind == "unknown":
        return sub_argv, decision.message
    # routed: replace the first token with the routed argv, preserve any trailing flags
    return list(decision.argv) + list(sub_argv[1:]), None


def _load_routine_ledger_view():
    from routine_orchestrator import ledger_view

    return ledger_view


def _load_routine_status_view():
    from routine_orchestrator import status_view

    return status_view


def _load_goal_loop():
    from routine_orchestrator import goal_loop

    return goal_loop


def _detect_routine_session():
    from routine_orchestrator import session_detect

    return session_detect.detect()


def _routine_session_surface(session) -> str | None:
    from routine_orchestrator import session_detect

    return session_detect.get_subagent_surface(session)


def _routine_result_payload(result: Any) -> Any:
    if isinstance(result, (dict, list, tuple, str, int, float, bool)) or result is None:
        return _jsonable(result)

    fields = [
        "loop_name",
        "counts",
        "findings",
        "mechanical_applied",
        "mechanical_failed",
        "deferred",
        "design_gate_findings",
        "dispatched",
        "enqueued",
        "events",
    ]
    payload = {
        field: _jsonable(getattr(result, field))
        for field in fields
        if hasattr(result, field)
    }
    return payload or _jsonable(result)


def _routine_list_payload() -> dict[str, Any]:
    routines = _load_routine_registry().list_routines()
    return {
        "success": True,
        "count": len(routines),
        "routines": [_routine_summary(routine) for routine in routines],
    }


def _routine_status_payload(*, routine_id: str | None, limit: int) -> dict[str, Any]:
    return _load_routine_status_view().routine_status_payload(
        routine_id=routine_id,
        limit=limit,
    )


def _annotate_run_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Surface a clear status when a run applied nothing (e.g. headless CLI)."""
    if not isinstance(payload, dict):
        return payload
    counts = payload.get("counts") or {}
    findings = int(counts.get("findings", 0) or 0)
    applied = int(counts.get("mechanical_applied", 0) or 0)
    dispatched = int(counts.get("dispatched", 0) or 0)
    deferred = int(counts.get("deferred", 0) or 0)
    escalated = int(counts.get("enqueued", 0) or 0)
    payload["summary"] = {
        "findings": findings, "applied": applied, "dispatched": dispatched,
        "deferred": deferred, "escalated": escalated,
    }
    if findings > 0 and (applied + dispatched) == 0:
        payload["status"] = "scanned-only"
        payload["message"] = (
            f"0 fixes applied — this run had no live fix-capable client session. "
            f"{escalated} finding(s) escalated. To actually fix, run in-session: "
            f"`/a-loops goal <id> --catalog-loop` (or `aug a-loops scan-only --loop <id>` "
            f"for a deterministic preview)."
        )
    return payload


def _routine_run_payload(routine_id: str) -> Any:
    registry = _load_routine_registry()
    routine = registry.get_routine(routine_id)
    kwargs: dict[str, Any] = {}
    if routine.execution == "tiered":
        session = _detect_routine_session()
        surface = _routine_session_surface(session)
        if surface is None:
            return {
                "success": False,
                "error": "no session detected",
                "detail": (
                    "aug a-loops run requires a native AI-client session for tiered loops; "
                    "use aug a-loops scan-only --loop <id> for deterministic scans."
                ),
            }
        kwargs["session"] = session
    return _annotate_run_status(_routine_result_payload(registry.dispatch(routine_id, **kwargs)))


def _routine_report_payload(routine_id: str, *, limit: int) -> dict[str, Any]:
    routine = _load_routine_registry().get_routine(routine_id)
    report_dir = _routine_report_dir(routine)
    report_candidates = _routine_report_files(routine)
    report_candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    reports = [
        {
            "path": str(path),
            "name": path.name,
            "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for path in report_candidates[:limit]
    ]
    report_dirs = sorted({str(path.parent) for path in report_candidates}) or [str(report_dir)]
    return {
        "success": True,
        "routine": _routine_summary(routine),
        "report_dir": report_dirs[0],
        "report_dirs": report_dirs,
        "reports": reports,
        "count": len(reports),
    }


def _routine_schedule_payload(*, routine_id: str | None, source: str) -> dict[str, Any]:
    registry = _load_routine_registry()
    routines = [registry.get_routine(routine_id)] if routine_id else registry.list_routines()
    schedules = []
    for routine in routines:
        for schedule in _read_routine_schedules(routine):
            if source and schedule.get("source") != source:
                continue
            loop_name = getattr(routine, "loop", None) or routine.id
            if schedule.get("loop") not in {None, loop_name, routine.id}:
                continue
            schedules.append(
                {
                    "routine_id": routine.id,
                    "skill_name": routine.skill_name,
                    **schedule,
                }
            )
    return {"success": True, "count": len(schedules), "schedules": schedules}


def _routine_goal_payload(args: Any) -> dict[str, Any]:
    goal_loop = _load_goal_loop()
    goal_id = getattr(args, "goal_id", None)
    if getattr(args, "suggest", False):
        return _routine_catalog_goal_payload(
            goal_id=None,
            stamp=getattr(args, "stamp", "") or _derive_goal_stamp(),
            max_iterations=getattr(args, "max_iterations", 1),
            loop_cap=getattr(args, "loop_cap", 6),
            suggest_timeout_seconds=getattr(args, "suggest_timeout_seconds", 2.0),
        )
    if getattr(args, "catalog_loop", False):
        return _routine_catalog_goal_payload(
            goal_id=goal_id,
            stamp=getattr(args, "stamp", "") or _derive_goal_stamp(),
            max_iterations=getattr(args, "max_iterations", 1),
            loop_cap=getattr(args, "loop_cap", 6),
            suggest_timeout_seconds=getattr(args, "suggest_timeout_seconds", 2.0),
        )
    if not goal_id:
        return goal_loop.list_goal_payloads()
    result = goal_loop.run_goal(
        goal_id,
        project_root=getattr(args, "project_root", None),
        runtime_dir=getattr(args, "runtime_dir", None),
        max_iterations=getattr(args, "max_iterations", 1),
        compound_proposal_json=getattr(args, "compound_proposal_json", None),
        skip_smoke=bool(getattr(args, "skip_smoke", False)),
    )
    if hasattr(result, "to_payload"):
        return result.to_payload()
    return _jsonable(result)


def _routine_summary(routine: Any) -> dict[str, Any]:
    return {
        "id": routine.id,
        "execution": routine.execution,
        "runner": getattr(routine, "runner", "") or "",
        "policy": routine.policy,
        "skill_name": routine.skill_name,
        "skill_root": str(routine.skill_root),
        "callable": routine.callable,
        "callable_path": str(routine.callable_path),
        "loop": getattr(routine, "loop", None),
        "hub": getattr(routine, "hub", None),
        "description": getattr(routine, "description", None),
    }


def _render_routine_table(payload: dict[str, Any]) -> str:
    """Render the loop list as a grouped human table with run guidance."""
    routines = payload.get("routines", []) or []
    count = payload.get("count", len(routines))
    prompts = sorted(
        (r for r in routines if r.get("execution") == "inline-session"),
        key=lambda r: str(r.get("id") or ""),
    )
    orchestrators = sorted(
        (r for r in routines if r.get("execution") != "inline-session"),
        key=lambda r: str(r.get("id") or ""),
    )

    def _row(r: dict[str, Any]) -> str:
        kind = "prompt" if r.get("execution") == "inline-session" else "orchestrator"
        return (
            f"  {str(r.get('id') or ''):20} {kind:12} "
            f"{str(r.get('runner') or ''):7} {str(r.get('skill_name') or ''):18} "
            f"{str(r.get('policy') or '')}"
        )

    lines: list[str] = [
        f"Augur Loops — {count} standard loops (all run natively in the active client)",
        "",
        f"{'ID':22} {'KIND':12} {'RUNNER':7} {'SKILL':18} TRUST",
        f"{'─' * 22} {'─' * 12} {'─' * 7} {'─' * 18} {'─' * 18}",
    ]
    if prompts:
        lines.append("PROMPT loops (hand the client a ready-to-run prompt)")
        lines.extend(_row(r) for r in prompts)
    if orchestrators:
        if prompts:
            lines.append("")
        lines.append("ORCHESTRATOR loops (scan → fix → verify; fixes can edit files)")
        lines.extend(_row(r) for r in orchestrators)
    lines += [
        "",
        "How to run — the loop name is the command:",
        "  a-loops <id>        names any loop (orchestrator -> single-loop goal in-session; prompt -> renders the prompt)",
        "  a-loops <goal>      a curated bundle (harden / clean / harden-and-clean)",
        "Explicit verbs (escape hatches):",
        "  a-loops run <id>                lightweight in-place run",
        "  a-loops scan-only --loop <id>   preview only (orchestrator loops, no edits)",
        "  a-loops status <id>             status / history",
        "  a-loops list --json             raw JSON",
    ]
    return "\n".join(lines)


def _read_routine_schedules(routine: Any) -> list[dict[str, Any]]:
    path = Path(routine.skill_root) / "assets" / "seeds" / "routine-schedule.yaml"
    if not path.is_file():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    schedules = payload.get("schedules", []) if isinstance(payload, dict) else []
    return [dict(item) for item in schedules if isinstance(item, dict)]


def _routine_report_dir(routine: Any) -> Path:
    try:
        from src.config.paths import get_documents_machine_dir

        return get_documents_machine_dir("reports") / routine.id
    except Exception:
        return Path.home() / "Documents" / "Augur" / "_augur" / "reports" / routine.id


def _routine_runtime_report_roots() -> list[Path]:
    try:
        from src.config.paths import get_runtime_dir

        runtime_dir = Path(get_runtime_dir())
    except Exception:
        runtime_dir = Path.home() / "Library" / "Application Support" / "Augur" / "state"
    return [
        runtime_dir / "reports",
        runtime_dir / "adaptive" / "reports",
    ]


def _routine_report_files(routine: Any) -> list[Path]:
    suffixes = {".md", ".json", ".jsonl", ".txt"}
    seen: set[str] = set()
    candidates: list[Path] = []

    report_dir = _routine_report_dir(routine)
    if report_dir.is_dir():
        for path in report_dir.iterdir():
            if path.is_file() and path.suffix.lower() in suffixes:
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    candidates.append(path)

    for root in _routine_runtime_report_roots():
        if not root.is_dir():
            continue
        for path in root.glob(f"{routine.id}*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(path)

    return candidates


def _routine_drift_payload(*, source: str = "all") -> dict[str, Any]:
    """Report drift between Augur seeds and installed loops across surfaces."""
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
            list_scheduled_execution_items,
        )
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"could not load scheduled_executions: {exc}"}

    items = list_scheduled_execution_items()
    if source != "all":
        items = [it for it in items if it.get("metadata", {}).get("source") == source]

    by_status: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        md = it.get("metadata", {})
        status = str(md.get("drift_status", "unknown"))
        by_status.setdefault(status, []).append(
            {
                "id": it.get("id"),
                "title": it.get("title"),
                "source": md.get("source"),
                "managed_by": md.get("managed_by"),
                "schedule": md.get("schedule"),
                "next_run": md.get("nextRun"),
                "source_path": it.get("source_path"),
            }
        )

    counts = {status: len(rows) for status, rows in by_status.items()}
    return {
        "success": True,
        "source_filter": source,
        "total": len(items),
        "counts_by_drift_status": counts,
        "entries": by_status,
    }


def _routine_adopt_payload(*, routine_id: str) -> dict[str, Any]:
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
            adopt_cloud_impl,
        )
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"could not load scheduled_conflict: {exc}"}
    import json as _json

    return _json.loads(adopt_cloud_impl(routine_id))


def _routine_push_payload(*, routine_id: str) -> dict[str, Any]:
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
            push_local_impl,
        )
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"could not load scheduled_conflict: {exc}"}
    import json as _json

    return _json.loads(push_local_impl(routine_id))


def _derive_goal_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _routine_catalog_goal_payload(
    *,
    goal_id: str | None,
    stamp: str,
    max_iterations: int = 1,
    loop_cap: int = 6,
    suggest_timeout_seconds: float = 2.0,
    catalog_loop: bool = False,
) -> dict[str, Any]:
    from routine_orchestrator import goal_suggest

    project_root = str(get_project_root())

    if not goal_id:
        suggestions = goal_suggest.suggest(
            project_root=project_root,
            per_loop_timeout_seconds=suggest_timeout_seconds,
        )
        return {
            "mode": "suggest",
            "success": True,
            "per_loop_timeout_seconds": suggest_timeout_seconds,
            "suggestions": [dataclasses.asdict(s) for s in suggestions],
        }

    session = _detect_routine_session()
    if _routine_session_surface(session) is None:
        return {
            "mode": "run",
            "success": False,
            "error": "bare-cli",
            "detail": (
                "goal --catalog-loop is an in-session routine. "
                "Run /a-loops goal <id> --catalog-loop inside an AI-client session. "
                "A bare CLI subprocess has no Task tool and cannot dispatch semantic fixes."
            ),
        }

    # Render the goal-loop inline-session routine so the client can dispatch it.
    # NOTE: the goal-loop routine declaration is added in Task 7.  Until then,
    # registry.dispatch("goal-loop") will raise RoutineNotFound.  We catch only
    # the registry's "not available yet" conditions so real bugs (ImportError,
    # TypeError, etc.) propagate and are reported with their true type by the
    # outer handler in _run_routine_cli.
    registry = _load_routine_registry()
    try:
        render_dict = registry.dispatch("goal-loop")
    except (registry.RoutineNotFound, registry.RoutineValidationError) as exc:
        return {
            "mode": "render",
            "success": False,
            "error": "routine goal-loop not declared yet",
            "detail": str(exc),
        }

    result = {"mode": "render", "goal_id": goal_id, "stamp": stamp}
    result.update(render_dict)
    result.setdefault("success", True)
    return result


def _pending_escalations_payload(*, clear_stale: bool) -> dict[str, Any]:
    runtime_root = _resolve_runtime_root()
    queue_path = runtime_root / "jobs" / "_escalations" / "pending.jsonl"

    if clear_stale:
        before = _nonempty_line_count(queue_path)
        events: list[dict[str, Any]] = []
        from routine_orchestrator import escalation_queue

        entries = escalation_queue.dequeue(runtime_dir=runtime_root, on_event=events)
        after = _nonempty_line_count(queue_path)
        return {
            "queue_path": str(queue_path),
            "pending": len(entries),
            "cleared": max(0, before - after),
            "events": events,
            "entries": _jsonable(entries),
        }

    entries, malformed = _read_pending_queue(queue_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fresh = [entry for entry in entries if _pending_entry_is_fresh(entry, now)]
    stale = len(entries) - len(fresh)
    return {
        "queue_path": str(queue_path),
        "pending": len(fresh),
        "stale": stale,
        "malformed": malformed,
        "entries": _jsonable(fresh),
    }


def _resolve_runtime_root() -> Path:
    return Path(get_runtime_dir())


def _read_pending_queue(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.is_file():
        return [], 0

    entries: list[dict[str, Any]] = []
    malformed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(value, dict):
            malformed += 1
            continue
        entries.append(value)
    return entries, malformed


def _pending_entry_is_fresh(entry: dict[str, Any], now: datetime) -> bool:
    try:
        expires_at = entry.get("expires_at")
        if isinstance(expires_at, str):
            return _parse_routine_time(expires_at) > now
        created_at = entry.get("created_at")
        ttl_seconds = int(entry.get("ttl_seconds", 14 * 24 * 60 * 60))
        if not isinstance(created_at, str):
            return False
        return _parse_routine_time(created_at) + timedelta(seconds=ttl_seconds) > now
    except (TypeError, ValueError):
        return False


def _parse_routine_time(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).replace(microsecond=0)


def _nonempty_line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return {
            str(key): _jsonable(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


__all__ = ["register_tools", "register_subcommands"]
