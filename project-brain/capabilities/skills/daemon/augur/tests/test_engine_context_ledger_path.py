"""Engine context collector can source recent history from the job ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from adaptive.engine_context import collect_context
from job_ledger import job_record


def test_collect_context_reads_recent_journal_from_ledger_view(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target_dir = tmp_path / "src" / "scheduler"
    target_dir.mkdir(parents=True)
    (target_dir / "ownership.py").write_text("def check():\n    return 'needs design'\n", encoding="utf-8")
    (target_dir / "README.md").write_text("---\ntitle: Scheduler\n---\nLocal context.\n", encoding="utf-8")

    loop_ref_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "daemon" / "references"
    loop_ref_dir.mkdir(parents=True)
    (loop_ref_dir / "routines-implementation.md").write_text(
        "---\ntitle: Dev Loops\n---\nLoop context.\n",
        encoding="utf-8",
    )

    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-999-test.md").write_text("---\ntitle: Test\n---\nDesign.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "test.md").write_text("---\ntitle: Test\n---\nWiki.\n", encoding="utf-8")
    runtime_dir = tmp_path / "runtime" / "adaptive"
    (runtime_dir / "reports").mkdir(parents=True)
    (runtime_dir / "reports" / "testing-latest.json").write_text(
        '{"summary": "testing report", "next_actions": ["fix pytest"]}',
        encoding="utf-8",
    )

    jobs_dir = tmp_path / "runtime" / "jobs"
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

    context = collect_context(
        issue={"path": "src/scheduler/ownership.py", "ownership_change": True},
        project_root=tmp_path,
        loop_name="testing",
        adr_dir=adr_dir,
        wiki_dir=wiki_dir,
        runtime_dir=runtime_dir,
    )

    recent = [source for source in context["sources"] if source["kind"] == "recent-ledger"]
    assert recent == [
        {
            "kind": "recent-ledger",
            "path": str((runtime_dir.parent / "jobs").relative_to(tmp_path)),
            "title": "testing recent ledger history",
            "excerpt": "failure:fix auto-test-pytest — boom",
        }
    ]
