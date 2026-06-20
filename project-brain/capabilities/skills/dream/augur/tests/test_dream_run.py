"""Tests for the ledger-backed dream runner."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dream_run.py"
_SPEC = importlib.util.spec_from_file_location("dream_run", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_dream_run_creates_ledger_jobs_and_report(tmp_path, monkeypatch):
    jobs_root = tmp_path / "runtime" / "jobs"
    vault_root = tmp_path / "vault"
    cache_root = tmp_path / "cache"
    report_root = tmp_path / "reports" / "dream"
    for path in (jobs_root, vault_root, cache_root):
        path.mkdir(parents=True)

    monkeypatch.setattr(mod.job_record, "jobs_dir", lambda: jobs_root)
    monkeypatch.setattr(
        mod,
        "_load_config",
        lambda: {
            "phases": {
                "order": ["orphans", "pattern-extraction", "cache-gc"],
                "skips": [],
            },
            "orphans": {"max_timeline_entries": 3},
            "cache_gc": {"retention_days": 30, "paths": []},
        },
    )
    monkeypatch.setattr(
        mod,
        "_execute_phase",
        lambda phase_id, **_kwargs: {"phase": phase_id, "ok": True},
    )

    result = mod.dream_run(
        vault_root=vault_root,
        cache_root=cache_root,
        report_output_root=report_root,
        iterations=2,
        cache_gc_dry_run=True,
    )

    assert result["count"] == 2
    assert len(result["runs"]) == 2
    assert all(run["state"] == "complete" for run in result["runs"])
    assert all(Path(run["report_path"]).is_file() for run in result["runs"])
    assert len(list(jobs_root.glob("*dream-cycle/meta.json"))) == 2
    for job_dir in jobs_root.iterdir():
        events = [
            json.loads(line)
            for line in (job_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert events[-1]["state"] == "complete"
