"""Tests for ADR-757 ledger-derived adaptive journal view."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from job_ledger import job_record, ledger
from routine_orchestrator import ledger_view


@pytest.fixture(autouse=True)
def _isolated_jobs_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    jobs = tmp_path / "jobs"
    monkeypatch.setattr(job_record, "jobs_dir", lambda: jobs)
    return jobs


def _write_job(
    jobs: Path,
    job_id: str,
    *,
    name: str,
    created_at: str,
    events: list[dict],
    args: dict | None = None,
    kind: str = "loop",
) -> Path:
    job_dir = jobs / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "meta.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "kind": kind,
                "name": name,
                "submitter": "pytest",
                "args": args or {},
                "declared_timeout_s": 600,
                "created_at": created_at,
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    return job_dir


def _record_dict(record) -> dict:
    payload = asdict(record)
    return {key: value for key, value in payload.items() if value is not None}


def test_translator_reduces_per_phase_events_to_one_run_summary(_isolated_jobs_dir: Path) -> None:
    _write_job(
        _isolated_jobs_dir,
        "20260516-100000-000-testing",
        name="testing",
        created_at="2026-05-16T10:00:00+00:00",
        events=[
            {"state": "pending", "t": "2026-05-16T10:00:00+00:00"},
            {"state": "running", "phase": "scan", "t": "2026-05-16T10:00:01+00:00"},
            {"state": "running", "phase": "fix", "t": "2026-05-16T10:00:02+00:00"},
            {"state": "complete", "t": "2026-05-16T10:00:03+00:00"},
        ],
    )

    records = ledger_view.read_recent_runs()

    assert [_record_dict(record) for record in records] == [
        {
            "loop": "testing",
            "action": "run",
            "category": "engine",
            "result": "success",
            "timestamp": "2026-05-16T10:00:03+00:00",
            "duration_ms": 3000,
        }
    ]


def test_ledger_writer_appends_journal_record_events(
    _isolated_jobs_dir: Path,
    tmp_path: Path,
) -> None:
    with ledger.run(kind="loop", name="testing", args={"mode": "run"}) as job:
        job.phase("dispatch")
        entry = ledger_view.LedgerJournalWriter(tmp_path / "adaptive").log(
            loop="testing",
            action="fix",
            category="auto-test-pytest",
            result="success",
            files=["project-brain/capabilities/skills/daemon/augur/tests/test_ledger_view.py"],
            commit="abc1234",
            duration_ms=42,
        )

    ledger_records = [asdict(record) for record in ledger_view.read_recent_runs()]

    assert ledger_records == [asdict(entry)]
    assert len(job_record.read_events(Path(job.job_dir))) >= 4


def test_translator_handles_failed_runs(_isolated_jobs_dir: Path) -> None:
    _write_job(
        _isolated_jobs_dir,
        "20260516-100100-000-testing",
        name="testing",
        created_at="2026-05-16T10:01:00+00:00",
        events=[
            {"state": "pending", "t": "2026-05-16T10:01:00+00:00"},
            {"state": "running", "t": "2026-05-16T10:01:01+00:00"},
            {
                "state": "failed",
                "error": "RuntimeError",
                "msg": "boom",
                "t": "2026-05-16T10:01:04+00:00",
            },
        ],
    )

    records = ledger_view.read_recent_runs()

    assert len(records) == 1
    assert records[0].result == "failure"
    assert records[0].error == "RuntimeError: boom"
    assert records[0].duration_ms == 4000


def test_translator_filters_by_loop_and_category(_isolated_jobs_dir: Path) -> None:
    _write_job(
        _isolated_jobs_dir,
        "20260516-100000-000-testing",
        name="testing",
        created_at="2026-05-16T10:00:00+00:00",
        events=[
            {
                "type": "journal_record",
                "loop": "testing",
                "action": "fix",
                "category": "auto-test-pytest",
                "result": "success",
                "timestamp": "2026-05-16T10:00:00+00:00",
                "duration_ms": 1,
            }
        ],
    )
    _write_job(
        _isolated_jobs_dir,
        "20260516-100100-000-hardening",
        name="hardening",
        created_at="2026-05-16T10:01:00+00:00",
        events=[
            {
                "type": "journal_record",
                "loop": "hardening",
                "action": "fix",
                "category": "auto-test-pytest",
                "result": "success",
                "timestamp": "2026-05-16T10:01:00+00:00",
                "duration_ms": 1,
            }
        ],
    )
    _write_job(
        _isolated_jobs_dir,
        "20260516-100200-000-testing",
        name="testing",
        created_at="2026-05-16T10:02:00+00:00",
        events=[
            {
                "type": "journal_record",
                "loop": "testing",
                "action": "fix",
                "category": "auto-lint",
                "result": "success",
                "timestamp": "2026-05-16T10:02:00+00:00",
                "duration_ms": 1,
            }
        ],
    )

    records = ledger_view.read_recent_runs(loop="testing", category="auto-test-pytest")

    assert [(record.loop, record.category) for record in records] == [
        ("testing", "auto-test-pytest")
    ]


def test_translator_recent_runs_orders_by_creation_descending(_isolated_jobs_dir: Path) -> None:
    for day in range(1, 6):
        _write_job(
            _isolated_jobs_dir,
            f"202605{day:02d}-100000-000-testing",
            name="testing",
            created_at=f"2026-05-{day:02d}T10:00:00+00:00",
            events=[
                {
                    "state": "complete",
                    "t": f"2026-05-{day:02d}T10:01:00+00:00",
                }
            ],
        )

    records = ledger_view.read_recent_runs(limit=3)

    assert [record.timestamp for record in records] == [
        "2026-05-05T10:01:00+00:00",
        "2026-05-04T10:01:00+00:00",
        "2026-05-03T10:01:00+00:00",
    ]


def test_translator_includes_dream_jobs_as_dream_routine_runs(_isolated_jobs_dir: Path) -> None:
    _write_job(
        _isolated_jobs_dir,
        "20260516-040000-000-dream-cycle",
        kind="dream",
        name="dream-cycle",
        created_at="2026-05-16T04:00:00+00:00",
        events=[
            {"state": "running", "t": "2026-05-16T04:00:01+00:00"},
            {"state": "complete", "t": "2026-05-16T04:00:05+00:00"},
        ],
    )

    records = ledger_view.read_recent_runs(loop="dream")

    assert len(records) == 1
    assert records[0].loop == "dream"
    assert records[0].kind == "dream"
    assert records[0].name == "dream-cycle"
    assert records[0].job_id == "20260516-040000-000-dream-cycle"
    assert records[0].state == "complete"
    assert records[0].result == "success"


def test_translator_includes_routine_orchestrator_jobs_as_routine_runs(
    _isolated_jobs_dir: Path,
) -> None:
    _write_job(
        _isolated_jobs_dir,
        "20260530-002151-430-000-routine-duplication",
        kind="routine-orchestrator",
        name="routine:duplication",
        created_at="2026-05-30T00:21:51+00:00",
        args={"loop": "duplication"},
        events=[
            {"state": "pending", "t": "2026-05-30T00:21:51+00:00"},
            {"state": "running", "phase": "scan", "t": "2026-05-30T00:21:52+00:00"},
            {"state": "complete", "t": "2026-05-30T00:21:53+00:00"},
        ],
    )

    records = ledger_view.read_recent_runs(loop="duplication")

    assert len(records) == 1
    assert records[0].loop == "duplication"
    assert records[0].kind == "routine-orchestrator"
    assert records[0].name == "routine:duplication"
    assert records[0].job_id == "20260530-002151-430-000-routine-duplication"
    assert records[0].state == "complete"
    assert records[0].result == "success"
