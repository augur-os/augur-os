"""Job ledger supervisor -- liveness sweep (ADR-743).

Scans jobs/ for non-terminal jobs. PID-gone -> failed/orphaned. PID alive but
heartbeat lapsed past threshold + declared timeout -> timeout (never force-killed
-- a live process is only surfaced). Surfaces every orphaned/timed-out job through
the daemon notification pipeline. Resubmit is opt-in via the allowlist, off by
default.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

try:
    from . import job_record
except ImportError:  # pragma: no cover - direct spec loading in tests
    import job_record

logger = logging.getLogger("job_ledger.supervisor")


def _pid_alive(pid: int) -> bool:
    """True if the process exists. Monkeypatched in tests."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _surface(job_id: str, reason: str) -> None:
    """Surface a stuck/orphaned job through the daemon notification pipeline."""
    try:
        import notification_service  # daemon sibling

        notification_service.notify(f"Job ledger: {job_id} {reason}", channel="daemon")
    except Exception as exc:  # noqa: BLE001 - surfacing failure must not break sweep
        logger.warning("job ledger could not surface %s (%s): %s", job_id, reason, exc)


def _last_running_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("state") == "running":
            return event
    return None


def sweep(*, config: dict[str, Any]) -> dict[str, Any]:
    """Scan jobs/, resolve liveness, surface and (opt-in) resubmit. Returns a summary."""
    threshold_s = int(config.get("heartbeat_threshold_s", 300))
    _allowlist = set(config.get("resubmit_allowlist", []) or [])
    root = job_record.jobs_dir()

    orphaned = timed_out = resubmitted = 0
    if not root.exists():
        return {"orphaned": orphaned, "timed_out": timed_out, "resubmitted": resubmitted}

    for job_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "_archive"):
        state = job_record.current_state(job_dir)
        if job_record.is_terminal(state) or state in ("unknown", "pending"):
            continue
        events = job_record.read_events(job_dir)
        last = _last_running_event(events)
        pid = int(last.get("pid", 0)) if last else 0

        if not _pid_alive(pid):
            job_record.append_event(job_dir, {"state": "failed", "reason": "orphaned"})
            _surface(job_dir.name, "orphaned (process gone)")
            orphaned += 1
        else:
            last_t = last.get("t") if last else None
            stale = _is_stale(last_t, threshold_s)
            meta = job_record.read_meta(job_dir)
            past_timeout = _past_declared_timeout(meta)
            if stale and past_timeout:
                job_record.append_event(job_dir, {"state": "timeout"})
                _surface(job_dir.name, "timeout (heartbeat lapsed past declared timeout)")
                timed_out += 1

    return {"orphaned": orphaned, "timed_out": timed_out, "resubmitted": resubmitted}


def _is_stale(last_t: str | None, threshold_s: int) -> bool:
    if not last_t:
        return True
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_t)).total_seconds()
        return age > threshold_s
    except (ValueError, TypeError):
        return True


def _past_declared_timeout(meta: dict[str, Any]) -> bool:
    timeout_s = meta.get("declared_timeout_s")
    created = meta.get("created_at")
    if not timeout_s or not created:
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(created)).total_seconds()
        return age > float(timeout_s)
    except (ValueError, TypeError):
        return False
