"""Background routine browse contract helpers for ADR-727."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from typing import Any

from src.config.paths import get_project_brain_dir, get_project_root

# A schedule whose prompt is `/routines run <id>` is the autonomous trigger source
# for that declared routine; the leading token after `run` is the declared id.
_ROUTINES_RUN_PATTERN = re.compile(r"/routines\s+run\s+([a-z0-9][\w-]*)", re.IGNORECASE)

_PROJECT_BRAIN_CAPABILITIES = get_project_brain_dir(get_project_root()) / "capabilities"
if str(_PROJECT_BRAIN_CAPABILITIES) not in sys.path:
    sys.path.insert(0, str(_PROJECT_BRAIN_CAPABILITIES))

from skills.daemon.scripts.routine_discovery import Routine, discover_all_routines  # noqa: E402


def _cadence_spec(routine: Routine) -> str:
    cadence = routine.cadence or {}
    cadence_type = str(cadence.get("type") or "")
    if cadence_type == "logon":
        return "on logon"
    return str(cadence.get("spec") or cadence.get("spec_raw") or cadence_type or "")


def _routine_to_detail(routine: Routine) -> dict[str, Any]:
    detail = asdict(routine)
    cadence = routine.cadence or {}
    detail.update(
        {
            # One-release compatibility surface for older scheduled detail code.
            "title": routine.display_name,
            "source": routine.source_kind,
            "kind": routine.source_kind,
            "workspace": "local machine",
            "execution_environment": "local",
            "schedule_human": _cadence_spec(routine),
            "raw_schedule": {
                "type": str(cadence.get("type") or ""),
                "value": str(cadence.get("spec_raw") or cadence.get("spec") or ""),
            },
            "prompt_summary": routine.description or "",
            "prompt_body": routine.description or "",
            "native_id": routine.id,
            "model": "",
            "next_run_at": cadence.get("next_run_estimated"),
            "warnings": [],
        }
    )
    return detail


def _routine_to_item(routine: Routine) -> dict[str, Any]:
    cadence = routine.cadence or {}
    ai_cost = routine.ai_cost or {}
    tags = [tag for tag in routine.tags if tag]
    if routine.spawn_kind and routine.spawn_kind not in tags:
        tags.append(routine.spawn_kind)
    if routine.source_kind and routine.source_kind not in tags:
        tags.append(routine.source_kind)

    return {
        "id": routine.id,
        "title": routine.display_name,
        "name": routine.display_name,
        "description": routine.description or "",
        "hub": "system",
        "type": "background-routines",
        "source_path": routine.source_path,
        "tags": tags,
        "metadata": {
            "source_kind": routine.source_kind,
            "source": routine.source_kind,
            "kind": routine.source_kind,
            "spawn_kind": routine.spawn_kind,
            "status": routine.status,
            "cadence": _cadence_spec(routine),
            "cadenceType": str(cadence.get("type") or ""),
            "cadenceRaw": str(cadence.get("spec_raw") or ""),
            "nextRun": str(cadence.get("next_run_estimated") or ""),
            "lastRun": routine.last_run_at or "",
            "last_run_status": routine.last_run_status or "",
            "last_run_log": routine.last_run_log or "",
            "recentRuns24h": str(routine.recent_runs_24h) if routine.recent_runs_24h is not None else "",
            "config_path": routine.config_path or "",
            "tokensPerRun": str(ai_cost.get("estimated_tokens_per_run") or ""),
            "tokensPerDay": str(ai_cost.get("estimated_tokens_per_day") or ""),
            "runsPerDay": str(ai_cost.get("estimated_runs_per_day") or ""),
            "cli": str(ai_cost.get("cli") or ""),
        },
    }


def list_background_routine_records(search: str | None = None) -> list[dict[str, Any]]:
    """Return normalized background routine detail records."""

    records = [_routine_to_detail(routine) for routine in discover_all_routines()]
    if not search:
        return records
    needle = search.strip().lower()
    return [
        record
        for record in records
        if needle in str(record.get("display_name") or record.get("title") or "").lower()
        or needle in str(record.get("description") or "").lower()
        or needle in str(record.get("source_kind") or "").lower()
        or needle in str(record.get("spawn_kind") or "").lower()
    ]


def list_background_routine_items(search: str | None = None) -> list[dict[str, Any]]:
    """Return normalized Browse rows for background routines."""

    routines = discover_all_routines()
    if search:
        needle = search.strip().lower()
        routines = [
            routine
            for routine in routines
            if needle in routine.display_name.lower()
            or needle in (routine.description or "").lower()
            or needle in routine.source_kind.lower()
            or needle in routine.spawn_kind.lower()
        ]
    return [_routine_to_item(routine) for routine in routines]


def dedupe_routine_items_against_schedules(
    routine_items: list[dict[str, Any]],
    scheduled_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop declared-routine rows that a scheduled execution already surfaces.

    The Routines tab merges two pipelines: routine_discovery (which emits ADR-758
    ``declared-routine`` rows from SKILL.md frontmatter) and scheduled_executions
    (codex/claude/augur-internal schedules). When a declared routine is actually
    scheduled — the schedule prompt invokes ``/routines run <id>`` — both pipelines
    surface the SAME routine, producing the duplicate cards a user sees in the tab.

    routine_discovery's own dedup only sees its sibling discoverers, never the
    separately-loaded schedules, so the twin survives until this merge step. Keep
    the schedule (richer: real cadence, drift status, conflict actions) and drop the
    declared twin, matching the DeclaredRoutineDiscoverer's documented intent of
    surfacing only declared routines with *no other* autonomous trigger source.
    """

    scheduled_routine_ids: set[str] = set()
    for item in scheduled_items:
        match = _ROUTINES_RUN_PATTERN.search(str(item.get("description") or ""))
        if match:
            scheduled_routine_ids.add(match.group(1).lower())

    if not scheduled_routine_ids:
        return routine_items

    return [
        item
        for item in routine_items
        if not (
            str((item.get("metadata") or {}).get("source_kind")) == "declared-routine"
            and str(item.get("id") or "").lower() in scheduled_routine_ids
        )
    ]


def get_background_routine_detail_impl(routine_id: str) -> str:
    """Return one background routine detail payload."""

    for routine in discover_all_routines():
        if routine.id == routine_id:
            return json.dumps({"success": True, "detail": _routine_to_detail(routine)}, default=str)
    return json.dumps({"success": False, "error": f"Background routine '{routine_id}' not found"})
