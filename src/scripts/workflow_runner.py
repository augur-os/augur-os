"""Generic Workflow Runner (ADR-086).

Extracted from the factory StageRunner to be reusable by any multi-stage
workflow (factory pipeline, /import, etc.).

Classes:
    Stage: Abstract base for a workflow stage (plan, execute, validate, questions).
    WorkflowRunner: Orchestrates stages with state persistence, retries, and
                    user question pauses.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Phase(str, Enum):
    """Phase within a stage."""

    PLAN = "plan"
    EXECUTE = "execute"
    VALIDATE = "validate"
    QUESTIONS = "questions"
    COMPLETE = "complete"


class RunStatus(str, Enum):
    """Overall workflow run status."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class PhaseOutcome(str, Enum):
    """Outcome of a single phase."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PhaseResult:
    """Result of running a single phase."""

    phase: Phase
    outcome: PhaseOutcome
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0


@dataclass
class StageResult:
    """Result of running a complete stage."""

    stage_name: str
    completed: bool = False
    phases: dict[Phase, PhaseResult] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    pending_questions: list[dict[str, Any]] = field(default_factory=list)
    needs_user_input: bool = False
    error: str | None = None


@dataclass
class RunState:
    """Serializable state for a workflow run.

    Generic replacement for factory-specific WorkflowState. Stores enough
    to resume a workflow after a pause (e.g., waiting for user questions).
    """

    run_id: str
    status: RunStatus = RunStatus.ACTIVE
    current_stage_idx: int = 0
    current_phase: Phase = Phase.PLAN
    auto_mode: bool = False

    # Per-stage outputs keyed by stage name
    stage_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Per-stage user answers keyed by stage name
    user_answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_questions: list[dict[str, Any]] = field(default_factory=list)

    # Retry tracking
    retry_count: int = 0
    max_retries: int = 3
    last_error: str | None = None

    # Custom data (workflow-specific context, e.g., folder path, hub name)
    context: dict[str, Any] = field(default_factory=dict)

    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON/YAML persistence."""
        self.updated_at = datetime.utcnow().isoformat() + "Z"
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "current_stage_idx": self.current_stage_idx,
            "current_phase": self.current_phase.value,
            "auto_mode": self.auto_mode,
            "stage_outputs": self.stage_outputs,
            "user_answers": self.user_answers,
            "pending_questions": self.pending_questions,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_error": self.last_error,
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunState:
        """Deserialize from dict."""
        return cls(
            run_id=data.get("run_id", ""),
            status=RunStatus(data.get("status", "active")),
            current_stage_idx=data.get("current_stage_idx", 0),
            current_phase=Phase(data.get("current_phase", "plan")),
            auto_mode=data.get("auto_mode", False),
            stage_outputs=data.get("stage_outputs", {}),
            user_answers=data.get("user_answers", {}),
            pending_questions=data.get("pending_questions", []),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            last_error=data.get("last_error"),
            context=data.get("context", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


# ---------------------------------------------------------------------------
# Stage (abstract)
# ---------------------------------------------------------------------------


class Stage(ABC):
    """Abstract base for a workflow stage.

    Subclasses implement plan(), execute(), validate(), and optionally
    generate_questions() and get_output(). The WorkflowRunner drives the
    phase loop for each stage.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stage name (used as dict key in state)."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        return ""

    @abstractmethod
    def plan(
        self,
        state: RunState,
        previous_output: dict[str, Any] | None = None,
        user_answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an execution plan.

        Returns a dict describing what this stage will do. Returning an
        empty dict signals failure.
        """
        ...

    @abstractmethod
    def execute(
        self,
        state: RunState,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the plan. Returns artifact dict."""
        ...

    def validate(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Validate artifacts. Returns (passed, error_message).

        Default implementation always passes.
        """
        return True, None

    def generate_questions(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate user questions. Empty list means no questions needed."""
        return []

    def get_output(self, state: RunState) -> dict[str, Any]:
        """Collect final output data for downstream stages."""
        return {}


# ---------------------------------------------------------------------------
# WorkflowRunner
# ---------------------------------------------------------------------------


class WorkflowRunner:
    """Drives a list of stages through the phase loop.

    Usage:
        stages = [DeepScanStage(), BlueprintStage(), CodeGenStage(), ConnectStage()]
        runner = WorkflowRunner(stages, state_dir=get_runtime_dir() / "import" / "my-run")
        result = runner.run(context={"folder": "~/Documents/Finance", "hub": "finance"})

    The runner persists state to state_dir/run_state.json after each phase
    transition so it can be resumed after interruption or user question pause.
    """

    def __init__(
        self,
        stages: list[Stage],
        *,
        state_dir: Path | None = None,
        auto_mode: bool = False,
        max_retries: int = 3,
    ) -> None:
        self.stages = stages
        self.state_dir = state_dir
        self.auto_mode = auto_mode
        self.max_retries = max_retries

    def run(
        self,
        *,
        context: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Run the full workflow from start or resume from saved state.

        Args:
            context: Custom data passed to stages via RunState.context.
            run_id: Optional run identifier. Generated if not provided.

        Returns:
            Final result dict with status, outputs, and any errors.
        """
        # Try to resume from saved state
        state = self._load_state()
        if state and state.status in (RunStatus.ACTIVE, RunStatus.PAUSED):
            # Clear pause if resuming
            if state.status == RunStatus.PAUSED:
                state.status = RunStatus.ACTIVE
                state.pending_questions = []
        else:
            # Start fresh
            if not run_id:
                run_id = f"run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            state = RunState(
                run_id=run_id,
                auto_mode=self.auto_mode,
                max_retries=self.max_retries,
                context=context or {},
            )

        # Run stages
        while state.current_stage_idx < len(self.stages):
            stage = self.stages[state.current_stage_idx]
            result = self._run_stage(stage, state)

            if result.needs_user_input:
                # Paused for user questions
                state.status = RunStatus.PAUSED
                state.pending_questions = result.pending_questions
                self._save_state(state)
                return {
                    "status": "paused",
                    "run_id": state.run_id,
                    "current_stage": stage.name,
                    "pending_questions": result.pending_questions,
                    "message": "Waiting for user answers",
                }

            if not result.completed:
                # Stage failed
                state.status = RunStatus.FAILED
                state.last_error = result.error
                self._save_state(state)
                return {
                    "status": "failed",
                    "run_id": state.run_id,
                    "current_stage": stage.name,
                    "error": result.error,
                    "completed_stages": list(state.stage_outputs.keys()),
                }

            # Stage succeeded — save output and advance
            state.stage_outputs[stage.name] = result.output
            state.current_stage_idx += 1
            state.current_phase = Phase.PLAN
            state.retry_count = 0
            self._save_state(state)

        # All stages complete
        state.status = RunStatus.COMPLETED
        self._save_state(state)

        return {
            "status": "completed",
            "run_id": state.run_id,
            "completed_stages": list(state.stage_outputs.keys()),
            "outputs": state.stage_outputs,
            "context": state.context,
        }

    def resume(self, answers: dict[str, Any] | None = None) -> dict[str, Any]:
        """Resume a paused workflow, optionally providing user answers.

        Args:
            answers: User answers for pending questions.

        Returns:
            Result dict (same format as run()).
        """
        state = self._load_state()
        if not state:
            return {"status": "error", "error": "No saved state to resume"}

        if state.status != RunStatus.PAUSED:
            return {"status": "error", "error": f"Cannot resume: status is {state.status.value}"}

        # Store answers
        if answers and state.current_stage_idx < len(self.stages):
            stage_name = self.stages[state.current_stage_idx].name
            state.user_answers[stage_name] = answers

        state.status = RunStatus.ACTIVE
        state.pending_questions = []
        self._save_state(state)

        return self.run()

    def _run_stage(self, stage: Stage, state: RunState) -> StageResult:
        """Run a single stage through the phase loop."""
        result = StageResult(stage_name=stage.name)

        # Get previous stage output
        prev_output: dict[str, Any] | None = None
        if state.current_stage_idx > 0:
            prev_name = self.stages[state.current_stage_idx - 1].name
            prev_output = state.stage_outputs.get(prev_name)

        user_answers = state.user_answers.get(stage.name)

        # Phase 1: PLAN
        try:
            plan = stage.plan(state, previous_output=prev_output, user_answers=user_answers)
        except Exception as e:
            result.error = f"Plan failed: {e}"
            return result

        if not plan:
            result.error = "Plan returned empty result"
            return result

        result.phases[Phase.PLAN] = PhaseResult(phase=Phase.PLAN, outcome=PhaseOutcome.SUCCESS, data={"plan": plan})

        # Phase 2: EXECUTE
        try:
            artifacts = stage.execute(state, plan)
        except Exception as e:
            result.error = f"Execute failed: {e}"
            if state.retry_count < state.max_retries:
                state.retry_count += 1
                return self._run_stage(stage, state)
            return result

        if not artifacts:
            result.error = "Execute produced no artifacts"
            return result

        result.phases[Phase.EXECUTE] = PhaseResult(
            phase=Phase.EXECUTE, outcome=PhaseOutcome.SUCCESS, data={"artifacts": artifacts}
        )

        # Phase 3: VALIDATE
        try:
            passed, error_msg = stage.validate(state, artifacts)
        except Exception as e:
            passed, error_msg = False, str(e)

        if not passed:
            if state.retry_count < state.max_retries:
                state.retry_count += 1
                return self._run_stage(stage, state)
            result.error = f"Validation failed: {error_msg}"
            return result

        result.phases[Phase.VALIDATE] = PhaseResult(phase=Phase.VALIDATE, outcome=PhaseOutcome.SUCCESS)

        # Phase 4: QUESTIONS (skip in auto mode)
        if not state.auto_mode and not state.user_answers.get(stage.name):
            try:
                questions = stage.generate_questions(state, artifacts)
            except Exception:
                questions = []

            if questions:
                result.needs_user_input = True
                result.pending_questions = questions
                state.pending_questions = questions
                return result

        result.phases[Phase.QUESTIONS] = PhaseResult(
            phase=Phase.QUESTIONS,
            outcome=PhaseOutcome.SKIPPED if state.auto_mode else PhaseOutcome.SUCCESS,
        )

        # Phase 5: COMPLETE — collect output
        try:
            output = stage.get_output(state)
        except Exception:
            output = {}

        # Merge artifacts into output
        output["artifacts"] = artifacts
        result.output = output
        result.completed = True

        result.phases[Phase.COMPLETE] = PhaseResult(phase=Phase.COMPLETE, outcome=PhaseOutcome.SUCCESS)

        return result

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _save_state(self, state: RunState) -> None:
        """Persist state to disk."""
        if not self.state_dir:
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        state_file = self.state_dir / "run_state.json"
        state_file.write_text(json.dumps(state.to_dict(), indent=2, default=str))

    def _load_state(self) -> RunState | None:
        """Load persisted state from disk."""
        if not self.state_dir:
            return None
        state_file = self.state_dir / "run_state.json"
        if not state_file.exists():
            return None
        try:
            data = json.loads(state_file.read_text())
            return RunState.from_dict(data)
        except Exception:
            return None
