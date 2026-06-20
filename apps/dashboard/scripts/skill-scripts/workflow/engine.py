"""
Workflow Engine.

Main orchestrator for the 5-stage plugin generation/refactoring workflow.
"""
# TODO_CLEANUP: This file is 824 lines — consider splitting into smaller modules

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Type

from .state_manager import (
    StateManager,
    WorkflowMode,
    WorkflowPhase,
    WorkflowState,
    WorkflowStatus,
)
from .stage_runner import StageRunner


class WorkflowEngine:
    """Main workflow orchestrator.

    Manages the 5-stage workflow:
    1. Baseline - Import/generate Layer 1 compliant skill
    2. Hardening - Enrich with triggers, tiers, safety
    3. Data Structures - Define schemas and storage patterns
    4. MCP/Actions - Define tools and dashboard actions
    5. UI Generation - Generate dashboard components
    """

    TOTAL_STAGES = 5

    def __init__(self, state_manager: Optional[StateManager] = None):
        """Initialize workflow engine.

        Args:
            state_manager: State persistence manager (created if not provided)
        """
        self.state_manager = state_manager or StateManager()
        self._stages: Dict[int, Type] = {}
        self._load_stages()

    def _load_stages(self):
        """Load stage implementations."""
        try:
            from ..stages import (
                Stage1Baseline,
                Stage2Hardening,
                Stage3Data,
                Stage4MCP,
                Stage5UI,
            )
        except ImportError:
            from stages import (
                Stage1Baseline,
                Stage2Hardening,
                Stage3Data,
                Stage4MCP,
                Stage5UI,
            )

        self._stages = {
            1: Stage1Baseline,
            2: Stage2Hardening,
            3: Stage3Data,
            4: Stage4MCP,
            5: Stage5UI,
        }

    def start_workflow(
        self,
        mode: str,
        skill_name: Optional[str] = None,
        source_path: Optional[str] = None,
        # Track 3b: `bundle` is the plugin BUNDLE name (lifestyle/ai/dev/...),
        # NOT a hub id from config/system/hubs.yaml. Default reflects the
        # most common user-facing personal-skill bundle.
        bundle: str = "lifestyle",
        target_profile: str = "standard",
        auto_mode: bool = False,
        run_scoring: bool = True,
        page_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a new plugin generation/refactoring workflow.

        Args:
            mode: 'new' for generation, 'refactor' for existing plugin
            skill_name: Name for new skill (required for 'new' mode)
            source_path: Path to existing plugin (required for 'refactor' mode)
            bundle: Target bundle (core, career, growth, finance, health, productivity, lifestyle, ai, admin, observe, dev, etc.)
            target_profile: Target profile (minimal, standard, full)
            auto_mode: Skip user questions, use defaults
            run_scoring: Run quality scoring before/after refactoring (refactor mode only)
            page_id: Optional page/tab ID for page-level scoring (e.g., 'recipes')

        Returns:
            Dict with workflow_id and initial status
        """
        # Validate inputs
        workflow_mode = WorkflowMode(mode)

        if workflow_mode == WorkflowMode.NEW:
            if not skill_name:
                return {"success": False, "error": "skill_name required for 'new' mode"}
            # Normalize skill name to kebab-case
            skill_name = skill_name.lower().replace("_", "-").replace(" ", "-")
        else:
            if not source_path:
                return {"success": False, "error": "source_path required for 'refactor' mode"}
            # Extract skill name from source path
            source = Path(source_path)
            if not source.exists():
                return {"success": False, "error": f"Source path not found: {source_path}"}
            skill_name = source.name

        # Check if skill already exists (for new mode)
        if workflow_mode == WorkflowMode.NEW:
            skill_path = self._get_skill_path(skill_name, bundle)
            if skill_path.exists():
                return {
                    "success": False,
                    "error": f"Skill '{skill_name}' already exists at {skill_path}",
                    "hint": "Use mode='refactor' to modify existing skill",
                }

        # Create workflow state
        workflow_id = self.state_manager.generate_workflow_id()

        state = WorkflowState(
            workflow_id=workflow_id,
            mode=workflow_mode,
            auto_mode=auto_mode,
            skill_name=skill_name,
            bundle=bundle,
            target_profile=target_profile,
            source_path=source_path,
        )

        # For refactor mode, create backup
        if workflow_mode == WorkflowMode.REFACTOR and source_path:
            backup_path = self._create_backup(Path(source_path), workflow_id)
            state.backup_path = str(backup_path)

            # Run initial quality scoring if enabled and not auto mode
            if run_scoring and not auto_mode:
                scoring_result = self._run_initial_scoring(state, page_id=page_id)
                state.scoring_data = scoring_result

                # Pause for scoring questions
                if scoring_result.get("questions"):
                    state.status = WorkflowStatus.PAUSED
                    state.pending_questions = scoring_result["questions"]

        # Save initial state
        self.state_manager.save(state)

        result = {
            "success": True,
            "workflow_id": workflow_id,
            "mode": mode,
            "skill_name": skill_name,
            "bundle": bundle,
            "target_profile": target_profile,
            "auto_mode": auto_mode,
            "status": state.status.value,
            "current_stage": 1,
            "current_phase": "plan",
        }

        # Include page info if page-level scoring
        if page_id:
            result["page_id"] = page_id
            result["scoring_level"] = "page"
        else:
            result["scoring_level"] = "plugin"

        # Include scoring info if enabled
        if run_scoring and state.scoring_data:
            result["scoring_enabled"] = True
            result["initial_score"] = state.scoring_data.get("before_score", {}).get("overall_score")
            result["initial_tier"] = state.scoring_data.get("before_score", {}).get("tier")
            result["page_id"] = state.scoring_data.get("page_id")
            if state.pending_questions:
                result["pending_questions"] = state.pending_questions
                result["message"] = "Quality assessment questions pending. Submit answers to continue."

        return result

    def resume_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Resume an interrupted workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Dict with current status and next action needed
        """
        # Try to load from active workflows
        state = self.state_manager.load(workflow_id)

        if not state:
            # Try checkpoint
            state = self.state_manager.load_latest_checkpoint(workflow_id)
            if state:
                # Resume from checkpoint means starting next stage
                state.current_phase = WorkflowPhase.PLAN
                state.status = WorkflowStatus.ACTIVE

        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        # If completed or failed, just return status
        if state.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.ABORTED):
            return {
                "success": True,
                "workflow_id": workflow_id,
                "status": state.status.value,
                "message": f"Workflow is {state.status.value}",
                "skill_name": state.skill_name,
                "stages_completed": state.stages_completed,
            }

        # If paused waiting for input, return pending questions
        if state.status == WorkflowStatus.PAUSED and state.pending_questions:
            return {
                "success": True,
                "workflow_id": workflow_id,
                "status": "waiting_for_input",
                "current_stage": state.current_stage,
                "current_phase": state.current_phase.value,
                "pending_questions": state.pending_questions,
                "message": "Workflow paused waiting for user answers",
            }

        # Continue execution
        state.status = WorkflowStatus.ACTIVE
        return self._run_current_stage(state)

    def advance_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Advance workflow to next stage.

        Called after user answers are submitted.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Dict with new status
        """
        state = self.state_manager.load(workflow_id)
        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        # Move to next stage
        if state.current_stage < self.TOTAL_STAGES:
            state.current_stage += 1
            state.current_phase = WorkflowPhase.PLAN
            state.status = WorkflowStatus.ACTIVE
            state.pending_questions = []
            self.state_manager.save(state)

            return self._run_current_stage(state)
        else:
            # Workflow complete
            state.status = WorkflowStatus.COMPLETED
            self.state_manager.save(state)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "status": "completed",
                "skill_name": state.skill_name,
                "skill_path": str(state.skill_path),
                "stages_completed": state.stages_completed,
            }

    def submit_answers(
        self,
        workflow_id: str,
        answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit user answers for current stage questions.

        Args:
            workflow_id: Workflow identifier
            answers: Dict mapping question_id to answer value

        Returns:
            Dict with submission result and next action
        """
        state = self.state_manager.load(workflow_id)
        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        if not state.pending_questions:
            return {
                "success": False,
                "error": "No pending questions for this workflow",
                "status": state.status.value,
            }

        # Validate all required questions are answered
        pending_ids = {q.get("id") for q in state.pending_questions}
        missing = pending_ids - set(answers.keys())

        # Check if any missing are required
        required_missing = []
        for q in state.pending_questions:
            if q.get("id") in missing and q.get("required", True):
                required_missing.append(q.get("id"))

        if required_missing:
            return {
                "success": False,
                "error": f"Missing required answers: {required_missing}",
            }

        # Store answers
        state.user_answers[state.current_stage] = answers
        state.pending_questions = []

        # Save and advance
        self.state_manager.save(state)

        return self.advance_workflow(workflow_id)

    def get_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get current workflow status.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Dict with complete workflow state
        """
        state = self.state_manager.load(workflow_id)
        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        return {
            "success": True,
            "workflow_id": workflow_id,
            "mode": state.mode.value,
            "auto_mode": state.auto_mode,
            "skill_name": state.skill_name,
            "bundle": state.bundle,
            "target_profile": state.target_profile,
            "skill_path": str(state.skill_path),
            "status": state.status.value,
            "current_stage": state.current_stage,
            "current_phase": state.current_phase.value,
            "stages_completed": state.stages_completed,
            "progress_percent": state.progress_percent,
            "pending_questions": state.pending_questions,
            "last_error": state.last_error,
            "retry_count": state.retry_count,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
        }

    def abort_workflow(
        self,
        workflow_id: str,
        cleanup: bool = False,
    ) -> Dict[str, Any]:
        """Abort a running workflow.

        Args:
            workflow_id: Workflow identifier
            cleanup: If True, delete generated files (restore backup for refactor)

        Returns:
            Dict with abort result
        """
        state = self.state_manager.load(workflow_id)
        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        # Cleanup if requested
        if cleanup:
            if state.mode == WorkflowMode.REFACTOR and state.backup_path:
                # Restore from backup
                backup = Path(state.backup_path)
                target = state.skill_path
                if backup.exists() and target.exists():
                    shutil.rmtree(target)
                    shutil.copytree(backup, target)
            elif state.mode == WorkflowMode.NEW:
                # Remove generated skill directory
                if state.skill_path.exists():
                    shutil.rmtree(state.skill_path)

        state.status = WorkflowStatus.ABORTED
        self.state_manager.save(state)

        return {
            "success": True,
            "workflow_id": workflow_id,
            "status": "aborted",
            "cleanup_performed": cleanup,
        }

    def list_workflows(
        self,
        status_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all workflows.

        Args:
            status_filter: Filter by status (active, completed, failed)

        Returns:
            Dict with workflow list
        """
        status = WorkflowStatus(status_filter) if status_filter else None
        workflows = self.state_manager.list_workflows(status)

        return {
            "success": True,
            "count": len(workflows),
            "workflows": workflows,
        }

    def get_available_pages(self, source_path: str) -> Dict[str, Any]:
        """Get available pages/tabs for page-level scoring.

        Args:
            source_path: Path to the skill directory

        Returns:
            Dict with list of available pages
        """
        try:
            from ..scoring import QualityScorer
        except ImportError:
            from scoring import QualityScorer

        skill_path = Path(source_path)
        if not skill_path.exists():
            return {"success": False, "error": f"Path not found: {source_path}"}

        pages = QualityScorer.get_available_pages(skill_path)

        return {
            "success": True,
            "skill_name": skill_path.name,
            "pages": pages,
            "count": len(pages),
            "hint": "Use page_id parameter with start_workflow for page-level scoring",
        }

    def _run_current_stage(self, state: WorkflowState) -> Dict[str, Any]:
        """Run the current stage.

        Args:
            state: Workflow state

        Returns:
            Dict with execution result
        """
        stage_num = state.current_stage

        if stage_num not in self._stages:
            return {
                "success": False,
                "error": f"Stage {stage_num} not implemented yet",
                "workflow_id": state.workflow_id,
            }

        # Create stage instance
        stage_class = self._stages[stage_num]
        stage = stage_class()

        # Create runner and execute
        runner = StageRunner(stage, state)
        result = runner.run()

        # Update state based on result
        if result.completed:
            # Stage completed, save output
            state.stage_outputs[stage_num] = result.output
            self.state_manager.checkpoint(state)

            if stage_num < self.TOTAL_STAGES:
                # More stages to go
                state.current_stage = stage_num + 1
                state.current_phase = WorkflowPhase.PLAN
                self.state_manager.save(state)

                return {
                    "success": True,
                    "workflow_id": state.workflow_id,
                    "stage_completed": stage_num,
                    "next_stage": stage_num + 1,
                    "status": "active",
                    "message": f"Stage {stage_num} complete, starting stage {stage_num + 1}",
                }
            else:
                # All stages complete
                state.status = WorkflowStatus.COMPLETED
                self.state_manager.save(state)

                return {
                    "success": True,
                    "workflow_id": state.workflow_id,
                    "status": "completed",
                    "skill_name": state.skill_name,
                    "skill_path": str(state.skill_path),
                    "stages_completed": list(range(1, self.TOTAL_STAGES + 1)),
                }

        elif result.needs_user_input:
            # Paused for user input
            self.state_manager.save(state)

            return {
                "success": True,
                "workflow_id": state.workflow_id,
                "status": "waiting_for_input",
                "current_stage": stage_num,
                "current_phase": state.current_phase.value,
                "pending_questions": result.pending_questions,
                "message": "Waiting for user answers",
            }

        else:
            # Stage failed
            self.state_manager.save(state)

            return {
                "success": False,
                "workflow_id": state.workflow_id,
                "status": state.status.value,
                "current_stage": stage_num,
                "error": result.error or "Stage execution failed",
                "retry_count": state.retry_count,
                "message": (
                    "Stage failed after max retries" if state.retry_count >= state.max_retries else "Stage failed"
                ),
            }

    def _get_skill_path(self, skill_name: str, bundle: str) -> Path:
        """Get the path where a skill would be created."""
        try:
            from src.config.paths import get_project_root
            project_root = get_project_root()
        except ImportError:
            project_root = Path(__file__).parent.parent.parent.parent.parent.parent  # fallback
        return project_root / "plugins" / bundle / "skills" / skill_name

    def _create_backup(self, source_path: Path, workflow_id: str) -> Path:
        """Create a backup of an existing skill.

        Args:
            source_path: Path to skill to backup
            workflow_id: Workflow ID for backup naming

        Returns:
            Path to backup directory
        """
        # Backup to data directory
        data_base = self.state_manager.base_dir.parent  # skills/mcp-app-factory/augur/
        backup_dir = data_base / "backups" / f"{source_path.name}-{workflow_id[:20]}"
        backup_dir.parent.mkdir(parents=True, exist_ok=True)

        shutil.copytree(source_path, backup_dir)
        return backup_dir

    def _run_initial_scoring(
        self,
        state: WorkflowState,
        page_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run initial quality scoring for refactor mode.

        Args:
            state: Workflow state
            page_id: Optional page/tab ID for page-level scoring

        Returns:
            Dict with scoring data including before_score and questions
        """
        try:
            from ..scoring import QualityScorer
        except ImportError:
            from scoring import QualityScorer

        skill_path = state.skill_path
        if state.source_path:
            skill_path = Path(state.source_path)

        # Create scorer with page_id if provided
        scorer = QualityScorer(skill_path, page_id=page_id)

        # If page_id provided but invalid, return available pages
        if page_id:
            available_pages = scorer.get_available_pages(skill_path)
            page_ids = [p.get("id") for p in available_pages if isinstance(p, dict)]
            if page_id not in page_ids:
                return {
                    "error": f"Page '{page_id}' not found",
                    "available_pages": available_pages,
                    "questions": [],
                }

        initial_score = scorer.score_plugin()
        questions = scorer.generate_assessment_questions(initial_score)

        return {
            "before_score": initial_score.to_dict(),
            "after_score": None,
            "comparison": None,
            "user_answers": {},
            "loop_iteration": 0,
            "approved": False,
            "questions": questions,
            "page_id": page_id,  # Store for later comparison
            "scoring_level": "page" if page_id else "plugin",
        }

    def complete_scoring_loop(self, workflow_id: str) -> Dict[str, Any]:
        """Run scoring after refactoring stages complete.

        Called after all 5 stages finish to compare before/after.
        Returns comparison and asks user to approve or continue looping.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Dict with comparison results and approval question
        """
        state = self.state_manager.load(workflow_id)
        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        if state.status != WorkflowStatus.COMPLETED:
            return {"success": False, "error": "Workflow must be completed before scoring loop"}

        if not state.scoring_data or not state.scoring_data.get("before_score"):
            return {"success": False, "error": "No initial scoring data found"}

        try:
            from ..scoring import QualityScorer, compare_scores, QualityScore
        except ImportError:
            from scoring import QualityScorer, compare_scores, QualityScore

        # Run after scoring (use same page_id as initial scoring)
        page_id = state.scoring_data.get("page_id")
        scorer = QualityScorer(state.skill_path, page_id=page_id)
        user_answers = state.scoring_data.get("user_answers", {})
        after_score = scorer.score_plugin(user_answers)

        # Compare scores
        before_score = QualityScore.from_dict(state.scoring_data["before_score"])
        comparison = compare_scores(before_score, after_score)

        # Update state
        state.scoring_data["after_score"] = after_score.to_dict()
        state.scoring_data["comparison"] = comparison.to_dict()
        state.scoring_data["loop_iteration"] += 1

        # Generate approval question
        state.status = WorkflowStatus.PAUSED
        state.pending_questions = [
            {
                "id": "approve_refactor",
                "text": f"Quality improved by {comparison.overall_delta:+.1f} points ({comparison.before_tier} -> {comparison.after_tier}). Approve this refactor?",
                "type": "choice",
                "options": [
                    {"value": "approve", "label": "Approve - Accept current state"},
                    {"value": "continue", "label": "Continue - Run another refactoring iteration"},
                    {"value": "revert", "label": "Revert - Restore from backup"},
                ],
                "context": f"Summary: {comparison.summary.get('recommendation', '')}",
                "required": True,
            }
        ]

        self.state_manager.save(state)

        return {
            "success": True,
            "workflow_id": workflow_id,
            "status": "scoring_complete",
            "before_score": state.scoring_data["before_score"]["overall_score"],
            "after_score": after_score.overall_score,
            "improvement": comparison.overall_delta,
            "before_tier": comparison.before_tier,
            "after_tier": comparison.after_tier,
            "comparison": comparison.to_dict(),
            "pending_questions": state.pending_questions,
            "recommendation": comparison.summary.get("recommendation", ""),
        }

    def handle_scoring_answer(
        self,
        workflow_id: str,
        answer: str,
    ) -> Dict[str, Any]:
        """Handle user's answer to scoring approval question.

        Args:
            workflow_id: Workflow identifier
            answer: User's answer ('approve', 'continue', or 'revert')

        Returns:
            Dict with result of the action
        """
        state = self.state_manager.load(workflow_id)
        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        if answer == "approve":
            # Mark as approved and complete
            state.scoring_data["approved"] = True
            state.status = WorkflowStatus.COMPLETED
            state.pending_questions = []
            self.state_manager.save(state)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "status": "approved",
                "message": "Refactoring approved!",
                "final_score": state.scoring_data.get("after_score", {}).get("overall_score"),
                "improvement": state.scoring_data.get("comparison", {}).get("overall", {}).get("delta"),
            }

        elif answer == "continue":
            # Reset to stage 1 for another iteration
            state.current_stage = 1
            state.current_phase = WorkflowPhase.PLAN
            state.status = WorkflowStatus.ACTIVE
            state.pending_questions = []
            state.retry_count = 0

            # Clear stage outputs for re-run
            state.stage_outputs = {}

            # Update before_score to current after_score for next comparison
            if state.scoring_data.get("after_score"):
                state.scoring_data["before_score"] = state.scoring_data["after_score"]
                state.scoring_data["after_score"] = None
                state.scoring_data["comparison"] = None

            self.state_manager.save(state)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "status": "continuing",
                "message": f"Starting iteration {state.scoring_data['loop_iteration'] + 1}",
                "current_stage": 1,
                "current_phase": "plan",
            }

        elif answer == "revert":
            # Restore from backup
            if state.backup_path:
                backup_path = Path(state.backup_path)
                if backup_path.exists():
                    # Remove current skill directory
                    if state.skill_path.exists():
                        shutil.rmtree(state.skill_path)
                    # Restore from backup
                    shutil.copytree(backup_path, state.skill_path)

            state.status = WorkflowStatus.ABORTED
            state.pending_questions = []
            self.state_manager.save(state)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "status": "reverted",
                "message": "Plugin restored from backup",
            }

        else:
            return {
                "success": False,
                "error": f"Invalid answer: {answer}. Must be 'approve', 'continue', or 'revert'",
            }

    def submit_scoring_answers(
        self,
        workflow_id: str,
        answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Submit answers to scoring assessment questions.

        Args:
            workflow_id: Workflow identifier
            answers: Dict mapping question_id to answer value

        Returns:
            Dict with result and next action
        """
        state = self.state_manager.load(workflow_id)
        if not state:
            return {"success": False, "error": f"Workflow not found: {workflow_id}"}

        if not state.scoring_data:
            return {"success": False, "error": "No scoring data found"}

        # Check for approval question
        if "approve_refactor" in answers:
            return self.handle_scoring_answer(workflow_id, answers["approve_refactor"])

        # Store scoring answers
        state.scoring_data["user_answers"] = answers
        state.pending_questions = []
        state.status = WorkflowStatus.ACTIVE
        self.state_manager.save(state)

        return {
            "success": True,
            "workflow_id": workflow_id,
            "status": "scoring_answers_submitted",
            "message": "Scoring answers submitted. Ready to run refactoring stages.",
            "current_stage": state.current_stage,
            "current_phase": state.current_phase.value,
        }
