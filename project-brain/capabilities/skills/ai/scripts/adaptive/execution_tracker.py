"""
Execution Tracker for Adaptive Slash Commands (ADR-102)

Tracks metrics during command execution for later analysis and improvement.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .incidents import IncidentRecord, aggregate_incidents, normalize_incident


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    SKIPPED = "skipped"


class Outcome(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


@dataclass
class StepRecord:
    name: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    resolution: str | None = None
    retry_count: int = 0
    tokens_used: int = 0
    files_read: int = 0
    files_written: int = 0


@dataclass
class PhaseRecord:
    name: str
    status: PhaseStatus = PhaseStatus.PENDING
    steps: list[StepRecord] = field(default_factory=list)
    started_at: float | None = None
    completed_at: float | None = None
    issues: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionLog:
    command: str
    args: dict[str, Any]
    started_at: float
    completed_at: float | None = None
    phases: list[PhaseRecord] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    outcome: Outcome | None = None
    blockers: list[str] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    incidents: list[IncidentRecord] = field(default_factory=list)


class ExecutionTracker:
    """Tracks execution metrics for adaptive improvement."""

    def __init__(
        self,
        command_name: str,
        args: dict[str, Any] | None = None,
        project_root: Path | None = None,
    ):
        self.log = ExecutionLog(
            command=command_name,
            args=args or {},
            started_at=time.time(),
        )
        self._started_monotonic = time.perf_counter()
        self.project_root = project_root
        self._current_phase: PhaseRecord | None = None
        self._current_step: StepRecord | None = None

    def start_phase(self, name: str) -> PhaseRecord:
        """Start a new execution phase."""
        phase = PhaseRecord(
            name=name,
            status=PhaseStatus.RUNNING,
            started_at=time.time(),
        )
        self.log.phases.append(phase)
        self._current_phase = phase
        return phase

    def end_phase(
        self,
        status: PhaseStatus = PhaseStatus.COMPLETED,
        issue: dict[str, Any] | None = None,
    ) -> None:
        """End the current phase."""
        if self._current_phase:
            self._current_phase.status = status
            self._current_phase.completed_at = time.time()
            if issue:
                self._current_phase.issues.append(issue)
            self._current_phase = None

    def start_step(self, name: str) -> StepRecord:
        """Start a new step within the current phase."""
        step = StepRecord(
            name=name,
            status=PhaseStatus.RUNNING,
            started_at=time.time(),
        )
        if self._current_phase:
            self._current_phase.steps.append(step)
        self._current_step = step
        return step

    def end_step(
        self,
        status: PhaseStatus = PhaseStatus.COMPLETED,
        error: str | None = None,
        resolution: str | None = None,
    ) -> None:
        """End the current step."""
        if self._current_step:
            self._current_step.status = status
            self._current_step.completed_at = time.time()
            self._current_step.error = error
            self._current_step.resolution = resolution
            self._current_step = None

    def record_retry(self) -> None:
        """Record that the current step is being retried."""
        if self._current_step:
            self._current_step.retry_count += 1

    def record_metrics(
        self,
        tokens: int = 0,
        files_read: int = 0,
        files_written: int = 0,
        tests_run: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0,
    ) -> None:
        """Record execution metrics."""
        self.log.metrics["tokens_used"] = self.log.metrics.get("tokens_used", 0) + tokens
        self.log.metrics["files_read"] = self.log.metrics.get("files_read", 0) + files_read
        self.log.metrics["files_written"] = self.log.metrics.get("files_written", 0) + files_written
        self.log.metrics["tests_run"] = self.log.metrics.get("tests_run", 0) + tests_run
        self.log.metrics["tests_passed"] = self.log.metrics.get("tests_passed", 0) + tests_passed
        self.log.metrics["tests_failed"] = self.log.metrics.get("tests_failed", 0) + tests_failed

    def add_blocker(self, blocker: str) -> None:
        """Add a blocker that prevented completion."""
        self.log.blockers.append(blocker)
        incident = normalize_incident(
            blocker,
            command=self.log.command,
            project_root=self.project_root,
        )
        if incident is not None:
            self.log.incidents.append(incident)

    def add_learning(self, learning: str) -> None:
        """Add a learning from this execution."""
        self.log.learnings.append(learning)

    def add_incident(self, incident: IncidentRecord) -> None:
        """Add an already-normalized incident."""
        self.log.incidents.append(incident)

    def finalize(self, outcome: Outcome) -> ExecutionLog:
        """Finalize the execution log."""
        self.log.completed_at = time.time()
        self.log.outcome = outcome
        self.log.metrics["duration_seconds"] = max(time.perf_counter() - self._started_monotonic, 1e-9)
        return self.log

    def save(self, runtime_dir: Path) -> Path:
        """Save the execution log to disk."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        log_dir = runtime_dir / "command-evolution" / self.log.command / "executions"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{timestamp}.json"

        log_data = {
            "command": self.log.command,
            "args": self.log.args,
            "started_at": datetime.fromtimestamp(self.log.started_at, tz=timezone.utc).isoformat(),
            "completed_at": (
                datetime.fromtimestamp(self.log.completed_at, tz=timezone.utc).isoformat()
                if self.log.completed_at
                else None
            ),
            "duration_seconds": self.log.metrics.get("duration_seconds", 0),
            "phases": [
                {
                    "name": p.name,
                    "status": p.status.value,
                    "started_at": (
                        datetime.fromtimestamp(p.started_at, tz=timezone.utc).isoformat() if p.started_at else None
                    ),
                    "completed_at": (
                        datetime.fromtimestamp(p.completed_at, tz=timezone.utc).isoformat() if p.completed_at else None
                    ),
                    "duration_seconds": (p.completed_at - p.started_at) if p.started_at and p.completed_at else 0,
                    "steps": [{"name": s.name, "status": s.status.value} for s in p.steps],
                    "issues": p.issues,
                }
                for p in self.log.phases
            ],
            "metrics": self.log.metrics,
            "outcome": self.log.outcome.value if self.log.outcome else None,
            "blockers": self.log.blockers,
            "learnings": self.log.learnings,
            "incidents": [incident.to_dict() for incident in self.log.incidents],
        }

        log_path.write_text(json.dumps(log_data, indent=2))
        if self.log.incidents:
            aggregate_incidents(runtime_dir, self.log.incidents)
        return log_path

    def get_log(self) -> ExecutionLog:
        """Get the current execution log."""
        return self.log
