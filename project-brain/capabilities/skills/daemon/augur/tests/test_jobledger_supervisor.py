"""Tests for job_ledger/supervisor.py -- file-based job ledger (ADR-743)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

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
    sys.modules[module_name] = module  # alias bare name so siblings resolve
    spec.loader.exec_module(module)
    return module


def test_orphaned_job_marked_failed(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    sup = _load("supervisor", "supervisor.py")
    monkeypatch.setattr(sup, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(sup, "_surface", lambda *a, **k: None)
    job_dir = jr.jobs_dir() / "20260514-120000-000-orphan"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "running", "pid": 4242})
    result = sup.sweep(config={"heartbeat_threshold_s": 300, "resubmit_allowlist": []})
    assert jr.current_state(job_dir) == "failed"
    assert result["orphaned"] == 1


def test_live_job_with_fresh_heartbeat_left_alone(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    sup = _load("supervisor", "supervisor.py")
    monkeypatch.setattr(sup, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(sup, "_surface", lambda *a, **k: None)
    job_dir = jr.jobs_dir() / "20260514-120000-000-live"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "running", "pid": 4242, "heartbeat": True})
    sup.sweep(config={"heartbeat_threshold_s": 300, "resubmit_allowlist": []})
    assert jr.current_state(job_dir) == "running"
