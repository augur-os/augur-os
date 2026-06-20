"""
Base Stage Abstract Class.

Defines the interface that all stage implementations must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ._imports import StageOutput, WorkflowState, ValidationResult


class BaseStage(ABC):
    """Abstract base class for workflow stages.

    Each stage must implement:
    - plan(): Create execution plan
    - execute(): Generate/modify files
    - test(): Run automated checks
    - validate(): Check acceptance criteria
    - generate_questions(): Create context-aware user questions
    - get_output(): Return stage output data
    """

    @property
    @abstractmethod
    def stage_num(self) -> int:
        """Stage number (1-5)."""
        pass

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Human-readable stage name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Stage description."""
        pass

    @abstractmethod
    def plan(
        self,
        state: "WorkflowState",
        previous_output: Optional["StageOutput"] = None,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create execution plan for this stage.

        Args:
            state: Current workflow state
            previous_output: Output from previous stage (if any)
            user_answers: User answers from retry (if any)

        Returns:
            Dict containing the execution plan with:
            - steps: List of steps to execute
            - files_to_create: Files that will be created
            - files_to_modify: Files that will be modified
            - expected_output: What success looks like
        """
        pass

    @abstractmethod
    def execute(
        self,
        state: "WorkflowState",
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the plan to generate/modify files.

        Args:
            state: Current workflow state
            plan: Execution plan from plan()

        Returns:
            Dict containing execution artifacts:
            - files_created: List of created file paths
            - files_modified: List of modified file paths
            - data: Any additional data produced
        """
        pass

    @abstractmethod
    def test(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run automated tests on the artifacts.

        Args:
            state: Current workflow state
            artifacts: Artifacts from execute()

        Returns:
            Dict mapping test name to result:
            - {test_name: {"passed": bool, "message": str, "details": any}}
        """
        pass

    @abstractmethod
    def validate(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        test_results: Dict[str, Any],
    ) -> "ValidationResult":
        """Validate against acceptance criteria.

        Args:
            state: Current workflow state
            artifacts: Artifacts from execute()
            test_results: Results from test()

        Returns:
            ValidationResult with pass/fail and issues
        """
        pass

    @abstractmethod
    def generate_questions(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        validation: Optional["ValidationResult"] = None,
    ) -> List[Dict[str, Any]]:
        """Generate context-aware questions for the user.

        Args:
            state: Current workflow state
            artifacts: Artifacts from execute()
            validation: Validation result (if available)

        Returns:
            List of question dicts with:
            - id: Unique question identifier
            - text: Question text (may include context variables)
            - type: text, choice, multi_choice, yes_no, confirm
            - options: List of options (for choice types)
            - default: Default value
            - required: Whether answer is required
            - context: Additional context to show user
        """
        pass

    @abstractmethod
    def get_output(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get the stage output data.

        Called after successful completion to collect data
        that should be passed to subsequent stages.

        Args:
            state: Current workflow state

        Returns:
            Dict of output data for this stage
        """
        pass

    def get_acceptance_criteria(self) -> List[str]:
        """Get list of acceptance criteria for this stage.

        Returns:
            List of criteria descriptions
        """
        return []

    def get_default_answers(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get default answers for auto mode.

        Args:
            state: Current workflow state

        Returns:
            Dict mapping question_id to default value
        """
        return {}
