"""Tests for job_ledger/jobs_ops.py -- file-based job ledger (ADR-743)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

LEDGER_DIR = Path(__file__).resolve().parents[2] / "scripts" / "job_ledger"


def _load(module_name: str, file_name: str) -> Any:
    full_name = f"jobledger_{module_name}"
    if full_name in sys.modules:
        module = sys.modules[full_name]
        sys.modules[module_name] = module
        return module
    spec = importlib.util.spec_from_file_location(full_name, LEDGER_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_jobs_list_and_detail(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ops = _load("jobs_ops", "jobs_ops.py")
    job_dir = jr.jobs_dir() / "20260514-120000-000-routine-vault"
    job_dir.mkdir(parents=True)
    (job_dir / "meta.json").write_text(
        '{"job_id": "20260514-120000-000-routine-vault", "name": "routine-vault", "kind": "loop"}',
        encoding="utf-8",
    )
    jr.append_event(job_dir, {"state": "running"})
    jr.append_event(job_dir, {"state": "complete"})

    listing = ops.list_jobs()
    assert len(listing) == 1 and listing[0]["state"] == "complete"
    detail = ops.job_detail("20260514-120000-000-routine-vault")
    assert len(detail["events"]) == 2 and detail["meta"]["name"] == "routine-vault"


def test_jobs_cancel_writes_marker(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ops = _load("jobs_ops", "jobs_ops.py")
    job_dir = jr.jobs_dir() / "20260514-120000-000-cancelme"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "running"})
    result = ops.cancel_job("20260514-120000-000-cancelme")
    assert result["cancel_requested"] is True
    assert (job_dir / "cancel_requested").exists()


def test_jobs_submit_and_replay_create_new_records(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    _load("ledger", "ledger.py")
    ops = _load("jobs_ops", "jobs_ops.py")

    submitted = ops.submit_job(kind="loop", name="routine-vault", timeout_s=30)
    assert submitted["job_id"]
    detail = ops.job_detail(submitted["job_id"])
    assert detail["state"] == "running"

    replayed = ops.replay_job(submitted["job_id"])
    assert replayed["replayed_from"] == submitted["job_id"]
    assert replayed["job_id"] != submitted["job_id"]
