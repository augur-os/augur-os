from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[2] / "scripts" / "job_ledger"


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, MODULE_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_new_job_id_is_sortable_and_slugged() -> None:
    jr = _load("job_record", "job_record.py")
    jid = jr.new_job_id("routine-vault")
    assert jid.endswith("-routine-vault")
    assert len(jid.split("-")[0]) == 8


def test_append_and_current_state(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    job_dir = jr.jobs_dir() / "20260514-120000-000-test"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "pending"})
    jr.append_event(job_dir, {"state": "running", "pid": 999})
    jr.append_event(job_dir, {"state": "complete"})
    assert jr.current_state(job_dir) == "complete"
    assert jr.is_terminal("complete") and not jr.is_terminal("running")


def test_corrupt_line_is_skipped(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    job_dir = jr.jobs_dir() / "20260514-120000-000-test"
    job_dir.mkdir(parents=True)
    (job_dir / "events.jsonl").write_text(
        '{"state": "running"}\n{not valid json\n{"state": "failed"}\n',
        encoding="utf-8",
    )
    assert jr.current_state(job_dir) == "failed"
    assert len(jr.read_events(job_dir)) == 2
