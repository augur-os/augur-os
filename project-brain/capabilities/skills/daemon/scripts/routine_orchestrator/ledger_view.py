"""Ledger-derived view of adaptive loop history records (ADR-757)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from job_ledger import job_record
except ImportError:  # pragma: no cover - package import path
    from skills.daemon.scripts.job_ledger import job_record


@dataclass
class JournalRecord:
    """Journal-shaped adaptive loop history record stored in the ADR-743 ledger."""

    loop: str
    action: str
    category: str
    result: str
    timestamp: str = ""
    files: list[str] | None = None
    commit: str | None = None
    error: str | None = None
    duration_ms: int = 0
    job_id: str | None = None
    kind: str | None = None
    name: str | None = None
    state: str | None = None
    created_at: str | None = None


class LedgerJournalWriter:
    """Adaptive history writer that writes only to the ADR-743 ledger."""

    def __init__(self, _legacy_dir: Path | None = None) -> None:
        del _legacy_dir

    def log(
        self,
        loop: str,
        action: str,
        category: str,
        result: str,
        files: list[str] | None = None,
        commit: str | None = None,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> JournalRecord:
        entry = JournalRecord(
            loop=loop,
            action=action,
            category=category,
            result=result,
            timestamp=datetime.now(timezone.utc).isoformat(),
            files=files,
            commit=commit,
            error=error,
            duration_ms=duration_ms,
        )
        _append_journal_record(entry)
        return entry


class LedgerJournalReader:
    """Adaptive history reader backed by ADR-743 job ledger records."""

    def read_all(self) -> list[JournalRecord]:
        return read_all()

    def filter(
        self,
        loop: str | None = None,
        category: str | None = None,
        result: str | None = None,
    ) -> list[JournalRecord]:
        records = self.read_all()
        if loop:
            records = [record for record in records if record.loop == loop]
        if category:
            records = [record for record in records if record.category == category]
        if result:
            records = [record for record in records if record.result == result]
        return records

    def last(self, n: int) -> list[JournalRecord]:
        records = self.read_all()
        return records[-n:] if len(records) > n else records

    def cleanup(self, retention_days: int = 30) -> int:
        del retention_days
        return 0


def read_all(jobs_root: Path | None = None) -> list[JournalRecord]:
    """Return all ledger-derived journal records in chronological order."""
    records = _read_all_records(jobs_root=jobs_root)
    records.sort(key=lambda record: _parse_time(record.timestamp) or _MIN_TIME)
    return records


def read_recent_runs(
    loop: str | None = None,
    category: str | None = None,
    limit: int = 100,
    jobs_root: Path | None = None,
) -> list[JournalRecord]:
    """Return recent journal-shaped records derived from ledger jobs."""
    records = _read_all_records(jobs_root=jobs_root)
    if loop:
        records = [record for record in records if record.loop == loop]
    if category:
        records = [record for record in records if record.category == category]
    records.sort(key=lambda record: _parse_time(record.timestamp) or _MIN_TIME, reverse=True)
    if limit > 0:
        records = records[:limit]
    return records


def read_all_for_loop(loop: str, jobs_root: Path | None = None) -> list[JournalRecord]:
    """Return all ledger-derived records for one adaptive loop."""
    records = [record for record in _read_all_records(jobs_root=jobs_root) if record.loop == loop]
    records.sort(key=lambda record: _parse_time(record.timestamp) or _MIN_TIME)
    return records


def _append_journal_record(entry: JournalRecord) -> None:
    """Append one journal-shaped event to the active ADR-743 job, if any."""
    try:
        from job_ledger import job_record as active_job_record
        from job_ledger.ledger import current_job_dir

        job_dir = current_job_dir()
        if job_dir is None:
            return
        payload = asdict(entry)
        payload = {key: value for key, value in payload.items() if value is not None}
        payload["type"] = "journal_record"
        payload["state"] = "running"
        payload["t"] = entry.timestamp or datetime.now(timezone.utc).isoformat()
        active_job_record.append_event(job_dir, payload)
    except Exception:
        return


def _read_all_records(jobs_root: Path | None = None) -> list[JournalRecord]:
    root = jobs_root or job_record.jobs_dir()
    if not root.is_dir():
        return []

    records: list[JournalRecord] = []
    for job_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        if job_dir.name == "_archive":
            continue
        meta = job_record.read_meta(job_dir)
        kind = str(meta.get("kind") or "")
        if kind not in {"loop", "dream", "routine-orchestrator"}:
            continue
        events = job_record.read_events(job_dir)
        journal_events = [
            event for event in events
            if isinstance(event, dict) and event.get("type") == "journal_record"
        ]
        if journal_events:
            records.extend(
                _record_from_journal_event(event, meta, job_id=job_dir.name)
                for event in journal_events
            )
        else:
            summary = _summary_from_job(meta, events, job_id=job_dir.name)
            if summary is not None:
                records.append(summary)
    return records


def _record_from_journal_event(
    event: dict[str, Any],
    meta: dict[str, Any],
    *,
    job_id: str,
) -> JournalRecord:
    state = str(event.get("state") or "")
    return JournalRecord(
        loop=str(event.get("loop") or meta.get("name") or ""),
        action=str(event.get("action") or "run"),
        category=str(event.get("category") or "engine"),
        result=str(event.get("result") or _result_from_state(state)),
        timestamp=str(event.get("timestamp") or event.get("t") or meta.get("created_at") or ""),
        files=list(event["files"]) if isinstance(event.get("files"), list) else None,
        commit=str(event["commit"]) if event.get("commit") is not None else None,
        error=str(event["error"]) if event.get("error") is not None else None,
        duration_ms=int(event.get("duration_ms") or 0),
        job_id=None,
        kind=None,
        name=None,
        state=None,
        created_at=None,
    )


def _summary_from_job(
    meta: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    job_id: str,
) -> JournalRecord | None:
    if not events:
        return None
    terminal = _terminal_event(events) or events[-1]
    created_at = str(meta.get("created_at") or "")
    timestamp = str(terminal.get("t") or created_at)
    error = _format_error(terminal)
    kind = str(meta.get("kind") or "")
    name = str(meta.get("name") or "")
    state = str(terminal.get("state") or "")
    metadata = (
        {
            "job_id": job_id,
            "kind": kind or None,
            "name": name or None,
            "state": state or None,
            "created_at": created_at or None,
        }
        if kind in {"dream", "routine-orchestrator"}
        else {}
    )
    return JournalRecord(
        loop=_loop_name(kind, name, meta),
        action="run",
        category="engine",
        result=_result_from_state(state),
        timestamp=timestamp,
        files=None,
        commit=_extract_commit(events),
        error=error,
        duration_ms=_duration_ms(created_at, timestamp, events),
        **metadata,
    )


def _loop_name(kind: str, name: str, meta: dict[str, Any]) -> str:
    if kind == "dream":
        return "dream"
    if kind == "routine-orchestrator":
        args = meta.get("args")
        if isinstance(args, dict) and args.get("loop"):
            return str(args["loop"])
        if name.startswith("routine:"):
            return name.split(":", 1)[1]
    return name


def _terminal_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        state = str(event.get("state") or "")
        if job_record.is_terminal(state):
            return event
    return None


def _result_from_state(state: str) -> str:
    return "success" if state == "complete" else "failure"


def _format_error(event: dict[str, Any]) -> str | None:
    state = str(event.get("state") or "")
    if state == "complete":
        return None
    error = event.get("error")
    msg = event.get("msg") or event.get("reason")
    if error and msg:
        return f"{error}: {msg}"
    if error:
        return str(error)
    if msg:
        return str(msg)
    return None


def _extract_commit(events: list[dict[str, Any]]) -> str | None:
    for event in reversed(events):
        commit = event.get("commit")
        if commit:
            return str(commit)
    return None


def _duration_ms(created_at: str, timestamp: str, events: list[dict[str, Any]]) -> int:
    start = _parse_time(created_at)
    end = _parse_time(timestamp)
    if start is None:
        times = [_parse_time(str(event.get("t") or "")) for event in events]
        valid = [time for time in times if time is not None]
        if valid:
            start = min(valid)
            end = max(valid)
    if start is None or end is None:
        return 0
    return max(0, int((end - start).total_seconds() * 1000))


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


_MIN_TIME = datetime.fromtimestamp(0, tz=timezone.utc)
