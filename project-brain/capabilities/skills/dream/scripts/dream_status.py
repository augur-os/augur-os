"""dream-status — compatibility wrapper over the ADR-758 routine status view.

The unified routine status surface owns ledger-derived status for every
routine, including dream. This module preserves the historical
``{"latest": ..., "history": [...]}`` shape for ``aug dream status`` and the
``dream-status`` MCP tool while delegating the read to the shared routine
status implementation.

The MCP wrapper passes ``get_runtime_dir() / "jobs"`` as ``jobs_root``; the
test suite passes a tmp path with synthetic per-job dirs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_TERMINAL_STATES = frozenset({"complete", "failed", "timeout", "cancelled"})


def dream_status(
    *,
    jobs_root: Path,
    kind: str = "dream",
    history_limit: int = 10,
) -> dict[str, Any]:
    """Return the latest dream job + a bounded history.

    Returns ``{"latest": {job_id, name, state, created_at} | None,
    "history": [{job_id, name, state, created_at}, ...]}`` (history sorted
    most-recent first; ``latest == history[0]`` when non-empty).
    """
    status_view = _load_status_view()
    routine_id = "dream" if kind == "dream" else kind
    payload = status_view.routine_status_payload(
        routine_id=routine_id,
        limit=history_limit,
        jobs_root=jobs_root,
    )
    rows = payload.get("routines", []) if isinstance(payload, dict) else []
    row = rows[0] if rows else {}
    recent_runs = row.get("recent_runs", []) if isinstance(row, dict) else []
    history = [_dream_history_entry(record) for record in recent_runs if isinstance(record, dict)]
    return {
        "latest": history[0] if history else None,
        "history": history,
    }


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _load_status_view():
    try:
        from routine_orchestrator import status_view

        return status_view
    except ModuleNotFoundError:
        daemon_scripts = Path(__file__).resolve().parents[2] / "daemon" / "scripts"
        if str(daemon_scripts) not in sys.path:
            sys.path.insert(0, str(daemon_scripts))
        from routine_orchestrator import status_view

        return status_view


def _dream_history_entry(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": record.get("job_id"),
        "name": record.get("name"),
        "state": record.get("state"),
        "created_at": record.get("created_at"),
    }


__all__ = ["dream_status"]
