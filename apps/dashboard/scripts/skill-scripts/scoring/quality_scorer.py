"""
Quality Scorer.

Main orchestrator for plugin quality scoring.
Coordinates analysis, research, scoring, and questionnaire generation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from .analyzer import (
    PageCapabilities,
    PluginCapabilities,
    extract_page_capabilities,
    extract_problem_statement,
    get_available_pages,
)
from .dimensions import (
    DimensionScore,
    QualityScore,
    ScoreDimension,
)
from .normalizer import (
    calculate_overall_score,
    classify_tier,
)
from .questionnaire import get_default_questions
from .scoring_page import (
    score_page_action_coverage,
    score_page_capability_completeness,
    score_page_data_support,
    score_page_problem_alignment,
    score_page_ui_access,
    score_page_user_journey_fit,
)
from .scoring_plugin import (
    score_action_coverage,
    score_capability_completeness,
    score_data_support,
    score_problem_alignment,
    score_ui_access,
    score_user_journey_fit,
)
from .user_research import UserExpectationModel, get_default_expectations


class QualityScorer:
    """Main quality scoring orchestrator.

    Coordinates the scoring process:
    1. Extract problem statement from plugin files (or page-specific)
    2. Research user expectations (optional web search)
    3. Score each dimension
    4. Normalize and aggregate scores
    5. Generate assessment questions

    Supports both plugin-level and page-level scoring:
    - Plugin-level: Scores the entire plugin across all capabilities
    - Page-level: Scores a specific page/tab (e.g., recipes, movies, reading)
    """

    def __init__(
        self,
        skill_path: Path,
        page_id: Optional[str] = None,
        web_search_func: Optional[Callable] = None,
    ):
        """Initialize quality scorer.

        Args:
            skill_path: Path to the skill directory
            page_id: Optional page/tab ID for page-level scoring (e.g., 'recipes')
            web_search_func: Optional function for web research
        """
        self.skill_path = Path(skill_path)
        self.skill_name = self.skill_path.name
        self.page_id = page_id
        self.web_search_func = web_search_func

        # Cached analysis results
        self._capabilities: Optional[PluginCapabilities] = None
        self._page_capabilities: Optional[PageCapabilities] = None
        self._expectations: Optional[UserExpectationModel] = None

    @classmethod
    def get_available_pages(cls, skill_path: Path) -> List[Dict[str, Any]]:
        """Get available pages for page-level scoring.

        Args:
            skill_path: Path to the skill directory

        Returns:
            List of page dicts with id, label, icon
        """
        return get_available_pages(skill_path)

    def score_plugin(
        self,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> QualityScore:
        """Score the plugin (or page) across all dimensions.

        If page_id was provided during initialization, scores only that page.
        Otherwise, scores the entire plugin.

        Args:
            user_answers: Optional answers from quality assessment questionnaire

        Returns:
            QualityScore with all dimension scores
        """
        if self.page_id:
            return self._score_page(user_answers)
        else:
            return self._score_full_plugin(user_answers)

    def _score_full_plugin(
        self,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> QualityScore:
        """Score the entire plugin across all dimensions."""
        capabilities = self._get_capabilities()
        expectations = self._get_expectations(capabilities.problem_statement)

        dimension_scores: Dict[ScoreDimension, DimensionScore] = {}

        dimension_scores[ScoreDimension.PROBLEM_ALIGNMENT] = score_problem_alignment(capabilities, user_answers)
        dimension_scores[ScoreDimension.ACTION_COVERAGE] = score_action_coverage(capabilities, user_answers)
        dimension_scores[ScoreDimension.DATA_SUPPORT] = score_data_support(self.skill_path, capabilities, user_answers)
        dimension_scores[ScoreDimension.UI_ACCESS] = score_ui_access(capabilities, user_answers)
        dimension_scores[ScoreDimension.CAPABILITY_COMPLETENESS] = score_capability_completeness(self.skill_path, capabilities)
        dimension_scores[ScoreDimension.USER_JOURNEY_FIT] = score_user_journey_fit(capabilities, expectations)

        overall = calculate_overall_score(dimension_scores)
        tier = classify_tier(overall)
        gaps = self._identify_gaps(dimension_scores)
        priorities = self._identify_priorities(dimension_scores, user_answers)

        return QualityScore(
            plugin_name=self.skill_name,
            timestamp=datetime.utcnow().isoformat() + "Z",
            dimension_scores=dimension_scores,
            overall_score=overall,
            tier=tier,
            problem_statement=capabilities.problem_statement,
            user_expectations=expectations.typical_actions[:5],
            gaps_identified=gaps,
            improvement_priority=priorities,
        )

    def _score_page(
        self,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> QualityScore:
        """Score a specific page/tab within the plugin."""
        page_caps = self._get_page_capabilities()
        if not page_caps:
            return self._score_full_plugin(user_answers)

        expectations = UserExpectationModel(
            category=f"{self.skill_name}/{self.page_id}",
            typical_actions=page_caps.expected_user_actions,
            data_accumulation_patterns=page_caps.data_accumulation,
            fast_access_needs=page_caps.quick_access_needs,
            common_workflows=[],
            pain_points=[],
        )

        dimension_scores: Dict[ScoreDimension, DimensionScore] = {}

        dimension_scores[ScoreDimension.PROBLEM_ALIGNMENT] = score_page_problem_alignment(page_caps, user_answers)
        dimension_scores[ScoreDimension.ACTION_COVERAGE] = score_page_action_coverage(page_caps, user_answers)
        dimension_scores[ScoreDimension.DATA_SUPPORT] = score_page_data_support(page_caps, user_answers)
        dimension_scores[ScoreDimension.UI_ACCESS] = score_page_ui_access(page_caps, user_answers)
        dimension_scores[ScoreDimension.CAPABILITY_COMPLETENESS] = score_page_capability_completeness(page_caps)
        dimension_scores[ScoreDimension.USER_JOURNEY_FIT] = score_page_user_journey_fit(page_caps, expectations)

        overall = calculate_overall_score(dimension_scores)
        tier = classify_tier(overall)
        gaps = self._identify_gaps(dimension_scores)
        priorities = self._identify_priorities(dimension_scores, user_answers)

        display_name = f"{self.skill_name}/{page_caps.page_label}"

        return QualityScore(
            plugin_name=display_name,
            timestamp=datetime.utcnow().isoformat() + "Z",
            dimension_scores=dimension_scores,
            overall_score=overall,
            tier=tier,
            problem_statement=page_caps.problem_statement,
            user_expectations=expectations.typical_actions[:5],
            gaps_identified=gaps,
            improvement_priority=priorities,
        )

    def generate_assessment_questions(
        self,
        initial_score: Optional[QualityScore] = None,
    ) -> List[Dict[str, Any]]:
        """Generate quality assessment questions.

        For page-level scoring, questions are contextualized to the specific page.

        Args:
            initial_score: Optional initial score for context

        Returns:
            List of question dicts for user input
        """
        questions = self._load_question_template()

        if self.page_id:
            page_caps = self._get_page_capabilities()
            if page_caps:
                questions = self._contextualize_questions_for_page(questions, page_caps)

        return questions

    def _load_question_template(self) -> List[Dict[str, Any]]:
        """Load questionnaire template from file."""
        template_path = Path(__file__).parent.parent / "questionnaires" / "templates" / "quality_assessment.yaml"

        if template_path.exists():
            try:
                with open(template_path, encoding="utf-8") as f:
                    template = yaml.safe_load(f) or {}
                return template.get("questions", [])
            except (yaml.YAMLError, OSError):
                pass

        try:
            from src.config.paths import get_project_root
            questionnaire_root = get_project_root() / "apps" / "dashboard" / "scripts" / "skill-scripts"
        except ImportError:
            questionnaire_root = self.skill_path.parent.parent.parent  # fallback
        template_path = (
            questionnaire_root
            / "questionnaires"
            / "templates"
            / "quality_assessment.yaml"
        )

        if template_path.exists():
            try:
                with open(template_path, encoding="utf-8") as f:
                    template = yaml.safe_load(f) or {}
                return template.get("questions", [])
            except (yaml.YAMLError, OSError):
                pass

        return get_default_questions()

    def _contextualize_questions_for_page(
        self,
        questions: List[Dict[str, Any]],
        page_caps: PageCapabilities,
    ) -> List[Dict[str, Any]]:
        """Contextualize questions for a specific page."""
        contextualized = []
        page_name = page_caps.page_label

        for q in questions:
            new_q = q.copy()
            text = new_q.get("text", "")
            text = text.replace("this plugin", f"the {page_name} page")
            text = text.replace("the plugin", f"the {page_name} page")
            new_q["text"] = text

            context = new_q.get("context", "")
            if context:
                context = context.replace("plugin", f"{page_name} page")
                new_q["context"] = context

            contextualized.append(new_q)

        if contextualized:
            contextualized.insert(
                0,
                {
                    "id": "_page_context",
                    "type": "info",
                    "text": f"📄 **Evaluating: {page_name}** (part of {self.skill_name})",
                    "context": f"These questions focus specifically on the {page_name} functionality.",
                },
            )

        return contextualized

    def _get_capabilities(self) -> PluginCapabilities:
        """Get or extract plugin capabilities."""
        if self._capabilities is None:
            self._capabilities = extract_problem_statement(self.skill_path)
        return self._capabilities

    def _get_expectations(self, problem_statement: str) -> UserExpectationModel:
        """Get or research user expectations."""
        if self._expectations is None:
            self._expectations = get_default_expectations(self.skill_name)
        return self._expectations

    def _get_page_capabilities(self) -> Optional[PageCapabilities]:
        """Get or extract page capabilities."""
        if self._page_capabilities is None and self.page_id:
            self._page_capabilities = extract_page_capabilities(self.skill_path, self.page_id)
        return self._page_capabilities

    def _identify_gaps(
        self,
        dimension_scores: Dict[ScoreDimension, DimensionScore],
    ) -> List[str]:
        """Identify gaps from all dimension issues."""
        gaps: List[str] = []
        for score in dimension_scores.values():
            gaps.extend(score.issues)
        return gaps[:10]

    def _identify_priorities(
        self,
        dimension_scores: Dict[ScoreDimension, DimensionScore],
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Identify improvement priorities."""
        priorities: List[str] = []

        sorted_dims = sorted(
            dimension_scores.items(),
            key=lambda x: x[1].normalized_score,
        )

        for dim, score in sorted_dims[:3]:
            if score.suggestions:
                priorities.append(score.suggestions[0])

        if user_answers and user_answers.get("improvement_priority"):
            user_priorities = user_answers["improvement_priority"]
            if isinstance(user_priorities, list):
                priorities.extend(user_priorities[:3])
            elif isinstance(user_priorities, str):
                priorities.append(user_priorities)

        return priorities[:5]
