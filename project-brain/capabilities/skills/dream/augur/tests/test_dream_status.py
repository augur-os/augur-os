"""Tests for dream-status (ADR-744 task 7).

dream-status reads the ADR-743 job ledger (a directory of per-job dirs each
holding meta.json + events.jsonl) and returns the latest ``kind == "dream"``
run + a short history.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dream_status.py"
_SPEC = importlib.util.spec_from_file_location("dream_status", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write_job(
    jobs_root: Path,
    job_id: str,
    *,
    kind: str = "dream",
    name: str = "dream-cycle",
    states: list[str] | None = None,
) -> Path:
    """Lay down a single job directory under the ledger root."""
    if states is None:
        states = ["running", "complete"]
    job_dir = jobs_root / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "meta.json").write_text(
        json.dumps({"kind": kind, "name": name, "created_at": job_id[:8]}),
        encoding="utf-8",
    )
    with (job_dir / "events.jsonl").open("w", encoding="utf-8") as fh:
        for state in states:
            fh.write(json.dumps({"state": state, "t": f"2026-05-14T04:00:0{len(state)}Z"}) + "\n")
    return job_dir


@pytest.fixture
def jobs_root(tmp_path: Path) -> Path:
    root = tmp_path / "runtime" / "jobs"
    root.mkdir(parents=True)
    return root


def test_returns_latest_dream_job(jobs_root: Path):
    _write_job(jobs_root, "20260512-040000-001-001-dream-cycle")
    _write_job(jobs_root, "20260514-040000-001-002-dream-cycle")
    _write_job(jobs_root, "20260513-040000-001-003-dream-cycle")

    result = mod.dream_status(jobs_root=jobs_root)
    assert result["latest"] is not None
    assert result["latest"]["job_id"].startswith("20260514")
    assert result["latest"]["state"] == "complete"


def test_delegates_to_unified_routine_status_view(monkeypatch: pytest.MonkeyPatch, jobs_root: Path):
    calls = []

    class _StatusView:
        @staticmethod
        def routine_status_payload(**kwargs):
            calls.append(kwargs)
            return {
                "success": True,
                "routines": [
                    {
                        "recent_runs": [
                            {
                                "job_id": "dream-job",
                                "name": "dream",
                                "state": "complete",
                                "created_at": "2026-05-16T04:00:00Z",
                            }
                        ]
                    }
                ],
            }

    monkeypatch.setattr(mod, "_load_status_view", lambda: _StatusView)

    result = mod.dream_status(jobs_root=jobs_root, history_limit=3)

    assert calls == [{"routine_id": "dream", "limit": 3, "jobs_root": jobs_root}]
    assert result["latest"]["job_id"] == "dream-job"


def test_filters_out_non_dream_kinds(jobs_root: Path):
    _write_job(jobs_root, "20260514-040000-001-001-dream-cycle", kind="dream")
    _write_job(jobs_root, "20260514-050000-001-001-self-heal", kind="self-heal")

    result = mod.dream_status(jobs_root=jobs_root)
    assert result["latest"]["job_id"].startswith("20260514-040000")
    assert all(entry["job_id"].endswith("dream-cycle") for entry in result["history"])


def test_distinguishes_in_progress_vs_completed_vs_failed(jobs_root: Path):
    _write_job(jobs_root, "20260514-040000-001-001-dream-cycle", states=["running"])
    _write_job(jobs_root, "20260514-040000-001-002-dream-cycle", states=["running", "complete"])
    _write_job(jobs_root, "20260514-040000-001-003-dream-cycle", states=["running", "failed"])

    result = mod.dream_status(jobs_root=jobs_root)
    history_states = {entry["job_id"]: entry["state"] for entry in result["history"]}
    assert "running" in history_states.values()
    assert "complete" in history_states.values()
    assert "failed" in history_states.values()


def test_returns_empty_history_when_no_dream_jobs(jobs_root: Path):
    _write_job(jobs_root, "20260514-050000-001-001-self-heal", kind="self-heal")
    result = mod.dream_status(jobs_root=jobs_root)
    assert result["latest"] is None
    assert result["history"] == []


def test_handles_missing_ledger_gracefully(tmp_path: Path):
    """Pre-ADR-743 systems may not have a jobs dir yet."""
    missing = tmp_path / "runtime" / "jobs-not-yet"
    result = mod.dream_status(jobs_root=missing)
    assert result == {"latest": None, "history": []}
