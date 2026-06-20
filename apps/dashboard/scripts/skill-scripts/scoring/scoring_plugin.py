"""
Plugin-level scoring methods for QualityScorer.

Scores the entire plugin across all quality dimensions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .analyzer import (
    PluginCapabilities,
    analyze_action_coverage,
    analyze_data_structure,
    analyze_ui_structure,
)
from .dimensions import DIMENSION_WEIGHTS, DimensionScore, ScoreDimension
from .normalizer import calculate_dimension_raw_score, normalize_score


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


def score_problem_alignment(
    capabilities: PluginCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score PROBLEM_ALIGNMENT dimension."""
    components: Dict[str, float] = {}
    max_points = {
        "description_clarity": 20,
        "capabilities_present": 15,
        "hub_subtitle": 15,
        "actions_cover_capabilities": 30,
        "user_score": 20,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Description clarity (0-20)
    if capabilities.description:
        desc_length = len(capabilities.description)
        if desc_length > 50:
            components["description_clarity"] = 20
        elif desc_length > 20:
            components["description_clarity"] = 15
        else:
            components["description_clarity"] = 10
            issues.append("Description is too brief")
            suggestions.append("Add more detail to the description")
    else:
        components["description_clarity"] = 0
        issues.append("Missing description in SKILL.md")
        suggestions.append("Add a description field to SKILL.md frontmatter")

    # Capabilities section (0-15)
    cap_count = len(capabilities.stated_capabilities)
    if cap_count >= 5:
        components["capabilities_present"] = 15
    elif cap_count >= 3:
        components["capabilities_present"] = 10
    elif cap_count >= 1:
        components["capabilities_present"] = 5
    else:
        components["capabilities_present"] = 0
        issues.append("No capabilities section in SKILL.md")
        suggestions.append("Add ## Capabilities section listing what the plugin does")

    # Hub subtitle (0-15)
    if capabilities.hub_subtitle:
        components["hub_subtitle"] = 15
    else:
        components["hub_subtitle"] = 0
        issues.append("Missing hub.subtitle in dashboard.yaml")
        suggestions.append("Add subtitle to hub section in dashboard.yaml")

    # Actions cover capabilities (0-30)
    action_analysis = analyze_action_coverage(capabilities)
    coverage = action_analysis["coverage_ratio"]
    components["actions_cover_capabilities"] = coverage * 30

    if coverage < 0.5:
        issues.append(f"Only {coverage*100:.0f}% of capabilities have matching actions")
        uncovered = action_analysis.get("uncovered_capabilities", [])[:3]
        if uncovered:
            suggestions.append(f"Add actions for: {', '.join(uncovered)}")

    # User questionnaire score (0-20)
    if user_answers:
        clarity = user_answers.get("problem_clarity", 3)
        relevance = user_answers.get("problem_relevance", 3)
        user_score = ((clarity + relevance) / 10) * 20
        components["user_score"] = user_score
    else:
        components["user_score"] = 10  # Neutral default

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


def score_action_coverage(
    capabilities: PluginCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score ACTION_COVERAGE dimension."""
    components: Dict[str, float] = {}
    max_points = {
        "action_count": 25,
        "flow_variety": 15,
        "capability_coverage": 30,
        "user_score": 20,
        "missing_penalty": 10,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Action count (0-25)
    action_count = len(capabilities.actions)
    if action_count >= 5:
        components["action_count"] = 25
    elif action_count >= 3:
        components["action_count"] = 18
    elif action_count >= 1:
        components["action_count"] = 10
    else:
        components["action_count"] = 0
        issues.append("No actions defined in dashboard.yaml")
        suggestions.append("Add actions array to dashboard.yaml")

    # Dispatch variety (0-15)
    dispatches = set()
    for action in capabilities.actions:
        if isinstance(action, dict):
            dispatch = _get_action_dispatch(action)
            if dispatch:
                dispatches.add(dispatch)

    if len(dispatches) >= 3:
        components["flow_variety"] = 15
    elif len(dispatches) >= 2:
        components["flow_variety"] = 10
    elif len(dispatches) >= 1:
        components["flow_variety"] = 5
    else:
        components["flow_variety"] = 0

    # Capability coverage (0-30)
    analysis = analyze_action_coverage(capabilities)
    components["capability_coverage"] = analysis["coverage_ratio"] * 30

    # User score (0-20)
    if user_answers:
        completeness = user_answers.get("action_completeness", 3)
        components["user_score"] = (completeness / 5) * 20
    else:
        components["user_score"] = 10

    # Missing actions penalty (starts at max, subtract for missing)
    missing_actions = user_answers.get("missing_actions", "") if user_answers else ""
    if missing_actions:
        missing_count = len([a for a in missing_actions.split(",") if a.strip()])
        penalty = min(missing_count * 2, 10)
        components["missing_penalty"] = 10 - penalty
        if missing_count > 0:
            issues.append(f"User identified {missing_count} missing actions")
            suggestions.append(f"Consider adding: {missing_actions}")
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


def score_data_support(
    skill_path: Path,
    capabilities: PluginCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score DATA_SUPPORT dimension."""
    components: Dict[str, float] = {}
    max_points = {
        "data_dir_exists": 10,
        "schemas_present": 15,
        "entity_coverage": 25,
        "storage_appropriate": 20,
        "user_score": 20,
        "growth_concern_penalty": 10,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    analysis = analyze_data_structure(skill_path, capabilities)

    # Data dir exists (0-10)
    if analysis["has_data_dir"]:
        components["data_dir_exists"] = 10
    else:
        components["data_dir_exists"] = 0
        issues.append("No data_dir configured in dashboard.yaml")
        suggestions.append("Add data_dir field to dashboard.yaml")

    # Schemas present (0-15)
    if analysis["has_schemas"]:
        schema_count = analysis["schema_count"]
        if schema_count >= 3:
            components["schemas_present"] = 15
        elif schema_count >= 1:
            components["schemas_present"] = 10
        else:
            components["schemas_present"] = 5
    else:
        components["schemas_present"] = 0
        issues.append("No schemas directory or schema files")
        suggestions.append("Create schemas/ directory with YAML schema files")

    # Entity coverage (0-25)
    components["entity_coverage"] = analysis["entity_coverage"] * 25

    # Storage appropriate (0-20) - basic check
    components["storage_appropriate"] = 15 if analysis["has_data_dir"] else 5

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
            issues.append(f"User concerned about: {concern}")
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


def score_ui_access(
    capabilities: PluginCapabilities,
    user_answers: Optional[Dict[str, Any]] = None,
) -> DimensionScore:
    """Score UI_ACCESS dimension."""
    components: Dict[str, float] = {}
    max_points = {
        "overview_tab": 10,
        "tab_count": 15,
        "quick_access": 20,
        "navigation": 25,
        "user_score": 30,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    analysis = analyze_ui_structure(capabilities)

    # Overview tab (0-10)
    if analysis["has_overview"] and analysis["overview_is_default"]:
        components["overview_tab"] = 10
    elif analysis["has_overview"]:
        components["overview_tab"] = 7
        issues.append("Overview tab exists but is not default")
        suggestions.append("Set default: true on overview tab")
    else:
        components["overview_tab"] = 0
        issues.append("No overview tab")
        suggestions.append("Add overview tab with default: true")

    # Tab count (0-15) - optimal is 4-8 tabs
    tab_count = analysis["tab_count"]
    if 4 <= tab_count <= 8:
        components["tab_count"] = 15
    elif 2 <= tab_count <= 10:
        components["tab_count"] = 10
    elif tab_count >= 1:
        components["tab_count"] = 5
    else:
        components["tab_count"] = 0
        issues.append("No tabs defined")
        suggestions.append("Add tabs array to dashboard.yaml")

    # Quick access actions (0-20)
    quick_actions = [
        a
        for a in capabilities.actions
        if isinstance(a, dict) and _get_action_dispatch(a) == "fire"
    ]
    if len(quick_actions) >= 2:
        components["quick_access"] = 20
    elif len(quick_actions) >= 1:
        components["quick_access"] = 12
    else:
        components["quick_access"] = 5
        suggestions.append("Add fire-dispatch actions for quick access")

    # Navigation structure (0-25)
    variety = analysis["tab_variety"]
    components["navigation"] = variety * 25

    # User score (0-30)
    if user_answers:
        nav_score = user_answers.get("ui_navigation", 3)
        access_priority = user_answers.get("quick_access_priority")
        # Base score from navigation rating
        user_score = (nav_score / 5) * 20
        # Bonus if access priority is addressed
        if access_priority and quick_actions:
            user_score += 10
        else:
            user_score += 5
        components["user_score"] = min(user_score, 30)
    else:
        components["user_score"] = 15

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


def score_capability_completeness(
    skill_path: Path,
    capabilities: PluginCapabilities,
) -> DimensionScore:
    """Score CAPABILITY_COMPLETENESS dimension."""
    components: Dict[str, float] = {}
    max_points = {
        "implementation_coverage": 40,
        "tests_exist": 20,
        "mcp_tools": 20,
        "scripts_exist": 20,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Implementation coverage (0-40)
    analysis = analyze_action_coverage(capabilities)
    components["implementation_coverage"] = analysis["coverage_ratio"] * 40

    # Tests exist (0-20)
    tests_dir = skill_path / "tests"
    if tests_dir.exists() and any(tests_dir.glob("*.py")):
        components["tests_exist"] = 20
    elif tests_dir.exists():
        components["tests_exist"] = 10
    else:
        components["tests_exist"] = 0
        issues.append("No tests directory")
        suggestions.append("Add tests/ directory with test files")

    # MCP tools (0-20)
    mcp_dir = skill_path / "mcp"
    if mcp_dir.exists() and (mcp_dir / "__init__.py").exists():
        components["mcp_tools"] = 20
    elif capabilities.mcp_tools:
        components["mcp_tools"] = 15
    else:
        components["mcp_tools"] = 5

    # Scripts exist (0-20)
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists() and any(scripts_dir.glob("*.py")):
        components["scripts_exist"] = 20
    elif scripts_dir.exists():
        components["scripts_exist"] = 10
    else:
        components["scripts_exist"] = 5

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


def score_user_journey_fit(
    capabilities: PluginCapabilities,
    expectations: "UserExpectationModel",
) -> DimensionScore:
    """Score USER_JOURNEY_FIT dimension."""
    from .user_research import UserExpectationModel  # noqa: F811

    components: Dict[str, float] = {}
    max_points = {
        "typical_actions_covered": 40,
        "data_patterns_supported": 30,
        "fast_access_met": 30,
    }
    issues: List[str] = []
    suggestions: List[str] = []

    # Get action labels for matching
    action_labels = [a.get("label", "").lower() for a in capabilities.actions if isinstance(a, dict)]
    action_text = " ".join(action_labels)

    # Typical actions covered (0-40)
    expected_actions = expectations.typical_actions
    covered = 0
    for expected in expected_actions:
        # Simple word overlap check
        expected_words = set(expected.lower().split())
        if any(w in action_text for w in expected_words):
            covered += 1

    if expected_actions:
        coverage = covered / len(expected_actions)
        components["typical_actions_covered"] = coverage * 40
    else:
        components["typical_actions_covered"] = 20

    # Data patterns supported (0-30)
    data_patterns = expectations.data_accumulation_patterns
    entities = [e.lower() for e in capabilities.data_entities]
    entity_text = " ".join(entities)

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
        for a in capabilities.actions
        if isinstance(a, dict) and _get_action_dispatch(a) == "fire"
    ]
    fast_needs = expectations.fast_access_needs

    if fast_actions and fast_needs:
        components["fast_access_met"] = 25
    elif fast_actions or fast_needs:
        components["fast_access_met"] = 15
    else:
        components["fast_access_met"] = 10

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
