# skills/auto-agent-digest/augur/tests/test_journal.py
"""Tests for the event journal I/O module."""

from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add scripts dir to sys.path so we can import journal directly
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops" / "agent_digest")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from journal import (  # noqa: E402
    append_event,
    archive_old,
    purge_archives,
    read_events,
)


@pytest.fixture
def journal_dir(tmp_path: Path) -> Path:
    d = tmp_path / "agent-digest"
    d.mkdir()
    return d


def test_append_event_creates_file(journal_dir: Path):
    event = {
        "ts": "2026-03-24T02:00:00Z",
        "source": "git",
        "type": "pattern_violation",
        "rule": "rule_11_no_fs",
        "evidence": "import fs in dashboard",
    }
    append_event(journal_dir, event)
    journal = journal_dir / "events.jsonl"
    assert journal.exists()
    lines = journal.read_text().strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["rule"] == "rule_11_no_fs"


def test_append_event_appends_to_existing(journal_dir: Path):
    for i in range(3):
        append_event(journal_dir, {"ts": f"2026-03-24T0{i}:00:00Z", "source": "test", "type": "test", "rule": f"rule_{i}"})
    lines = (journal_dir / "events.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3


def test_read_events_filters_by_window(journal_dir: Path):
    old = {"ts": "2026-03-10T00:00:00Z", "source": "git", "type": "test", "rule": "old"}
    recent = {"ts": "2026-03-23T00:00:00Z", "source": "git", "type": "test", "rule": "recent"}
    append_event(journal_dir, old)
    append_event(journal_dir, recent)
    since = datetime(2026, 3, 20, tzinfo=timezone.utc)
    events = read_events(journal_dir, since=since)
    assert len(events) == 1
    assert events[0]["rule"] == "recent"


def test_read_events_empty_journal(journal_dir: Path):
    events = read_events(journal_dir)
    assert events == []


def test_archive_old_compresses_events(journal_dir: Path):
    append_event(journal_dir, {"ts": "2026-03-24T00:00:00Z", "source": "test", "type": "test", "rule": "r1"})
    archive_old(journal_dir, date_str="2026-03-24")
    assert (journal_dir / "events.jsonl").read_text().strip() == ""
    archive = journal_dir / "events.2026-03-24.jsonl.gz"
    assert archive.exists()
    with gzip.open(archive, "rt") as f:
        lines = f.read().strip().split("\n")
    assert len(lines) == 1


def test_purge_archives_removes_old(journal_dir: Path, tmp_path: Path):
    old_archive = journal_dir / "events.2026-01-01.jsonl.gz"
    with gzip.open(old_archive, "wt") as f:
        f.write('{"old": true}\n')
    recent_archive = journal_dir / "events.2026-03-20.jsonl.gz"
    with gzip.open(recent_archive, "wt") as f:
        f.write('{"recent": true}\n')
    purge_archives(journal_dir, retention_days=30, reference_date=datetime(2026, 3, 24, tzinfo=timezone.utc))
    assert not old_archive.exists()
    assert recent_archive.exists()
