"""Append-only JSONL queue of notes pending article enrichment.

The queue file lives under runtime state, resolved by callers. This module
accepts the queue path explicitly so the queue logic stays pure and testable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def enqueue(queue_path: Path, *, note_path: Path, reason: str) -> bool:
    """Append a note to the pending queue unless the note path is already queued."""
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    note_path_text = str(note_path)
    existing = {entry["note_path"] for entry in read_pending(queue_path)}
    if note_path_text in existing:
        return False

    entry = {
        "note_path": note_path_text,
        "reason": reason,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }
    with queue_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return True


def read_pending(queue_path: Path) -> list[dict[str, Any]]:
    """Read valid pending queue entries, skipping missing files and bad JSONL lines."""
    if not queue_path.exists():
        return []

    entries: list[dict[str, Any]] = []
    with queue_path.open(encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "note_path" in payload:
                entries.append(payload)
    return entries


def drain(queue_path: Path, processed_note_paths: Iterable[Path]) -> int:
    """Remove processed entries by rewriting the queue file. Return the count removed."""
    if not queue_path.exists():
        return 0

    entries = read_pending(queue_path)
    processed = {str(path) for path in processed_note_paths}
    remaining = [entry for entry in entries if entry["note_path"] not in processed]
    removed = len(entries) - len(remaining)

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = queue_path.with_suffix(f"{queue_path.suffix}.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        for entry in remaining:
            fh.write(json.dumps(entry) + "\n")
    tmp_path.replace(queue_path)
    return removed
