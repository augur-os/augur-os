"""Tests for adaptive/execution_tracker.py — command execution tracking.

Validates the ExecutionTracker: creating phases and steps, recording metrics,
blockers, learnings, finalizing, and saving execution logs to disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.ai.scripts.adaptive.execution_tracker import (
    ExecutionTracker,
    Outcome,
    PhaseStatus,
)


# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------


class TestTrackerLifecycle:
    def test_create_tracker(self):
        tracker = ExecutionTracker("test-cmd", args={"flag": True})
        log = tracker.get_log()
        assert log.command == "test-cmd"
        assert log.args == {"flag": True}
        assert log.started_at > 0

    def test_phase_lifecycle(self):
        tracker = ExecutionTracker("test-cmd")
        phase = tracker.start_phase("build")
        assert phase.name == "build"
        assert phase.status == PhaseStatus.RUNNING

        tracker.end_phase(PhaseStatus.COMPLETED)
        assert phase.status == PhaseStatus.COMPLETED
        assert phase.completed_at is not None

    def test_step_within_phase(self):
        tracker = ExecutionTracker("test-cmd")
        tracker.start_phase("build")
        step = tracker.start_step("compile")
        assert step.name == "compile"
        assert step.status == PhaseStatus.RUNNING

        tracker.end_step(PhaseStatus.COMPLETED)
        assert step.status == PhaseStatus.COMPLETED

        log = tracker.get_log()
        assert len(log.phases[0].steps) == 1

    def test_finalize(self):
        tracker = ExecutionTracker("test-cmd")
        tracker.start_phase("init")
        tracker.end_phase()
        log = tracker.finalize(Outcome.SUCCESS)
        assert log.outcome == Outcome.SUCCESS
        assert log.completed_at is not None
        assert log.metrics["duration_seconds"] > 0


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


class TestRecording:
    def test_record_metrics(self):
        tracker = ExecutionTracker("test-cmd")
        tracker.record_metrics(tokens=100, files_read=5)
        tracker.record_metrics(tokens=50, files_written=2)
        log = tracker.get_log()
        assert log.metrics["tokens_used"] == 150
        assert log.metrics["files_read"] == 5
        assert log.metrics["files_written"] == 2

    def test_record_retry(self):
        tracker = ExecutionTracker("test-cmd")
        tracker.start_phase("build")
        step = tracker.start_step("flaky-step")
        tracker.record_retry()
        tracker.record_retry()
        assert step.retry_count == 2

    def test_add_blocker(self):
        tracker = ExecutionTracker("test-cmd")
        tracker.add_blocker("port 3000 already in use")
        log = tracker.get_log()
        assert "port 3000 already in use" in log.blockers

    def test_add_learning(self):
        tracker = ExecutionTracker("test-cmd")
        tracker.add_learning("Always check lockfile")
        log = tracker.get_log()
        assert "Always check lockfile" in log.learnings


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


class TestSave:
    def test_save_creates_json_file(self, tmp_path: Path):
        tracker = ExecutionTracker("test-cmd", args={"dry_run": False})
        tracker.start_phase("build")
        tracker.end_phase()
        tracker.finalize(Outcome.SUCCESS)

        log_path = tracker.save(tmp_path)
        assert log_path.exists()
        assert log_path.suffix == ".json"

        data = json.loads(log_path.read_text())
        assert data["command"] == "test-cmd"
        assert data["outcome"] == "success"
        assert len(data["phases"]) == 1

    def test_save_directory_structure(self, tmp_path: Path):
        tracker = ExecutionTracker("my-cmd")
        tracker.finalize(Outcome.FAILURE)
        log_path = tracker.save(tmp_path)
        assert "command-evolution" in str(log_path)
        assert "my-cmd" in str(log_path)
        assert "executions" in str(log_path)

    def test_step_error_persisted(self, tmp_path: Path):
        tracker = ExecutionTracker("fail-cmd")
        tracker.start_phase("deploy")
        tracker.start_step("push")
        tracker.end_step(PhaseStatus.FAILED, error="timeout")
        tracker.end_phase(PhaseStatus.FAILED)
        tracker.finalize(Outcome.FAILURE)

        log_path = tracker.save(tmp_path)
        data = json.loads(log_path.read_text())
        assert data["outcome"] == "failure"
        steps = data["phases"][0]["steps"]
        assert steps[0]["status"] == "failed"
