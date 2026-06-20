"""
Question Generation Logic.

Handles loading templates and generating context-aware questions
based on workflow state and stage artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_template_path(stage_num: int) -> Path:
    """Get the path to a stage's question template."""
    return TEMPLATES_DIR / f"stage_{stage_num}.yaml"


def load_template(stage_num: int) -> Dict[str, Any]:
    """Load a stage's question template.

    Args:
        stage_num: Stage number (1-5)

    Returns:
        Template dictionary with questions and metadata
    """
    template_path = get_template_path(stage_num)
    if not template_path.exists():
        return {"questions": []}

    with open(template_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"questions": []}


class QuestionGenerator:
    """Generates context-aware questions for workflow stages."""

    def __init__(self):
        """Initialize the question generator."""
        self.templates: Dict[int, Dict[str, Any]] = {}

    def get_template(self, stage_num: int) -> Dict[str, Any]:
        """Get or load a template for a stage."""
        if stage_num not in self.templates:
            self.templates[stage_num] = load_template(stage_num)
        return self.templates[stage_num]

    def generate_questions(
        self,
        stage_num: int,
        context: Dict[str, Any],
        validation_issues: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate context-aware questions for a stage.

        Args:
            stage_num: Stage number (1-5)
            context: Context variables for template substitution
            validation_issues: List of validation issues to address

        Returns:
            List of question dictionaries
        """
        template = self.get_template(stage_num)
        questions = []

        for q_template in template.get("questions", []):
            question = self._apply_context(q_template.copy(), context)

            # Add validation-specific questions if there are issues
            if validation_issues and q_template.get("validation_related"):
                relevant_issues = [issue for issue in validation_issues if q_template.get("id") in issue.lower()]
                if relevant_issues:
                    question["context"] = (
                        question.get("context", "") + f"\n\nValidation issues: {'; '.join(relevant_issues)}"
                    )

            questions.append(question)

        return questions

    def _apply_context(
        self,
        question: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply context variables to a question template.

        Args:
            question: Question template
            context: Context variables

        Returns:
            Question with variables substituted
        """
        for key in ["text", "default", "context"]:
            if key in question and isinstance(question[key], str):
                for var_name, var_value in context.items():
                    placeholder = f"${{{var_name}}}"
                    question[key] = question[key].replace(placeholder, str(var_value))

        return question

    def get_default_answers(
        self,
        stage_num: int,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get default answers for a stage (used in auto mode).

        Args:
            stage_num: Stage number (1-5)
            context: Context variables

        Returns:
            Dictionary mapping question_id to default value
        """
        template = self.get_template(stage_num)
        defaults = {}

        for q_template in template.get("questions", []):
            q_id = q_template.get("id")
            default = q_template.get("default", "")

            # Apply context to default
            if isinstance(default, str):
                for var_name, var_value in context.items():
                    placeholder = f"${{{var_name}}}"
                    default = default.replace(placeholder, str(var_value))

            defaults[q_id] = default

        return defaults
