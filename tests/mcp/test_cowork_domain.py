"""
Tests for ADR-270 cowork runtime path resolution.
"""

from __future__ import annotations

from src.mcp.augur_framework.tools.domain import cowork


def test_cowork_paths_use_runtime_state_env(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AUGUR_STATE", str(state_dir))

    dispatch_dir = cowork._get_cowork_dispatch_dir()
    results_dir = cowork._get_cowork_results_dir()

    assert dispatch_dir == state_dir / "cowork-dispatch"
    assert results_dir == state_dir / "cowork-results"


def test_ingest_result_writes_summary_log_to_runtime_state(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AUGUR_STATE", str(state_dir))

    task = {
        "task_id": "task-123",
        "result": {
            "summary": "Cowork finished the task",
        },
    }

    result = cowork._ingest_result(task, dry_run=False)

    assert result["ingested"] is True
    logs = list((state_dir / "cowork-results").glob("session_*.log"))
    assert len(logs) == 1
    assert "task=task-123" in logs[0].read_text(encoding="utf-8")
    assert "Cowork finished the task" in logs[0].read_text(encoding="utf-8")
