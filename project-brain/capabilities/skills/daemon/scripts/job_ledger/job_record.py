"""Job ledger record shapes + state resolution (ADR-743).

A job is a directory under get_runtime_dir()/jobs/<job-id>/ containing meta.json
and an append-only events.jsonl. Current state is the ``state`` of the last
valid JSONL line, never timestamp-sorted, so clock skew is harmless.
"""
from __future__ import annotations

import json
import logging
import re
from itertools import count
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("job_ledger.record")

TERMINAL_STATES = frozenset({"complete", "failed", "timeout", "cancelled"})
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_ID_COUNTER = count()


def jobs_dir() -> Path:
    """Root of the job ledger. Monkeypatchable in tests."""
    from src.config.paths import get_runtime_dir

    d = get_runtime_dir() / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-") or "job"


def new_job_id(name: str) -> str:
    """Return ``<YYYYMMDD-HHMMSS-mmm>-<name-slug>``."""
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S-") + f"{now.microsecond // 1000:03d}-{next(_ID_COUNTER) % 1000:03d}"
    return f"{stamp}-{slugify(name)}"


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def append_event(job_dir: Path, event: dict[str, Any]) -> bool:
    """Append one JSON line to events.jsonl. Internally safe; never raises."""
    try:
        event.setdefault("t", datetime.now(timezone.utc).isoformat())
        with (job_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, default=str) + "\n")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger append failed for %s: %s", job_dir.name, exc)
        return False


def read_events(job_dir: Path) -> list[dict[str, Any]]:
    """Read all valid events; malformed lines are skipped, not fatal."""
    path = job_dir / "events.jsonl"
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def current_state(job_dir: Path) -> str:
    """State of the last valid JSONL line; ``unknown`` if there are none."""
    events = read_events(job_dir)
    for event in reversed(events):
        if isinstance(event, dict) and "state" in event:
            return str(event["state"])
    return "unknown"


def read_meta(job_dir: Path) -> dict[str, Any]:
    path = job_dir / "meta.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
