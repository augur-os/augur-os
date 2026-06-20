"""Adaptive engine can read journal-shaped records from the job ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from adaptive.engine import AdaptiveLoopEngine
from job_ledger import job_record


def test_engine_uses_ledger_view_reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    jobs_dir = tmp_path / "jobs"
    job_dir = jobs_dir / "20260516-100000-000-testing"
    job_dir.mkdir(parents=True)
    (job_dir / "meta.json").write_text(
        json.dumps(
            {
                "job_id": job_dir.name,
                "kind": "loop",
                "name": "testing",
                "created_at": "2026-05-16T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "type": "journal_record",
                "loop": "testing",
                "action": "fix",
                "category": "auto-test-pytest",
                "result": "failure",
                "timestamp": "2026-05-16T10:00:00+00:00",
                "error": "boom",
                "duration_ms": 10,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(job_record, "jobs_dir", lambda: jobs_dir)

    engine = AdaptiveLoopEngine({"engine": {}}, runtime_dir=tmp_path, project_root=tmp_path)

    entries = engine.journal_reader.read_all()
    assert [(entry.loop, entry.category, entry.result, entry.error) for entry in entries] == [
        ("testing", "auto-test-pytest", "failure", "boom")
    ]
    assert engine._recent_category_failures("testing", "auto-test-pytest") == [
        {
            "timestamp": "2026-05-16T10:00:00+00:00",
            "action": "fix",
            "error": "boom",
        }
    ]
