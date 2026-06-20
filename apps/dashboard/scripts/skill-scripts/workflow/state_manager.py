"""
Workflow State Management.

Handles persistent state for plugin generation/refactoring workflows.
Supports checkpointing, resumption, and state transitions.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class WorkflowMode(str, Enum):
    """Workflow operation mode."""

    NEW = "new"
    REFACTOR = "refactor"


class WorkflowPhase(str, Enum):
    """Current phase within a stage."""

    PLAN = "plan"
    EXECUTE = "execute"
    TEST = "test"
    VALIDATE = "validate"
    QUESTIONS = "questions"
    COMPLETE = "complete"


class WorkflowStatus(str, Enum):
    """Overall workflow status."""

    ACTIVE = "active"
    PAUSED = "paused"  # Waiting for user input or after retry exhaustion
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class StageOutput:
    """Output from a completed stage."""

    stage_num: int
    completed_at: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryRecord:
    """Record of a retry attempt."""

    stage: int
    phase: str
    error: str
    timestamp: str


@dataclass
class WorkflowState:
    """Complete state of a workflow."""

    # Identity
    workflow_id: str
    mode: WorkflowMode
    auto_mode: bool = False  # Skip questions, use defaults

    # Target
    skill_name: str = ""
    # Track 3b: bundle is the plugin BUNDLE id (skill distribution group),
    # not a hub id from config/system/hubs.yaml.
    bundle: str = "lifestyle"
    target_profile: str = "standard"  # minimal, standard, full

    # Source (refactor mode only)
    source_path: Optional[str] = None
    backup_path: Optional[str] = None

    # Progress
    current_stage: int = 1
    current_phase: WorkflowPhase = WorkflowPhase.PLAN
    status: WorkflowStatus = WorkflowStatus.ACTIVE

    # Outputs
    stage_outputs: Dict[int, StageOutput] = field(default_factory=dict)
    user_answers: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    pending_questions: List[Dict[str, Any]] = field(default_factory=list)

    # Error handling
    retry_count: int = 0
    max_retries: int = 3
    retry_history: List[RetryRecord] = field(default_factory=list)
    last_error: Optional[str] = None
    llm_diagnosis: Optional[str] = None  # ADR-106: LLM retry suggestion

    # Quality Scoring (for refactor mode)
    # Structure: {
    #   "before_score": QualityScore.to_dict(),
    #   "after_score": QualityScore.to_dict() | None,
    #   "comparison": ScoreComparison.to_dict() | None,
    #   "user_answers": Dict[str, Any],
    #   "loop_iteration": int,
    #   "approved": bool,
    # }
    scoring_data: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    @property
    def stages_completed(self) -> List[int]:
        """List of completed stage numbers."""
        return sorted(self.stage_outputs.keys())

    @property
    def progress_percent(self) -> float:
        """Overall progress as percentage."""
        total_phases = 5 * 6  # 5 stages, 6 phases each
        completed_phases = len(self.stages_completed) * 6
        current_phase_idx = list(WorkflowPhase).index(self.current_phase)
        return ((completed_phases + current_phase_idx) / total_phases) * 100

    @property
    def skill_path(self) -> Path:
        """Path to the skill being created/modified."""
        from pathlib import Path

        try:
            from src.config.paths import get_project_root
            project_root = get_project_root()
        except ImportError:
            project_root = Path(__file__).parent.parent.parent.parent.parent.parent  # fallback
        return project_root / "plugins" / self.bundle / "skills" / self.skill_name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        self.updated_at = datetime.utcnow().isoformat() + "Z"
        return {
            "workflow_id": self.workflow_id,
            "mode": self.mode.value if isinstance(self.mode, WorkflowMode) else self.mode,
            "auto_mode": self.auto_mode,
            "target": {
                "skill_name": self.skill_name,
                "bundle": self.bundle,
                "profile": self.target_profile,
            },
            "source": (
                {
                    "path": self.source_path,
                    "backup_path": self.backup_path,
                }
                if self.source_path
                else None
            ),
            "progress": {
                "current_stage": self.current_stage,
                "current_phase": (
                    self.current_phase.value if isinstance(self.current_phase, WorkflowPhase) else self.current_phase
                ),
                "status": self.status.value if isinstance(self.status, WorkflowStatus) else self.status,
                "stages_completed": self.stages_completed,
                "progress_percent": round(self.progress_percent, 1),
            },
            "stage_outputs": {
                k: {"stage_num": v.stage_num, "completed_at": v.completed_at, "data": v.data}
                for k, v in self.stage_outputs.items()
            },
            "user_answers": self.user_answers,
            "pending_questions": self.pending_questions,
            "error_handling": {
                "retry_count": self.retry_count,
                "max_retries": self.max_retries,
                "last_error": self.last_error,
                "retry_history": [
                    {"stage": r.stage, "phase": r.phase, "error": r.error, "timestamp": r.timestamp}
                    for r in self.retry_history
                ],
            },
            "scoring_data": self.scoring_data,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """Create from dictionary (YAML deserialization)."""
        target = data.get("target", {})
        source = data.get("source", {})
        progress = data.get("progress", {})
        error_handling = data.get("error_handling", {})

        stage_outputs = {}
        for k, v in data.get("stage_outputs", {}).items():
            stage_outputs[int(k)] = StageOutput(
                stage_num=v.get("stage_num", int(k)),
                completed_at=v.get("completed_at", ""),
                data=v.get("data", {}),
            )

        retry_history = [
            RetryRecord(
                stage=r.get("stage", 0),
                phase=r.get("phase", ""),
                error=r.get("error", ""),
                timestamp=r.get("timestamp", ""),
            )
            for r in error_handling.get("retry_history", [])
        ]

        return cls(
            workflow_id=data.get("workflow_id", ""),
            mode=WorkflowMode(data.get("mode", "new")),
            auto_mode=data.get("auto_mode", False),
            skill_name=target.get("skill_name", ""),
            bundle=target.get("bundle", "lifestyle"),
            target_profile=target.get("profile", "standard"),
            source_path=source.get("path") if source else None,
            backup_path=source.get("backup_path") if source else None,
            current_stage=progress.get("current_stage", 1),
            current_phase=WorkflowPhase(progress.get("current_phase", "plan")),
            status=WorkflowStatus(progress.get("status", "active")),
            stage_outputs=stage_outputs,
            user_answers=data.get("user_answers", {}),
            pending_questions=data.get("pending_questions", []),
            retry_count=error_handling.get("retry_count", 0),
            max_retries=error_handling.get("max_retries", 3),
            retry_history=retry_history,
            last_error=error_handling.get("last_error"),
            scoring_data=data.get("scoring_data", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class StateManager:
    """Manages workflow state persistence."""

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize state manager.

        Args:
            base_dir: Base directory for state storage. Defaults to
                skills/mcp-app-factory/augur/workflows/
        """
        if base_dir is None:
            # Default to data directory
            data_base = os.environ.get("AUGUR_ROOT")
            if data_base:
                base_dir = (
                    Path(data_base).parent / "plugins" / "ai" / "skills" / "mcp-app-factory" / "data" / "workflows"
                )
            else:
                try:
                    from src.config.paths import get_project_root
                    project_root = get_project_root()
                except ImportError:
                    project_root = Path(__file__).parent.parent.parent.parent.parent.parent  # fallback
                base_dir = project_root / "plugins" / "ai" / "skills" / "mcp-app-factory" / "data" / "workflows"

        self.base_dir = Path(base_dir)
        self.active_dir = self.base_dir / "active"
        self.completed_dir = self.base_dir / "completed"
        self.failed_dir = self.base_dir / "failed"
        self.checkpoints_dir = self.base_dir / "checkpoints"

        # Ensure directories exist
        for d in [self.active_dir, self.completed_dir, self.failed_dir, self.checkpoints_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def generate_workflow_id(self) -> str:
        """Generate a unique workflow ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        import random

        suffix = "".join(random.choices("abcdef0123456789", k=6))
        return f"plugin-gen-{timestamp}-{suffix}"

    def save(self, state: WorkflowState) -> Path:
        """Save workflow state to file.

        Args:
            state: Workflow state to save

        Returns:
            Path to saved state file
        """
        # Determine directory based on status
        if state.status == WorkflowStatus.COMPLETED:
            target_dir = self.completed_dir
        elif state.status in (WorkflowStatus.FAILED, WorkflowStatus.ABORTED):
            target_dir = self.failed_dir
        else:
            target_dir = self.active_dir

        file_path = target_dir / f"{state.workflow_id}.yaml"

        # Remove from other directories if file moved
        for directory in [self.active_dir, self.completed_dir, self.failed_dir]:
            if directory != target_dir:
                old_file = directory / f"{state.workflow_id}.yaml"
                if old_file.exists():
                    old_file.unlink()

        with open(file_path, "w") as f:
            yaml.dump(state.to_dict(), f, default_flow_style=False, allow_unicode=True)

        return file_path

    def load(self, workflow_id: str) -> Optional[WorkflowState]:
        """Load workflow state by ID.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowState if found, None otherwise
        """
        # Check all directories
        for directory in [self.active_dir, self.completed_dir, self.failed_dir]:
            file_path = directory / f"{workflow_id}.yaml"
            if file_path.exists():
                with open(file_path) as f:
                    data = yaml.safe_load(f)
                return WorkflowState.from_dict(data)

        return None

    def checkpoint(self, state: WorkflowState) -> Path:
        """Create a checkpoint for the current stage.

        Args:
            state: Workflow state to checkpoint

        Returns:
            Path to checkpoint file
        """
        checkpoint_dir = self.checkpoints_dir / state.workflow_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_file = checkpoint_dir / f"stage_{state.current_stage}_complete.yaml"

        with open(checkpoint_file, "w") as f:
            yaml.dump(state.to_dict(), f, default_flow_style=False, allow_unicode=True)

        return checkpoint_file

    def load_latest_checkpoint(self, workflow_id: str) -> Optional[WorkflowState]:
        """Load the latest checkpoint for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowState from latest checkpoint, None if no checkpoints
        """
        checkpoint_dir = self.checkpoints_dir / workflow_id
        if not checkpoint_dir.exists():
            return None

        checkpoints = sorted(checkpoint_dir.glob("stage_*_complete.yaml"))
        if not checkpoints:
            return None

        latest = checkpoints[-1]
        with open(latest) as f:
            data = yaml.safe_load(f)

        return WorkflowState.from_dict(data)

    def list_workflows(
        self,
        status_filter: Optional[WorkflowStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List all workflows with optional status filter.

        Args:
            status_filter: Filter by status (active, completed, failed)

        Returns:
            List of workflow summaries
        """
        workflows = []

        directories = {
            WorkflowStatus.ACTIVE: self.active_dir,
            WorkflowStatus.COMPLETED: self.completed_dir,
            WorkflowStatus.FAILED: self.failed_dir,
        }

        if status_filter:
            dirs_to_check = {status_filter: directories.get(status_filter)}
        else:
            dirs_to_check = directories

        for status, directory in dirs_to_check.items():
            if directory and directory.exists():
                for file_path in directory.glob("*.yaml"):
                    try:
                        with open(file_path) as f:
                            data = yaml.safe_load(f)
                        workflows.append(
                            {
                                "workflow_id": data.get("workflow_id"),
                                "mode": data.get("mode"),
                                "skill_name": data.get("target", {}).get("skill_name"),
                                "status": data.get("progress", {}).get("status"),
                                "current_stage": data.get("progress", {}).get("current_stage"),
                                "progress_percent": data.get("progress", {}).get("progress_percent"),
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                            }
                        )
                    except Exception:
                        pass

        # Sort by updated_at descending
        workflows.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return workflows

    def delete(self, workflow_id: str, keep_checkpoints: bool = False) -> bool:
        """Delete a workflow and optionally its checkpoints.

        Args:
            workflow_id: Workflow identifier
            keep_checkpoints: If True, preserve checkpoints

        Returns:
            True if workflow was deleted
        """
        deleted = False

        for directory in [self.active_dir, self.completed_dir, self.failed_dir]:
            file_path = directory / f"{workflow_id}.yaml"
            if file_path.exists():
                file_path.unlink()
                deleted = True

        if not keep_checkpoints:
            checkpoint_dir = self.checkpoints_dir / workflow_id
            if checkpoint_dir.exists():
                shutil.rmtree(checkpoint_dir)

        return deleted

    def move_to_status(self, workflow_id: str, new_status: WorkflowStatus) -> bool:
        """Move a workflow to a different status directory.

        Args:
            workflow_id: Workflow identifier
            new_status: New status

        Returns:
            True if moved successfully
        """
        state = self.load(workflow_id)
        if not state:
            return False

        # Delete from current location
        for directory in [self.active_dir, self.completed_dir, self.failed_dir]:
            file_path = directory / f"{workflow_id}.yaml"
            if file_path.exists():
                file_path.unlink()

        # Update status and save to new location
        state.status = new_status
        self.save(state)
        return True
