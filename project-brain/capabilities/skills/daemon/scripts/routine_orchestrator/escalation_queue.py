"""Pending escalation queue for ADR-755 routine orchestration."""
from __future__ import annotations

import contextlib
import json
import os
import uuid
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_TTL_SECONDS = 14 * 24 * 60 * 60

EventSink = Callable[[dict[str, Any]], None] | list[dict[str, Any]] | None


def enqueue(
    finding: dict[str, Any],
    *,
    runtime_dir: Path | str | None = None,
    path: Path | str | None = None,
    now: datetime | str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    """Append one finding to the pending escalation queue."""
    queue_path = _pending_path(runtime_dir=runtime_dir, path=path)
    entry = build_entry(finding, now=now, ttl_seconds=ttl_seconds)
    with _queue_lock(queue_path):
        _append_jsonl(queue_path, entry)
    return entry


def build_entry(
    finding: dict[str, Any],
    *,
    now: datetime | str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    entry_id: str | None = None,
) -> dict[str, Any]:
    """Build a queue entry without writing it."""
    timestamp = _coerce_now(now)
    expires_at = timestamp + timedelta(seconds=ttl_seconds)
    return {
        "id": entry_id or uuid.uuid4().hex,
        "finding": dict(finding),
        "created_at": _format_time(timestamp),
        "updated_at": _format_time(timestamp),
        "ttl_seconds": ttl_seconds,
        "expires_at": _format_time(expires_at),
    }


def dequeue(
    *,
    runtime_dir: Path | str | None = None,
    path: Path | str | None = None,
    now: datetime | str | None = None,
    on_event: EventSink = None,
) -> list[dict[str, Any]]:
    """Return non-stale pending entries and compact away stale/bad lines."""
    queue_path = _pending_path(runtime_dir=runtime_dir, path=path)
    timestamp = _coerce_now(now)
    with _queue_lock(queue_path):
        return _dequeue_unlocked(queue_path, now=timestamp, on_event=on_event)


load = dequeue


def pick_up(
    entry_id: str,
    *,
    runtime_dir: Path | str | None = None,
    path: Path | str | None = None,
    now: datetime | str | None = None,
    worker_id: str = "",
    on_event: EventSink = None,
) -> dict[str, Any] | None:
    """Mark a pending entry as picked up unless another worker already did."""
    queue_path = _pending_path(runtime_dir=runtime_dir, path=path)
    picked_path = queue_path.with_name("picked_up.jsonl")
    timestamp = _coerce_now(now)
    with _queue_lock(queue_path):
        picked_ids = {
            str(entry.get("id", ""))
            for entry in _load_valid_entries(picked_path, on_event=on_event)[0]
        }
        if entry_id in picked_ids:
            return None

        entries = _dequeue_unlocked(queue_path, now=timestamp, on_event=on_event)
        entry = next((item for item in entries if item.get("id") == entry_id), None)
        if entry is None:
            return None

        marker = {
            "id": entry_id,
            "picked_up_at": _format_time(timestamp),
            "worker_id": worker_id,
        }
        _append_jsonl(picked_path, marker)
        return entry


def complete(
    entry_id: str,
    *,
    runtime_dir: Path | str | None = None,
    path: Path | str | None = None,
    on_event: EventSink = None,
) -> bool:
    """Remove a successfully processed entry from pending.jsonl."""
    queue_path = _pending_path(runtime_dir=runtime_dir, path=path)
    with _queue_lock(queue_path):
        entries, changed = _load_valid_entries(queue_path, on_event=on_event)
        kept = [entry for entry in entries if entry.get("id") != entry_id]
        removed = len(kept) != len(entries)
        if changed or removed:
            _rewrite_jsonl(queue_path, kept)
        return removed


def _pending_path(
    *,
    runtime_dir: Path | str | None = None,
    path: Path | str | None = None,
) -> Path:
    if path is not None:
        return Path(path)
    root = Path(runtime_dir) if runtime_dir is not None else _default_runtime_dir()
    return root / "jobs" / "_escalations" / "pending.jsonl"


def _default_runtime_dir() -> Path:
    from src.config.paths import get_runtime_dir

    return Path(get_runtime_dir())


def _load_valid_entries(
    path: Path,
    *,
    on_event: EventSink = None,
) -> tuple[list[dict[str, Any]], bool]:
    if not path.is_file():
        return [], False

    entries: list[dict[str, Any]] = []
    changed = False
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            changed = True
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            changed = True
            _emit(
                on_event,
                {
                    "event": "escalation_queue_malformed_line",
                    "line_number": line_number,
                    "reason": "json_decode_error",
                },
            )
            continue
        if not isinstance(value, dict):
            changed = True
            _emit(
                on_event,
                {
                    "event": "escalation_queue_malformed_line",
                    "line_number": line_number,
                    "reason": "not_an_object",
                },
            )
            continue
        entries.append(value)
    return entries, changed


def _dequeue_unlocked(
    queue_path: Path,
    *,
    now: datetime,
    on_event: EventSink = None,
) -> list[dict[str, Any]]:
    entries, changed = _load_valid_entries(queue_path, on_event=on_event)
    fresh: list[dict[str, Any]] = []
    for entry in entries:
        try:
            is_fresh = _is_fresh(entry, now)
        except (TypeError, ValueError):
            changed = True
            _emit(
                on_event,
                {
                    "event": "escalation_queue_malformed_line",
                    "entry_id": entry.get("id", ""),
                    "reason": "invalid_timestamp",
                },
            )
            continue

        if is_fresh:
            fresh.append(entry)
            continue
        changed = True
        _emit(
            on_event,
            {
                "event": "escalation_queue_stale_drop",
                "entry_id": entry.get("id", ""),
                "dropped_at": _format_time(now),
                "reason": "ttl_expired",
            },
        )
    if changed:
        _rewrite_jsonl(queue_path, fresh)
    return fresh


def _is_fresh(entry: dict[str, Any], now: datetime) -> bool:
    expires_at = entry.get("expires_at")
    if isinstance(expires_at, str):
        return _parse_time(expires_at) > now

    created_at = entry.get("created_at")
    ttl_seconds = entry.get("ttl_seconds", DEFAULT_TTL_SECONDS)
    if not isinstance(created_at, str):
        return False
    return _parse_time(created_at) + timedelta(seconds=int(ttl_seconds)) > now


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")


def _rewrite_jsonl(path: Path, entries: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
    os.replace(tmp_path, path)


@contextlib.contextmanager
def _queue_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            import fcntl
        except ImportError:
            yield
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _coerce_now(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    if isinstance(value, datetime):
        timestamp = value
    else:
        timestamp = _parse_time(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).replace(microsecond=0)


def _parse_time(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).replace(microsecond=0)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _emit(on_event: EventSink, event: dict[str, Any]) -> None:
    if on_event is None:
        return
    if isinstance(on_event, list):
        on_event.append(event)
        return
    on_event(event)
