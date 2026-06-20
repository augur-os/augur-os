"""Tests for ADR-755 pending escalation queue."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
DAEMON_DIR = TESTS_DIR.parents[1]
ESCALATION_QUEUE_PATH = (
    DAEMON_DIR / "scripts" / "routine_orchestrator" / "escalation_queue.py"
)


def _load_escalation_queue():
    spec = importlib.util.spec_from_file_location(
        "routine_orchestrator_escalation_queue",
        ESCALATION_QUEUE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_enqueue_writes_to_pending_jsonl(tmp_path) -> None:
    queue = _load_escalation_queue()
    finding = {"loop": "testing", "auto_command": "auto-semantic", "path": "x.py"}

    entry = queue.enqueue(finding, runtime_dir=tmp_path, now="2026-05-16T10:00:00+00:00")

    pending_path = tmp_path / "jobs" / "_escalations" / "pending.jsonl"
    rows = _read_jsonl(pending_path)
    assert len(rows) == 1
    assert rows[0]["id"] == entry["id"]
    assert rows[0]["finding"] == finding
    assert rows[0]["created_at"] == "2026-05-16T10:00:00+00:00"
    assert rows[0]["updated_at"] == "2026-05-16T10:00:00+00:00"
    assert rows[0]["ttl_seconds"] == 14 * 24 * 60 * 60
    assert rows[0]["expires_at"] == "2026-05-30T10:00:00+00:00"


def test_enqueue_defaults_to_runtime_jobs_escalations(monkeypatch, tmp_path) -> None:
    queue = _load_escalation_queue()
    monkeypatch.setattr(queue, "_default_runtime_dir", lambda: tmp_path)

    queue.enqueue({"name": "default-path"}, now="2026-05-16T10:00:00+00:00")

    pending_path = tmp_path / "jobs" / "_escalations" / "pending.jsonl"
    assert _read_jsonl(pending_path)[0]["finding"] == {"name": "default-path"}


def test_enqueue_allows_direct_path_injection(tmp_path) -> None:
    queue = _load_escalation_queue()
    injected_path = tmp_path / "custom" / "pending.jsonl"

    queue.enqueue(
        {"name": "path-injected"},
        path=injected_path,
        now="2026-05-16T10:00:00+00:00",
    )

    assert _read_jsonl(injected_path)[0]["finding"] == {"name": "path-injected"}


def test_dequeue_returns_entries_under_ttl(tmp_path) -> None:
    queue = _load_escalation_queue()
    now = datetime(2026, 5, 16, 10, tzinfo=timezone.utc)
    stale = now - timedelta(days=15)
    fresh_a = now - timedelta(days=2)
    fresh_b = now - timedelta(seconds=1)

    queue.enqueue({"name": "stale"}, runtime_dir=tmp_path, now=stale)
    fresh_entry_a = queue.enqueue({"name": "fresh-a"}, runtime_dir=tmp_path, now=fresh_a)
    fresh_entry_b = queue.enqueue({"name": "fresh-b"}, runtime_dir=tmp_path, now=fresh_b)

    entries = queue.dequeue(runtime_dir=tmp_path, now=now)

    assert [entry["id"] for entry in entries] == [
        fresh_entry_a["id"],
        fresh_entry_b["id"],
    ]
    assert [entry["finding"]["name"] for entry in entries] == ["fresh-a", "fresh-b"]


def test_dequeue_drops_stale_entries_and_records_ledger_event(tmp_path) -> None:
    queue = _load_escalation_queue()
    events: list[dict] = []
    now = datetime(2026, 5, 16, 10, tzinfo=timezone.utc)
    stale_entry = queue.enqueue(
        {"name": "stale"},
        runtime_dir=tmp_path,
        now=now - timedelta(days=15),
    )
    fresh_entry = queue.enqueue({"name": "fresh"}, runtime_dir=tmp_path, now=now)

    entries = queue.dequeue(runtime_dir=tmp_path, now=now, on_event=events.append)

    assert [entry["id"] for entry in entries] == [fresh_entry["id"]]
    assert _read_jsonl(tmp_path / "jobs" / "_escalations" / "pending.jsonl") == [
        fresh_entry
    ]
    assert events == [
        {
            "event": "escalation_queue_stale_drop",
            "entry_id": stale_entry["id"],
            "dropped_at": "2026-05-16T10:00:00+00:00",
            "reason": "ttl_expired",
        }
    ]


def test_pick_up_marks_entry_in_progress_atomically(tmp_path) -> None:
    queue = _load_escalation_queue()
    entry = queue.enqueue({"name": "semantic"}, runtime_dir=tmp_path)

    first = queue.pick_up(entry["id"], runtime_dir=tmp_path, worker_id="worker-a")
    second = queue.pick_up(entry["id"], runtime_dir=tmp_path, worker_id="worker-b")

    assert first is not None
    assert first["id"] == entry["id"]
    assert second is None
    picked_up_rows = _read_jsonl(tmp_path / "jobs" / "_escalations" / "picked_up.jsonl")
    assert len(picked_up_rows) == 1
    assert picked_up_rows[0]["id"] == entry["id"]
    assert picked_up_rows[0]["worker_id"] == "worker-a"
    assert picked_up_rows[0]["picked_up_at"]


def test_malformed_line_is_skipped_not_fatal(tmp_path) -> None:
    queue = _load_escalation_queue()
    events: list[dict] = []
    pending_path = tmp_path / "jobs" / "_escalations" / "pending.jsonl"
    pending_path.parent.mkdir(parents=True)
    valid_entry = queue.build_entry(
        {"name": "valid"},
        now="2026-05-16T10:00:00+00:00",
    )
    pending_path.write_text(
        "{not-json}\n" + json.dumps(valid_entry, sort_keys=True) + "\n",
    )

    entries = queue.dequeue(
        runtime_dir=tmp_path,
        now="2026-05-16T10:01:00+00:00",
        on_event=events.append,
    )

    assert [entry["id"] for entry in entries] == [valid_entry["id"]]
    assert events == [
        {
            "event": "escalation_queue_malformed_line",
            "line_number": 1,
            "reason": "json_decode_error",
        }
    ]


def test_malformed_timestamp_is_skipped_not_fatal(tmp_path) -> None:
    queue = _load_escalation_queue()
    events: list[dict] = []
    pending_path = tmp_path / "jobs" / "_escalations" / "pending.jsonl"
    pending_path.parent.mkdir(parents=True)
    valid_entry = queue.build_entry(
        {"name": "valid"},
        now="2026-05-16T10:00:00+00:00",
    )
    invalid_entry = dict(valid_entry)
    invalid_entry["id"] = "bad-time"
    invalid_entry["expires_at"] = "not-a-date"
    pending_path.write_text(
        json.dumps(invalid_entry, sort_keys=True) + "\n"
        + json.dumps(valid_entry, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    entries = queue.dequeue(
        runtime_dir=tmp_path,
        now="2026-05-16T10:01:00+00:00",
        on_event=events.append,
    )

    assert [entry["id"] for entry in entries] == [valid_entry["id"]]
    assert events == [
        {
            "event": "escalation_queue_malformed_line",
            "entry_id": "bad-time",
            "reason": "invalid_timestamp",
        }
    ]


def test_complete_removes_success_entry_from_pending(tmp_path) -> None:
    queue = _load_escalation_queue()
    first = queue.enqueue({"name": "first"}, runtime_dir=tmp_path)
    second = queue.enqueue({"name": "second"}, runtime_dir=tmp_path)

    assert queue.complete(first["id"], runtime_dir=tmp_path) is True
    assert queue.complete("missing", runtime_dir=tmp_path) is False

    pending_path = tmp_path / "jobs" / "_escalations" / "pending.jsonl"
    assert _read_jsonl(pending_path) == [second]
