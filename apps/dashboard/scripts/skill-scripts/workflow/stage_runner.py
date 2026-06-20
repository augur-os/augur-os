"""
Stage Runner.

Executes the internal loop for each stage:
Plan → Execute → Test → Validate → Questions → Complete
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .state_manager import (
    RetryRecord,
    StageOutput,
    WorkflowPhase,
    WorkflowState,
    WorkflowStatus,
)

if TYPE_CHECKING:
    try:
        from ..stages.base_stage import BaseStage
    except ImportError:
        from stages.base_stage import BaseStage


class PhaseStatus(str, Enum):
    """Status of a phase execution."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


@dataclass
class PhaseResult:
    """Result of executing a single phase."""

    phase: WorkflowPhase
    status: PhaseStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class StageResult:
    """Result of executing a complete stage."""

    stage_num: int
    completed: bool = False
    phases: Dict[WorkflowPhase, PhaseResult] = field(default_factory=dict)
    output: Optional[StageOutput] = None
    pending_questions: List[Dict[str, Any]] = field(default_factory=list)
    needs_user_input: bool = False
    error: Optional[str] = None


class StageRunner:
    """Runs the internal loop for a stage.

    Each stage follows:
    1. Plan - Analyze and create execution plan
    2. Execute - Generate/modify files
    3. Test - Run automated checks
    4. Validate - Check acceptance criteria (retry up to max_retries)
    5. Questions - Present user questions (skip in auto mode)
    6. Complete - Checkpoint and mark stage done
    """

    def __init__(self, stage: "BaseStage", state: WorkflowState):
        """Initialize stage runner.

        Args:
            stage: Stage implementation to run
            state: Current workflow state
        """
        self.stage = stage
        self.state = state
        self.result = StageResult(stage_num=stage.stage_num)

    def run(self) -> StageResult:
        """Run the stage from current phase to completion or pause.

        Returns:
            StageResult with completion status and any pending questions
        """
        # Determine starting phase
        start_phase = self.state.current_phase

        # Phase execution order
        phases = [
            WorkflowPhase.PLAN,
            WorkflowPhase.EXECUTE,
            WorkflowPhase.TEST,
            WorkflowPhase.VALIDATE,
            WorkflowPhase.QUESTIONS,
            WorkflowPhase.COMPLETE,
        ]

        # Find starting index
        try:
            start_idx = phases.index(start_phase)
        except ValueError:
            start_idx = 0

        # Run phases in order
        for phase in phases[start_idx:]:
            self.state.current_phase = phase

            phase_result = self._run_phase(phase)
            self.result.phases[phase] = phase_result

            if phase_result.status == PhaseStatus.FAILED:
                # Check if we should retry
                if phase in (WorkflowPhase.EXECUTE, WorkflowPhase.TEST, WorkflowPhase.VALIDATE):
                    if self.state.retry_count < self.state.max_retries:
                        self.state.retry_count += 1
                        self.state.retry_history.append(
                            RetryRecord(
                                stage=self.stage.stage_num,
                                phase=phase.value,
                                error=phase_result.error or "Unknown error",
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )
                        )

                        # ADR-106: LLM-assisted diagnosis after trigger_attempt
                        self._try_llm_diagnosis(phase_result.error or "Unknown error")

                        # Retry from plan phase
                        self.state.current_phase = WorkflowPhase.PLAN
                        return self.run()  # Recursive retry

                # Max retries exceeded or non-retryable phase
                self.state.status = WorkflowStatus.PAUSED
                self.state.last_error = phase_result.error
                self.result.error = phase_result.error
                return self.result

            if phase == WorkflowPhase.QUESTIONS:
                if phase_result.status == PhaseStatus.PENDING:
                    # Waiting for user input
                    self.state.status = WorkflowStatus.PAUSED
                    self.result.needs_user_input = True
                    self.result.pending_questions = phase_result.data.get("questions", [])
                    self.state.pending_questions = self.result.pending_questions
                    return self.result

        # Stage completed successfully
        self.result.completed = True
        self.result.output = StageOutput(
            stage_num=self.stage.stage_num,
            completed_at=datetime.utcnow().isoformat() + "Z",
            data=self._collect_stage_output(),
        )

        # Reset retry count for next stage
        self.state.retry_count = 0
        self.state.pending_questions = []

        return self.result

    def _try_llm_diagnosis(self, error: str) -> None:
        """ADR-106: Invoke LLM diagnosis when retry count hits trigger_attempt."""
        try:
            from src.lib.llm_retry import (
                LLMRetryConfig,
                RetryAttemptLog,
                diagnose_with_llm,
            )

            config = LLMRetryConfig.load()
            if self.state.retry_count < config.trigger_attempt:
                return
            if not config.is_enabled_for("workflow_engine"):
                return

            attempts = [
                RetryAttemptLog(
                    attempt=r.stage,
                    error=r.error,
                    timestamp=r.timestamp,
                )
                for r in self.state.retry_history
            ]
            diagnosis = diagnose_with_llm(
                component="workflow_engine",
                attempts=attempts,
                context=f"stage={self.stage.stage_num} phase={self.state.current_phase.value}",
                config=config,
            )
            if diagnosis.suggestion:
                # Feed diagnosis into state so PLAN phase can use it
                self.state.llm_diagnosis = diagnosis.suggestion
        except Exception:
            pass  # Never block retry path

    def _run_phase(self, phase: WorkflowPhase) -> PhaseResult:
        """Run a single phase.

        Args:
            phase: Phase to run

        Returns:
            PhaseResult
        """
        start_time = datetime.utcnow()

        try:
            if phase == WorkflowPhase.PLAN:
                result = self._run_plan()
            elif phase == WorkflowPhase.EXECUTE:
                result = self._run_execute()
            elif phase == WorkflowPhase.TEST:
                result = self._run_test()
            elif phase == WorkflowPhase.VALIDATE:
                result = self._run_validate()
            elif phase == WorkflowPhase.QUESTIONS:
                result = self._run_questions()
            elif phase == WorkflowPhase.COMPLETE:
                result = self._run_complete()
            else:
                result = PhaseResult(
                    phase=phase,
                    status=PhaseStatus.SKIPPED,
                )

            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.duration_ms = int(duration)
            return result

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            return PhaseResult(
                phase=phase,
                status=PhaseStatus.FAILED,
                error=str(e),
                duration_ms=int(duration),
            )

    def _run_plan(self) -> PhaseResult:
        """Run plan phase."""
        # Get previous stage output if available
        prev_output = None
        if self.stage.stage_num > 1:
            prev_output = self.state.stage_outputs.get(self.stage.stage_num - 1)

        # Get user answers for this stage if we're retrying
        user_answers = self.state.user_answers.get(self.stage.stage_num, {})

        plan = self.stage.plan(
            state=self.state,
            previous_output=prev_output,
            user_answers=user_answers,
        )

        return PhaseResult(
            phase=WorkflowPhase.PLAN,
            status=PhaseStatus.SUCCESS if plan else PhaseStatus.FAILED,
            data={"plan": plan},
            error=None if plan else "Failed to create execution plan",
        )

    def _run_execute(self) -> PhaseResult:
        """Run execute phase."""
        plan = self.result.phases.get(WorkflowPhase.PLAN)
        if not plan or plan.status != PhaseStatus.SUCCESS:
            return PhaseResult(
                phase=WorkflowPhase.EXECUTE,
                status=PhaseStatus.FAILED,
                error="No valid plan to execute",
            )

        artifacts = self.stage.execute(
            state=self.state,
            plan=plan.data.get("plan", {}),
        )

        return PhaseResult(
            phase=WorkflowPhase.EXECUTE,
            status=PhaseStatus.SUCCESS if artifacts else PhaseStatus.FAILED,
            data={"artifacts": artifacts},
            error=None if artifacts else "Execution produced no artifacts",
        )

    def _run_test(self) -> PhaseResult:
        """Run test phase."""
        execute_result = self.result.phases.get(WorkflowPhase.EXECUTE)
        if not execute_result or execute_result.status != PhaseStatus.SUCCESS:
            return PhaseResult(
                phase=WorkflowPhase.TEST,
                status=PhaseStatus.FAILED,
                error="No artifacts to test",
            )

        artifacts = execute_result.data.get("artifacts", {})
        test_results = self.stage.test(
            state=self.state,
            artifacts=artifacts,
        )

        # Determine if tests passed
        all_passed = all(r.get("passed", False) if isinstance(r, dict) else r for r in test_results.values())

        return PhaseResult(
            phase=WorkflowPhase.TEST,
            status=PhaseStatus.SUCCESS if all_passed else PhaseStatus.FAILED,
            data={"test_results": test_results},
            error=None if all_passed else "One or more tests failed",
        )

    def _run_validate(self) -> PhaseResult:
        """Run validate phase."""
        test_result = self.result.phases.get(WorkflowPhase.TEST)
        execute_result = self.result.phases.get(WorkflowPhase.EXECUTE)

        if not test_result or test_result.status != PhaseStatus.SUCCESS:
            return PhaseResult(
                phase=WorkflowPhase.VALIDATE,
                status=PhaseStatus.FAILED,
                error="Cannot validate without passing tests",
            )

        artifacts = execute_result.data.get("artifacts", {}) if execute_result else {}
        test_data = test_result.data.get("test_results", {})

        validation = self.stage.validate(
            state=self.state,
            artifacts=artifacts,
            test_results=test_data,
        )

        return PhaseResult(
            phase=WorkflowPhase.VALIDATE,
            status=PhaseStatus.SUCCESS if validation.passed else PhaseStatus.FAILED,
            data={"validation": validation},
            error=None if validation.passed else f"Validation failed: {len(validation.errors)} errors",
        )

    def _run_questions(self) -> PhaseResult:
        """Run questions phase."""
        # Skip questions in auto mode
        if self.state.auto_mode:
            return PhaseResult(
                phase=WorkflowPhase.QUESTIONS,
                status=PhaseStatus.SKIPPED,
                data={"skipped_reason": "auto_mode"},
            )

        # Check if we already have answers for this stage
        if self.state.user_answers.get(self.stage.stage_num):
            return PhaseResult(
                phase=WorkflowPhase.QUESTIONS,
                status=PhaseStatus.SUCCESS,
                data={"answers": self.state.user_answers[self.stage.stage_num]},
            )

        # Generate context-aware questions
        execute_result = self.result.phases.get(WorkflowPhase.EXECUTE)
        validate_result = self.result.phases.get(WorkflowPhase.VALIDATE)

        artifacts = execute_result.data.get("artifacts", {}) if execute_result else {}
        validation = validate_result.data.get("validation") if validate_result else None

        questions = self.stage.generate_questions(
            state=self.state,
            artifacts=artifacts,
            validation=validation,
        )

        if questions:
            return PhaseResult(
                phase=WorkflowPhase.QUESTIONS,
                status=PhaseStatus.PENDING,
                data={"questions": questions},
            )

        # No questions needed
        return PhaseResult(
            phase=WorkflowPhase.QUESTIONS,
            status=PhaseStatus.SUCCESS,
            data={"questions": []},
        )

    def _run_complete(self) -> PhaseResult:
        """Run complete phase."""
        return PhaseResult(
            phase=WorkflowPhase.COMPLETE,
            status=PhaseStatus.SUCCESS,
            data={"completed_at": datetime.utcnow().isoformat() + "Z"},
        )

    def _collect_stage_output(self) -> Dict[str, Any]:
        """Collect output data from all phases."""
        output = {}

        for phase, result in self.result.phases.items():
            if result.status == PhaseStatus.SUCCESS and result.data:
                # Flatten phase data into output
                for key, value in result.data.items():
                    if key not in ("plan",):  # Skip internal data
                        # Serialize complex objects
                        output[f"{phase.value}_{key}"] = self._serialize_value(value)

        # Add stage-specific output from the stage implementation
        stage_output = self.stage.get_output(self.state)
        if stage_output:
            for key, value in stage_output.items():
                output[key] = self._serialize_value(value)

        return output

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for YAML storage."""
        # Handle ValidationResult
        if hasattr(value, 'to_dict'):
            return value.to_dict()
        elif hasattr(value, '__dict__'):
            # Generic object serialization
            return {k: self._serialize_value(v) for k, v in value.__dict__.items() if not k.startswith('_')}
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, Path):
            return str(value)
        else:
            return value
