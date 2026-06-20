"""Tests for job_ledger/retention.py -- file-based job ledger (ADR-743)."""
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


def test_old_terminal_jobs_archived_fresh_ones_kept(tmp_path: Path, monkeypatch) -> None:
    import os
    import time

    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ret = _load("retention", "retention.py")

    old = jr.jobs_dir() / "20260101-000000-000-old"
    old.mkdir(parents=True)
    jr.append_event(old, {"state": "complete"})
    (old / "meta.json").write_text('{"job_id": "old"}', encoding="utf-8")
    ancient = time.time() - 60 * 60 * 24 * 40
    os.utime(old / "events.jsonl", (ancient, ancient))

    fresh = jr.jobs_dir() / "20260514-120000-000-fresh"
    fresh.mkdir(parents=True)
    jr.append_event(fresh, {"state": "complete"})

    result = ret.archive(retention_days=30)
    assert result["archived"] == 1
    assert not old.exists()
    assert (jr.jobs_dir() / "_archive" / "old.events.jsonl.gz").exists()
    assert (jr.jobs_dir() / "_archive" / "old.meta.json").exists()
    assert fresh.exists()
