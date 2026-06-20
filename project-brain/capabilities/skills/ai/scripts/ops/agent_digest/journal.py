# skills/auto-agent-digest/scripts/journal.py
"""Event journal I/O for the agent-digest nightly loop.

Append-only JSONL journal at {runtime_dir}/agent-digest/events.jsonl.
Supports read with time window filtering, archive to .gz, and retention purge.
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _journal_path(journal_dir: Path) -> Path:
    return journal_dir / "events.jsonl"


def _fingerprint(event: dict) -> str:
    """Stable fingerprint for dedup: (source, type, rule, commit|session, evidence|signal)."""
    parts = [
        event.get("source", ""),
        event.get("type", ""),
        event.get("rule", ""),
        event.get("commit", event.get("session", "")),
        event.get("evidence", event.get("signal", event.get("note", ""))),
    ]
    return "|".join(parts)


def _load_seen(journal_dir: Path) -> set[str]:
    """Load fingerprints of events already in the journal."""
    path = _journal_path(journal_dir)
    if not path.exists():
        return set()
    seen = set()
    for line in path.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            seen.add(_fingerprint(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            continue
    return seen


def append_event(journal_dir: Path, event: dict, *, dedup: bool = True) -> bool:
    """Append a single event to the journal. Creates file if needed.

    When dedup=True (default), skips events whose fingerprint already exists.
    Returns True if the event was written, False if deduplicated away.
    """
    journal_dir.mkdir(parents=True, exist_ok=True)
    if dedup:
        seen = _load_seen(journal_dir)
        if _fingerprint(event) in seen:
            return False
    with _journal_path(journal_dir).open("a") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")
    return True


def read_events(
    journal_dir: Path,
    since: datetime | None = None,
) -> list[dict]:
    """Read events from journal, optionally filtered to those after `since`."""
    path = _journal_path(journal_dir)
    if not path.exists():
        return []
    events = []
    for line in path.read_text().strip().split("\n"):
        if not line:
            continue
        event = json.loads(line)
        if since is not None:
            ts = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            if ts < since:
                continue
        events.append(event)
    return events


def archive_old(journal_dir: Path, date_str: str) -> Path | None:
    """Move current journal to a dated gzip archive. Returns archive path."""
    src = _journal_path(journal_dir)
    if not src.exists() or src.stat().st_size == 0:
        return None
    archive = journal_dir / f"events.{date_str}.jsonl.gz"
    with src.open("r") as fin, gzip.open(archive, "wt") as fout:
        fout.write(fin.read())
    src.write_text("")
    return archive


def purge_archives(
    journal_dir: Path,
    retention_days: int = 30,
    reference_date: datetime | None = None,
) -> list[Path]:
    """Remove archives older than retention_days. Returns list of purged paths."""
    ref = reference_date or datetime.now(timezone.utc)
    cutoff = ref - timedelta(days=retention_days)
    purged = []
    for gz in sorted(journal_dir.glob("events.*.jsonl.gz")):
        date_part = gz.name.replace("events.", "").replace(".jsonl.gz", "")
        try:
            archive_date = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if archive_date < cutoff:
            gz.unlink()
            purged.append(gz)
    return purged
