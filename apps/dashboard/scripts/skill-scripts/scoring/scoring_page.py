"""
Page-level scoring methods for QualityScorer.

Scores individual pages/tabs within a plugin across all quality dimensions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .analyzer import PageCapabilities
from .dimensions import DIMENSION_WEIGHTS, DimensionScore, ScoreDimension
from .normalizer import calculate_dimension_raw_score, normalize_score
from .user_research import UserExpectationModel


def _get_action_dispatch(action: Dict[str, Any]) -> Optional[str]:
    """Read canonical dispatch first, then map legacy flow values."""
    dispatch = action.get("dispatch")
    if dispatch:
        return dispatch

    flow = action.get("flow")
    if flow == "fast":
        return "fire"
    if flow == "llm":
        return "oneshot"
    return flow


def score_page_problem_alignment(
    page_caps: PageCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score PROBLEM_ALIGNMENT for a specific page."""
    components: Dict[str, float] = {}
    max_points = {
        "problem_statement_clarity": 25,
        "capabilities_present": 25,
        "expected_actions_match": 30,
        "user_score": 20,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Problem statement clarity (0-25)
    if page_caps.problem_statement and len(page_caps.problem_statement) > 20:
        components["problem_statement_clarity"] = 25
    elif page_caps.problem_statement:
        components["problem_statement_clarity"] = 15
        issues.append(f"Vague problem statement for {page_caps.page_label}")
        suggestions.append(f"Add more specific description for {page_caps.page_label} page")
    else:
        components["problem_statement_clarity"] = 0
        issues.append(f"No problem statement for {page_caps.page_label}")
        suggestions.append(f"Add ### {page_caps.page_label} section in SKILL.md")

    # Capabilities present (0-25)
    cap_count = len(page_caps.stated_capabilities)
    if cap_count >= 3:
        components["capabilities_present"] = 25
    elif cap_count >= 1:
        components["capabilities_present"] = 15
    else:
        components["capabilities_present"] = 5
        issues.append(f"No capabilities listed for {page_caps.page_label}")
        suggestions.append(f"Add capabilities for {page_caps.page_label} in SKILL.md")

    # Expected actions match (0-30) - how many expected actions are covered
    expected = page_caps.expected_user_actions
    actions_text = " ".join([a.get("label", "").lower() for a in page_caps.actions])
    covered = 0
    for exp in expected:
        exp_words = set(exp.lower().split())
        if any(w in actions_text for w in exp_words):
            covered += 1

    if expected:
        coverage = covered / len(expected)
        components["expected_actions_match"] = coverage * 30
        if coverage < 0.5:
            uncovered = [e for e in expected if not any(w in actions_text for w in e.lower().split())][:3]
            issues.append(f"Missing expected actions for {page_caps.page_label}")
            suggestions.append(f"Consider adding: {', '.join(uncovered)}")
    else:
        components["expected_actions_match"] = 15

    # User score (0-20)
    if user_answers:
        clarity = user_answers.get("problem_clarity", 3)
        relevance = user_answers.get("problem_relevance", 3)
        components["user_score"] = ((clarity + relevance) / 10) * 20
    else:
        components["user_score"] = 10

    raw = calculate_dimension_raw_score(components, max_points)
    normalized = normalize_score(raw)

    return DimensionScore(
        dimension=ScoreDimension.PROBLEM_ALIGNMENT,
        raw_score=raw,
        normalized_score=normalized,
        weight=DIMENSION_WEIGHTS[ScoreDimension.PROBLEM_ALIGNMENT],
        components=components,
        issues=issues,
        suggestions=suggestions,
    )


def score_page_action_coverage(
    page_caps: PageCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score ACTION_COVERAGE for a specific page."""
    components: Dict[str, float] = {}
    max_points = {
        "expected_action_coverage": 35,
        "action_count": 20,
        "flow_variety": 15,
        "user_score": 20,
        "missing_penalty": 10,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Expected action coverage (0-35)
    expected = page_caps.expected_user_actions
    actions_text = " ".join([a.get("label", "").lower() for a in page_caps.actions])
    covered = 0
    uncovered_actions = []

    for exp in expected:
        exp_words = set(exp.lower().split())
        if any(w in actions_text for w in exp_words):
            covered += 1
        else:
            uncovered_actions.append(exp)

    if expected:
        coverage = covered / len(expected)
        components["expected_action_coverage"] = coverage * 35
        if coverage < 0.6:
            issues.append(f"Only {coverage*100:.0f}% of expected {page_caps.page_label} actions covered")
            suggestions.append(f"Add actions for: {', '.join(uncovered_actions[:3])}")
    else:
        components["expected_action_coverage"] = 17

    # Action count (0-20)
    action_count = len(page_caps.actions)
    if action_count >= 5:
        components["action_count"] = 20
    elif action_count >= 3:
        components["action_count"] = 15
    elif action_count >= 1:
        components["action_count"] = 8
    else:
        components["action_count"] = 0
        issues.append(f"No actions for {page_caps.page_label} page")
        suggestions.append(f"Add actions specific to {page_caps.page_label}")

    # Dispatch variety (0-15)
    dispatches = {
        _get_action_dispatch(a)
        for a in page_caps.actions
        if isinstance(a, dict) and _get_action_dispatch(a)
    }
    if len(dispatches) >= 3:
        components["flow_variety"] = 15
    elif len(dispatches) >= 2:
        components["flow_variety"] = 10
    elif len(dispatches) >= 1:
        components["flow_variety"] = 5
    else:
        components["flow_variety"] = 0

    # User score (0-20)
    if user_answers:
        completeness = user_answers.get("action_completeness", 3)
        components["user_score"] = (completeness / 5) * 20
    else:
        components["user_score"] = 10

    # Missing penalty (0-10)
    missing_text = user_answers.get("missing_actions", "") if user_answers else ""
    if missing_text:
        missing_count = len([a for a in missing_text.split(",") if a.strip()])
        penalty = min(missing_count * 2, 10)
        components["missing_penalty"] = 10 - penalty
    else:
        components["missing_penalty"] = 10

    raw = calculate_dimension_raw_score(components, max_points)
    normalized = normalize_score(raw)

    return DimensionScore(
        dimension=ScoreDimension.ACTION_COVERAGE,
        raw_score=raw,
        normalized_score=normalized,
        weight=DIMENSION_WEIGHTS[ScoreDimension.ACTION_COVERAGE],
        components=components,
        issues=issues,
        suggestions=suggestions,
    )


def score_page_data_support(
    page_caps: PageCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score DATA_SUPPORT for a specific page."""
    components: Dict[str, float] = {}
    max_points = {
        "data_entities_defined": 25,
        "accumulation_patterns": 25,
        "storage_appropriate": 20,
        "user_score": 20,
        "growth_concern_penalty": 10,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Data entities defined (0-25)
    entity_count = len(page_caps.data_entities)
    if entity_count >= 2:
        components["data_entities_defined"] = 25
    elif entity_count >= 1:
        components["data_entities_defined"] = 15
    else:
        components["data_entities_defined"] = 5
        issues.append(f"No data entities for {page_caps.page_label}")
        suggestions.append(f"Define data storage for {page_caps.page_label}")

    # Accumulation patterns (0-25) - does data structure support growth?
    expected_patterns = page_caps.data_accumulation
    entities_text = " ".join([e.lower() for e in page_caps.data_entities])
    covered = 0
    for pattern in expected_patterns:
        pattern_words = set(pattern.lower().split())
        if any(w in entities_text for w in pattern_words):
            covered += 1

    if expected_patterns:
        coverage = covered / len(expected_patterns)
        components["accumulation_patterns"] = coverage * 25
    else:
        components["accumulation_patterns"] = 12

    # Storage appropriate (0-20)
    components["storage_appropriate"] = 15 if page_caps.data_entities else 5

    # User score (0-20)
    if user_answers:
        organization = user_answers.get("data_organization", 3)
        components["user_score"] = (organization / 5) * 20
    else:
        components["user_score"] = 10

    # Growth concern penalty (0-10)
    if user_answers:
        concern = user_answers.get("data_growth_concern", "none")
        if concern == "none":
            components["growth_concern_penalty"] = 10
        elif concern in ("backup", "organization"):
            components["growth_concern_penalty"] = 7
        else:
            components["growth_concern_penalty"] = 4
            issues.append(f"Data growth concern: {concern}")
    else:
        components["growth_concern_penalty"] = 7

    raw = calculate_dimension_raw_score(components, max_points)
    normalized = normalize_score(raw)

    return DimensionScore(
        dimension=ScoreDimension.DATA_SUPPORT,
        raw_score=raw,
        normalized_score=normalized,
        weight=DIMENSION_WEIGHTS[ScoreDimension.DATA_SUPPORT],
        components=components,
        issues=issues,
        suggestions=suggestions,
    )


def score_page_ui_access(
    page_caps: PageCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score UI_ACCESS for a specific page."""
    components: Dict[str, float] = {}
    max_points = {
        "page_accessible": 15,
        "quick_access_actions": 25,
        "navigation_clarity": 20,
        "user_score": 30,
        "quick_access_met": 10,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Page accessible (0-15) - does the page have an href?
    if page_caps.href:
        components["page_accessible"] = 15
    else:
        components["page_accessible"] = 5
        issues.append(f"No direct link to {page_caps.page_label} page")
        suggestions.append(f"Add href to {page_caps.page_id} tab in dashboard.yaml")

    # Quick access actions (0-25)
    quick_actions = [
        a
        for a in page_caps.actions
        if isinstance(a, dict) and _get_action_dispatch(a) == "fire"
    ]
    if len(quick_actions) >= 3:
        components["quick_access_actions"] = 25
    elif len(quick_actions) >= 2:
        components["quick_access_actions"] = 18
    elif len(quick_actions) >= 1:
        components["quick_access_actions"] = 10
    else:
        components["quick_access_actions"] = 3
        issues.append(f"No fire-dispatch actions for {page_caps.page_label}")
        suggestions.append(
            f"Add quick actions (dispatch: fire) for {page_caps.page_label}"
        )

    # Navigation clarity (0-20) - has icon, sensible label
    if page_caps.icon and page_caps.page_label:
        components["navigation_clarity"] = 20
    elif page_caps.page_label:
        components["navigation_clarity"] = 12
    else:
        components["navigation_clarity"] = 5

    # User score (0-30)
    if user_answers:
        nav_score = user_answers.get("ui_navigation", 3)
        components["user_score"] = (nav_score / 5) * 30
    else:
        components["user_score"] = 15

    # Quick access needs met (0-10)
    quick_needs = page_caps.quick_access_needs
    if quick_actions and quick_needs:
        components["quick_access_met"] = 10
    elif quick_actions or not quick_needs:
        components["quick_access_met"] = 6
    else:
        components["quick_access_met"] = 2
        issues.append(f"Quick access needs not met for {page_caps.page_label}")

    raw = calculate_dimension_raw_score(components, max_points)
    normalized = normalize_score(raw)

    return DimensionScore(
        dimension=ScoreDimension.UI_ACCESS,
        raw_score=raw,
        normalized_score=normalized,
        weight=DIMENSION_WEIGHTS[ScoreDimension.UI_ACCESS],
        components=components,
        issues=issues,
        suggestions=suggestions,
    )


def score_page_capability_completeness(
    page_caps: PageCapabilities,
) -> DimensionScore:
    """Score CAPABILITY_COMPLETENESS for a specific page."""
    components: Dict[str, float] = {}
    max_points = {
        "stated_vs_expected": 40,
        "action_implementation": 30,
        "data_implementation": 30,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Stated vs expected capabilities (0-40)
    stated = len(page_caps.stated_capabilities)
    expected = len(page_caps.expected_user_actions)
    if stated >= expected * 0.8:
        components["stated_vs_expected"] = 40
    elif stated >= expected * 0.5:
        components["stated_vs_expected"] = 25
    elif stated >= 1:
        components["stated_vs_expected"] = 15
    else:
        components["stated_vs_expected"] = 5
        issues.append(f"Few capabilities stated for {page_caps.page_label}")
        suggestions.append(f"Document capabilities for {page_caps.page_label} in SKILL.md")

    # Action implementation (0-30) - do stated capabilities have actions?
    action_labels = " ".join([a.get("label", "").lower() for a in page_caps.actions])
    implemented = 0
    for cap in page_caps.stated_capabilities:
        cap_words = set(cap.lower().split())
        if any(w in action_labels for w in cap_words):
            implemented += 1

    if page_caps.stated_capabilities:
        impl_ratio = implemented / len(page_caps.stated_capabilities)
        components["action_implementation"] = impl_ratio * 30
    else:
        components["action_implementation"] = 15

    # Data implementation (0-30) - is data support adequate?
    if page_caps.data_entities:
        components["data_implementation"] = min(len(page_caps.data_entities) * 10, 30)
    else:
        components["data_implementation"] = 5
        issues.append(f"No data structure for {page_caps.page_label}")

    raw = calculate_dimension_raw_score(components, max_points)
    normalized = normalize_score(raw)

    return DimensionScore(
        dimension=ScoreDimension.CAPABILITY_COMPLETENESS,
        raw_score=raw,
        normalized_score=normalized,
        weight=DIMENSION_WEIGHTS[ScoreDimension.CAPABILITY_COMPLETENESS],
        components=components,
        issues=issues,
        suggestions=suggestions,
    )


def score_page_user_journey_fit(
    page_caps: PageCapabilities,
    expectations: UserExpectationModel,
) -> DimensionScore:
    """Score USER_JOURNEY_FIT for a specific page."""
    components: Dict[str, float] = {}
    max_points = {
        "typical_actions_covered": 40,
        "data_patterns_supported": 30,
        "fast_access_met": 30,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Get action labels for matching
    action_labels = [a.get("label", "").lower() for a in page_caps.actions if isinstance(a, dict)]
    action_text = " ".join(action_labels)

    # Typical actions covered (0-40)
    expected_actions = expectations.typical_actions
    covered = 0
    for expected in expected_actions:
        expected_words = set(expected.lower().split())
        if any(w in action_text for w in expected_words):
            covered += 1

    if expected_actions:
        coverage = covered / len(expected_actions)
        components["typical_actions_covered"] = coverage * 40
        if coverage < 0.5:
            issues.append(f"Many expected {page_caps.page_label} actions not covered")
    else:
        components["typical_actions_covered"] = 20

    # Data patterns supported (0-30)
    data_patterns = expectations.data_accumulation_patterns
    entity_text = " ".join([e.lower() for e in page_caps.data_entities])

    pattern_covered = 0
    for pattern in data_patterns:
        pattern_words = set(pattern.lower().split())
        if any(w in entity_text for w in pattern_words):
            pattern_covered += 1

    if data_patterns:
        coverage = pattern_covered / len(data_patterns)
        components["data_patterns_supported"] = coverage * 30
    else:
        components["data_patterns_supported"] = 15

    # Fast access met (0-30)
    fast_actions = [
        a
        for a in page_caps.actions
        if isinstance(a, dict) and _get_action_dispatch(a) == "fire"
    ]
    fast_needs = expectations.fast_access_needs

    if fast_actions and fast_needs:
        # Check if fast actions address fast needs
        fast_action_text = " ".join([a.get("label", "").lower() for a in fast_actions])
        needs_met = sum(1 for need in fast_needs if any(w in fast_action_text for w in need.lower().split()))
        if fast_needs:
            components["fast_access_met"] = (needs_met / len(fast_needs)) * 30
        else:
            components["fast_access_met"] = 25
    elif fast_actions:
        components["fast_access_met"] = 20
    else:
        components["fast_access_met"] = 10
        issues.append(f"No fire-dispatch quick actions for {page_caps.page_label}")

    raw = calculate_dimension_raw_score(components, max_points)
    normalized = normalize_score(raw)

    return DimensionScore(
        dimension=ScoreDimension.USER_JOURNEY_FIT,
        raw_score=raw,
        normalized_score=normalized,
        weight=DIMENSION_WEIGHTS[ScoreDimension.USER_JOURNEY_FIT],
        components=components,
        issues=issues,
        suggestions=suggestions,
    )
