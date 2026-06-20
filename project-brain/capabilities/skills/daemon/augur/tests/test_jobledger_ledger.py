from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_DIR = Path(__file__).resolve().parents[2] / "scripts" / "job_ledger"


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, MODULE_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _patch_jobs_dir(monkeypatch, tmp_path: Path):
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    return jr


def test_clean_run_records_running_then_complete(tmp_path: Path, monkeypatch) -> None:
    jr = _patch_jobs_dir(monkeypatch, tmp_path)
    ledger = _load("ledger", "ledger.py")
    with ledger.run(kind="loop", name="routine-vault", timeout_s=600) as job:
        job.phase("scan")
        job.heartbeat()
    states = [e["state"] for e in jr.read_events(Path(job.job_dir))]
    assert states[0] == "pending" and states[1] == "running"
    assert states[-1] == "complete"
    assert (Path(job.job_dir) / "output").is_dir()
    assert any(e.get("phase") == "scan" for e in jr.read_events(Path(job.job_dir)))


def test_exception_records_failed_and_reraises(tmp_path: Path, monkeypatch) -> None:
    jr = _patch_jobs_dir(monkeypatch, tmp_path)
    ledger = _load("ledger", "ledger.py")
    with pytest.raises(ValueError):
        with ledger.run(kind="loop", name="boom") as job:
            raise ValueError("kaboom")
    events = jr.read_events(Path(job.job_dir))
    assert events[-1]["state"] == "failed"
    assert events[-1]["error"] == "ValueError"


def test_cooperative_cancel(tmp_path: Path, monkeypatch) -> None:
    jr = _patch_jobs_dir(monkeypatch, tmp_path)
    ledger = _load("ledger", "ledger.py")
    with ledger.run(kind="loop", name="cancelme") as job:
        (Path(job.job_dir) / "cancel_requested").write_text("", encoding="utf-8")
        with pytest.raises(ledger.JobCancelled):
            job.heartbeat()
    assert jr.current_state(Path(job.job_dir)) == "cancelled"


def test_ledger_write_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: (_ for _ in ()).throw(OSError("disk full")))
    ledger = _load("ledger", "ledger.py")
    ran = False
    with ledger.run(kind="loop", name="resilient") as job:
        ran = True
    assert ran
