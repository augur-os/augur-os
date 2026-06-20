"""Unified routine status view for ADR-758 surfaces."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from . import ledger_view, registry


def routine_status_payload(
    *,
    routine_id: str | None = None,
    limit: int = 5,
    jobs_root: Path | None = None,
    skills_root: Path | str | None = None,
    skills_roots: list[Path | str] | tuple[Path | str, ...] | None = None,
) -> dict[str, Any]:
    """Return the canonical ledger-derived status payload for routines."""
    routines = (
        [registry.get_routine(routine_id, skills_root=skills_root, skills_roots=skills_roots)]
        if routine_id
        else registry.list_routines(skills_root=skills_root, skills_roots=skills_roots)
    )
    rows: list[dict[str, Any]] = []
    for routine in routines:
        loop_name = getattr(routine, "loop", None) or routine.id
        recent_runs = ledger_view.read_recent_runs(loop=loop_name, limit=0, jobs_root=jobs_root)
        recent_runs.sort(
            key=lambda record: (
                str(getattr(record, "timestamp", "") or ""),
                str(getattr(record, "job_id", "") or ""),
            ),
            reverse=True,
        )
        if limit > 0:
            recent_runs = recent_runs[:limit]
        row = routine_summary(routine)
        row["last_run"] = _jsonable(recent_runs[0]) if recent_runs else None
        row["recent_runs"] = _jsonable(recent_runs)
        rows.append(row)
    return {"success": True, "count": len(rows), "routines": rows}


def routine_summary(routine: Any) -> dict[str, Any]:
    """Return the stable JSON summary shape for one routine declaration."""
    return {
        "id": routine.id,
        "execution": routine.execution,
        "policy": routine.policy,
        "skill_name": routine.skill_name,
        "skill_root": str(routine.skill_root),
        "callable": routine.callable,
        "callable_path": str(routine.callable_path),
        "loop": getattr(routine, "loop", None),
        "hub": getattr(routine, "hub", None),
        "description": getattr(routine, "description", None),
    }


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


__all__ = ["routine_status_payload", "routine_summary"]
