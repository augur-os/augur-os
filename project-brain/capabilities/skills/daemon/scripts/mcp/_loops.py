"""Adaptive loop MCP tool registration.

Tools: get-daemon-loop-status, get-daemon-loop-history.
Split from __init__.py for module size management.
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
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from . import logger

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.config import get_project_root, get_runtime_dir
except ImportError:
    import os
    import sys

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    def get_project_root():
        from pathlib import Path

        data_dir = os.environ.get("AUGUR_ROOT")
        if data_dir:
            return Path(data_dir)
        return Path.home() / "Projects" / "augur"

    def get_runtime_dir():
        from pathlib import Path

        runtime_dir = os.environ.get("AUGUR_STATE") or os.environ.get("AUGUR_RUNTIME")
        if runtime_dir:
            return Path(runtime_dir)
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return Path.home() / ".local" / "state" / "augur"


def register_loop_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register adaptive loop tools with the MCP server."""

    @mcp.tool(
        name="get-daemon-loop-status",
        annotations=tool_annotations(
            {
                "title": "Get Daemon Loop Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_daemon_loop_status_tool() -> str:
        """Return adaptive loop status for daemon loop dashboard actions."""
        metrics.track_tool("get_daemon_loop_status", skill="daemon")

        try:
            import yaml as _yaml
            from adaptive.discovery import discover_auto_commands, group_by_loop

            project_root = get_project_root()
            adaptive_dir = get_runtime_dir() / "adaptive"
            config_file = project_root / "config" / "system" / "adaptive_loops.yaml"
            trust_file = adaptive_dir / "trust_state.json"

            config_payload: dict[str, Any] = {}
            if config_file.exists():
                with open(config_file) as f:
                    config_payload = _yaml.safe_load(f) or {}

            trust_payload: dict[str, Any] = {}
            if trust_file.exists():
                trust_payload = json.loads(trust_file.read_text())

            journal_entries = _read_journal_entries(adaptive_dir)

            loops_cfg = config_payload.get("loops", {}) if isinstance(config_payload, dict) else {}
            trust_loops = trust_payload.get("loops", {}) if isinstance(trust_payload, dict) else {}
            engine_payload = config_payload.get("engine", {}) if isinstance(config_payload, dict) else {}
            services_payload = config_payload.get("services", {}) if isinstance(config_payload, dict) else {}
            discovered_registry = discover_auto_commands(project_root)
            discovered_by_loop = group_by_loop(discovered_registry)
            summaries: list[dict[str, Any]] = []
            events_by_loop: dict[str, list[dict[str, Any]]] = {}
            for entry in journal_entries:
                loop_name = entry.get("loop")
                if isinstance(loop_name, str) and loop_name:
                    events_by_loop.setdefault(loop_name, []).append(entry)

            loop_names = sorted(
                {
                    *(loops_cfg.keys() if isinstance(loops_cfg, dict) else []),
                    *(trust_loops.keys() if isinstance(trust_loops, dict) else []),
                    *discovered_by_loop.keys(),
                }
            )

            for loop_name in loop_names:
                summary = _build_loop_summary(
                    loop_name,
                    loops_cfg,
                    trust_loops,
                    events_by_loop,
                    discovered_by_loop,
                )
                summaries.append(summary)

            return json.dumps(
                {
                    "success": True,
                    "engine": engine_payload,
                    "services": services_payload,
                    "loop_count": len(summaries),
                    "loops": summaries,
                    "journal": list(reversed(journal_entries[-50:])),
                    "moduleConfigs": loops_cfg if isinstance(loops_cfg, dict) else {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to get daemon loop status: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-daemon-loop-history",
        annotations=tool_annotations(
            {
                "title": "Get Daemon Loop History",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_daemon_loop_history_tool(limit: int = 50, loop: str | None = None) -> str:
        """Return recent adaptive loop history entries."""
        metrics.track_tool("get_daemon_loop_history", skill="daemon")

        try:
            events = [
                event for event in _read_journal_entries(get_runtime_dir() / "adaptive")
                if not loop or event.get("loop") == loop
            ]

            events = events[-max(1, limit) :]
            events.reverse()
            return json.dumps({"success": True, "events": events, "total": len(events)}, indent=2)
        except Exception as e:
            logger.error(f"Failed to get daemon loop history: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})


def _read_journal_entries(_adaptive_dir) -> list[dict[str, Any]]:
    from dataclasses import asdict
    from routine_orchestrator import ledger_view

    return [
        _strip_none(asdict(record))
        for record in ledger_view.read_all(jobs_root=_adaptive_dir.parent / "jobs")
    ]


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _summarize_loop_ownership(loop_entries: list[Any]) -> tuple[str, str]:
    """Return overall owner plus a trigger-by-trigger ownership summary."""

    if not loop_entries:
        return "unknown", "no discovered scheduler metadata"

    owners_by_trigger: dict[str, set[str]] = {}
    for entry in loop_entries:
        trigger = str(getattr(entry, "trigger", None) or "unknown")
        scheduler = str(getattr(entry, "scheduler", None) or "unknown")
        owners_by_trigger.setdefault(trigger, set()).add(scheduler)

    trigger_owners = {
        trigger: (sorted(schedulers)[0] if len(schedulers) == 1 else "mixed")
        for trigger, schedulers in sorted(owners_by_trigger.items())
    }
    unique_owners = set(trigger_owners.values())
    owner = next(iter(unique_owners)) if len(unique_owners) == 1 else "split"
    owner_detail = ", ".join(
        f"{trigger} via {scheduler}" for trigger, scheduler in trigger_owners.items()
    )
    return owner, owner_detail


def _build_loop_summary(
    loop_name: str,
    loops_cfg: dict,
    trust_loops: dict,
    events_by_loop: dict[str, list[dict[str, Any]]],
    discovered_by_loop: dict,
) -> dict[str, Any]:
    """Build a single loop summary dict for the dashboard payload."""
    loop_cfg = loops_cfg.get(loop_name, {}) if isinstance(loops_cfg, dict) else {}
    loop_trust = trust_loops.get(loop_name, {}) if isinstance(trust_loops, dict) else {}
    loop_events = events_by_loop.get(loop_name, [])
    loop_entries = discovered_by_loop.get(loop_name, [])
    last_event = loop_events[-1] if loop_events else None
    recent_events = loop_events[-20:]
    trust_categories = (
        loop_trust.get("categories", {})
        if isinstance(loop_trust, dict)
        else {}
    )
    if not isinstance(trust_categories, dict):
        trust_categories = {}
    max_clean_scan_streak = max(
        (cat.get("consecutive_clean_scans", 0) for cat in trust_categories.values() if isinstance(cat, dict)),
        default=0,
    )
    category_rows: list[dict[str, Any]] = []
    category_names = sorted(
        {
            *(trust_categories.keys()),
            *(entry.name for entry in loop_entries),
        }
    )
    entry_by_name = {entry.name: entry for entry in loop_entries}
    for category_name in category_names:
        category_payload = trust_categories.get(category_name, {})
        if not isinstance(category_payload, dict):
            category_payload = {}
        entry = entry_by_name.get(category_name)
        category_rows.append(
            {
                "name": category_name,
                "enabled": bool(category_payload.get("enabled", True)),
                "trust": float(
                    category_payload.get(
                        "trust",
                        entry.initial_trust if entry else 0.0,
                    )
                    or 0.0
                ),
                "tier": int(
                    category_payload.get("tier", entry.tier if entry else 0) or 0
                ),
                "difficulty": int(category_payload.get("difficulty", 0) or 0),
                "successCount": int(category_payload.get("success_count", 0) or 0),
                "failureCount": int(category_payload.get("failure_count", 0) or 0),
                "consecutiveSuccesses": int(
                    category_payload.get("consecutive_successes", 0) or 0
                ),
                "consecutiveFailures": int(
                    category_payload.get("consecutive_failures", 0) or 0
                ),
                "trigger": entry.trigger if entry else None,
            }
        )

    category_rows.sort(key=lambda row: (row["tier"], row["name"]))
    difficulty_current = max((row["difficulty"] for row in category_rows), default=0)
    owner, owner_detail = _summarize_loop_ownership(loop_entries)
    difficulty_label = (
        "starter"
        if difficulty_current <= 0
        else "steady"
        if difficulty_current == 1
        else "elevated"
        if difficulty_current == 2
        else "aggressive"
    )

    next_actions: list[str] = []
    if bool(loop_trust.get("probation", False)):
        next_actions.append("Loop is on probation and needs clean successful cycles before full budget resumes.")
    failing_categories = [row["name"] for row in category_rows if row["consecutiveFailures"] > 0]
    if failing_categories:
        next_actions.append(
            f"Investigate failing categories: {', '.join(failing_categories[:4])}"
        )
    disabled_categories = [row["name"] for row in category_rows if not row["enabled"]]
    if disabled_categories:
        next_actions.append(
            f"Re-enable or repair disabled categories: {', '.join(disabled_categories[:4])}"
        )
    if not next_actions and recent_events:
        next_actions.append("Recent loop runs are healthy; continue monitoring trust drift and budget usage.")

    cycle_summary = {
        "totalIssues": sum(1 for entry in recent_events if entry.get("result") != "success"),
        "autoFixed": sum(
            1
            for entry in recent_events
            if entry.get("result") == "success"
            and entry.get("category") != "engine"
        ),
        "manualFollowup": sum(
            1
            for entry in recent_events
            if entry.get("result") != "success"
            and entry.get("category") != "engine"
        ),
        "broken": sum(1 for row in category_rows if row["consecutiveFailures"] >= 3),
        "clean": sum(1 for row in category_rows if row["consecutiveFailures"] == 0),
        "categoriesRan": len(category_rows),
    }
    return {
        "name": loop_name,
        "enabled": bool(loop_cfg.get("enabled", True)) if isinstance(loop_cfg, dict) else True,
        "trigger": (
            "continuous"
            if {entry.trigger for entry in loop_entries} == {"continuous"}
            else "post-execution"
            if {entry.trigger for entry in loop_entries} == {"post-execution"}
            else "mixed"
            if len({entry.trigger for entry in loop_entries if entry.trigger}) > 1
            else "continuous"
            if loop_name == "self-heal"
            else "nightly"
        ),
        "owner": owner,
        "ownerDetail": owner_detail,
        "budget": loop_trust.get("budget", loop_cfg.get("budget") if isinstance(loop_cfg, dict) else None),
        "budgetRemaining": loop_trust.get(
            "budget_remaining",
            loop_cfg.get("budget") if isinstance(loop_cfg, dict) else None,
        ),
        "budgetGrowthRate": int(
            (loop_cfg.get("budget_growth_rate", 0) if isinstance(loop_cfg, dict) else 0) or 0
        ),
        "probation": bool(loop_trust.get("probation", False)),
        "probationSuccesses": int(loop_trust.get("probation_successes", 0) or 0),
        "consecutiveSuccesses": int(
            loop_trust.get("total_consecutive_successes", 0) or 0
        ),
        "lastRun": last_event.get("timestamp") if last_event else None,
        "recentSuccesses": sum(1 for entry in recent_events if entry.get("result") == "success"),
        "recentFailures": sum(1 for entry in recent_events if entry.get("result") != "success"),
        "categories": category_rows,
        "difficulty": {
            "current": difficulty_current,
            "max": max((row["difficulty"] for row in category_rows), default=0),
            "label": difficulty_label,
        },
        "cycleSummary": cycle_summary,
        "nextActions": next_actions,
        "maxCleanScanStreak": max_clean_scan_streak,
        "cycleCount": int(loop_trust.get("cycle_count", 0) or 0),
    }
