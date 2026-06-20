"""
Before/After Score Comparison.

Follows pattern from analyst/scripts/evaluation/compare_runs.py
for delta analysis and status classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from .dimensions import QualityScore, ScoreDimension


@dataclass
class DimensionComparison:
    """Comparison of a single dimension between before/after."""

    dimension: ScoreDimension
    before_score: float
    after_score: float
    delta: float
    status: str  # "improved", "regressed", "unchanged"
    before_issues: List[str]
    after_issues: List[str]
    issues_resolved: List[str]
    new_issues: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "dimension": self.dimension.value,
            "before": self.before_score,
            "after": self.after_score,
            "delta": self.delta,
            "status": self.status,
            "before_issues": self.before_issues,
            "after_issues": self.after_issues,
            "issues_resolved": self.issues_resolved,
            "new_issues": self.new_issues,
        }


@dataclass
class ScoreComparison:
    """Full comparison between before and after quality scores."""

    plugin_name: str
    timestamp: str
    before_overall: float
    after_overall: float
    overall_delta: float
    overall_status: str
    before_tier: str
    after_tier: str
    tier_changed: bool
    dimension_comparisons: Dict[ScoreDimension, DimensionComparison]
    summary: Dict[str, Any] = field(default_factory=dict)

    def compute_summary(self) -> None:
        """Compute comparison summary."""
        improved = [d for d, c in self.dimension_comparisons.items() if c.status == "improved"]
        regressed = [d for d, c in self.dimension_comparisons.items() if c.status == "regressed"]
        unchanged = [d for d, c in self.dimension_comparisons.items() if c.status == "unchanged"]

        total_issues_before = sum(len(c.before_issues) for c in self.dimension_comparisons.values())
        total_issues_after = sum(len(c.after_issues) for c in self.dimension_comparisons.values())
        total_resolved = sum(len(c.issues_resolved) for c in self.dimension_comparisons.values())
        total_new = sum(len(c.new_issues) for c in self.dimension_comparisons.values())

        self.summary = {
            "dimensions_improved": len(improved),
            "dimensions_regressed": len(regressed),
            "dimensions_unchanged": len(unchanged),
            "issues_before": total_issues_before,
            "issues_after": total_issues_after,
            "issues_resolved": total_resolved,
            "new_issues": total_new,
            "net_issues_change": total_issues_after - total_issues_before,
            "improved_dimensions": [d.value for d in improved],
            "regressed_dimensions": [d.value for d in regressed],
            "recommendation": self._generate_recommendation(),
        }

    def _generate_recommendation(self) -> str:
        """Generate recommendation based on comparison."""
        if self.overall_delta >= 10:
            return "Significant improvement! Consider approving this refactor."
        elif self.overall_delta >= 5:
            return "Good progress. Continue refining or approve."
        elif self.overall_delta >= 0:
            return "Minimal change. Consider additional improvements."
        elif self.overall_delta >= -5:
            return "Slight regression. Review changes before approving."
        else:
            return "Significant regression. Recommend reverting or major rework."

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "plugin_name": self.plugin_name,
            "timestamp": self.timestamp,
            "overall": {
                "before": self.before_overall,
                "after": self.after_overall,
                "delta": self.overall_delta,
                "status": self.overall_status,
            },
            "tier": {
                "before": self.before_tier,
                "after": self.after_tier,
                "changed": self.tier_changed,
            },
            "dimensions": {d.value: c.to_dict() for d, c in self.dimension_comparisons.items()},
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoreComparison":
        """Deserialize from storage."""
        dimension_comparisons = {}
        for dim_name, dim_data in data.get("dimensions", {}).items():
            dimension = ScoreDimension(dim_name)
            dimension_comparisons[dimension] = DimensionComparison(
                dimension=dimension,
                before_score=dim_data["before"],
                after_score=dim_data["after"],
                delta=dim_data["delta"],
                status=dim_data["status"],
                before_issues=dim_data.get("before_issues", []),
                after_issues=dim_data.get("after_issues", []),
                issues_resolved=dim_data.get("issues_resolved", []),
                new_issues=dim_data.get("new_issues", []),
            )

        overall = data.get("overall", {})
        tier = data.get("tier", {})

        comparison = cls(
            plugin_name=data["plugin_name"],
            timestamp=data["timestamp"],
            before_overall=overall.get("before", 0),
            after_overall=overall.get("after", 0),
            overall_delta=overall.get("delta", 0),
            overall_status=overall.get("status", "unchanged"),
            before_tier=tier.get("before", "poor"),
            after_tier=tier.get("after", "poor"),
            tier_changed=tier.get("changed", False),
            dimension_comparisons=dimension_comparisons,
            summary=data.get("summary", {}),
        )
        return comparison


def compare_scores(before: QualityScore, after: QualityScore) -> ScoreComparison:
    """Compare two quality scores.

    Args:
        before: Quality score before refactoring
        after: Quality score after refactoring

    Returns:
        ScoreComparison with detailed delta analysis
    """
    dimension_comparisons: Dict[ScoreDimension, DimensionComparison] = {}

    # Compare each dimension
    for dimension in ScoreDimension:
        before_dim = before.dimension_scores.get(dimension)
        after_dim = after.dimension_scores.get(dimension)

        before_score = before_dim.normalized_score if before_dim else 0.0
        after_score = after_dim.normalized_score if after_dim else 0.0
        delta = after_score - before_score

        # Classify status with threshold
        if delta > 2:
            status = "improved"
        elif delta < -2:
            status = "regressed"
        else:
            status = "unchanged"

        before_issues = before_dim.issues if before_dim else []
        after_issues = after_dim.issues if after_dim else []

        # Calculate resolved and new issues
        issues_resolved = [i for i in before_issues if i not in after_issues]
        new_issues = [i for i in after_issues if i not in before_issues]

        dimension_comparisons[dimension] = DimensionComparison(
            dimension=dimension,
            before_score=before_score,
            after_score=after_score,
            delta=delta,
            status=status,
            before_issues=before_issues,
            after_issues=after_issues,
            issues_resolved=issues_resolved,
            new_issues=new_issues,
        )

    # Calculate overall comparison
    overall_delta = after.overall_score - before.overall_score
    if overall_delta > 2:
        overall_status = "improved"
    elif overall_delta < -2:
        overall_status = "regressed"
    else:
        overall_status = "unchanged"

    comparison = ScoreComparison(
        plugin_name=before.plugin_name,
        timestamp=datetime.utcnow().isoformat() + "Z",
        before_overall=before.overall_score,
        after_overall=after.overall_score,
        overall_delta=overall_delta,
        overall_status=overall_status,
        before_tier=before.tier,
        after_tier=after.tier,
        tier_changed=before.tier != after.tier,
        dimension_comparisons=dimension_comparisons,
    )
    comparison.compute_summary()

    return comparison


def format_comparison_summary(comparison: ScoreComparison) -> str:
    """Format comparison as human-readable summary.

    Args:
        comparison: ScoreComparison to format

    Returns:
        Formatted summary string
    """
    lines = [
        f"## Quality Score Comparison: {comparison.plugin_name}",
        "",
        f"**Overall Score**: {comparison.before_overall:.1f} -> {comparison.after_overall:.1f} ({comparison.overall_delta:+.1f})",
        f"**Tier**: {comparison.before_tier} -> {comparison.after_tier}",
        f"**Status**: {comparison.overall_status.upper()}",
        "",
        "### Dimension Changes",
    ]

    for dim, comp in comparison.dimension_comparisons.items():
        emoji = {"improved": "+", "regressed": "-", "unchanged": "="}[comp.status]
        lines.append(
            f"- [{emoji}] **{dim.value}**: {comp.before_score:.1f} -> {comp.after_score:.1f} ({comp.delta:+.1f})"
        )

    if comparison.summary:
        lines.extend(
            [
                "",
                "### Summary",
                f"- Dimensions improved: {comparison.summary.get('dimensions_improved', 0)}",
                f"- Dimensions regressed: {comparison.summary.get('dimensions_regressed', 0)}",
                f"- Issues resolved: {comparison.summary.get('issues_resolved', 0)}",
                f"- New issues: {comparison.summary.get('new_issues', 0)}",
                "",
                f"**Recommendation**: {comparison.summary.get('recommendation', '')}",
            ]
        )

    return "\n".join(lines)
