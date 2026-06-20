"""
Quality Scoring Dimensions.

Defines the multi-dimensional scoring system for plugin quality assessment.
Inspired by calculate_agent_scores.py weighted component pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class ScoreDimension(str, Enum):
    """Scoring dimensions for plugin quality."""

    PROBLEM_ALIGNMENT = "problem_alignment"  # Does the plugin solve stated problems?
    ACTION_COVERAGE = "action_coverage"  # Do actions address user needs?
    DATA_SUPPORT = "data_support"  # Do data structures support workflows?
    UI_ACCESS = "ui_access"  # Does UI provide appropriate access?
    CAPABILITY_COMPLETENESS = "capability_completeness"  # Are all capabilities implemented?
    USER_JOURNEY_FIT = "user_journey_fit"  # Does it fit typical user journeys?


# Dimension weights (must sum to 1.0)
DIMENSION_WEIGHTS: Dict[ScoreDimension, float] = {
    ScoreDimension.PROBLEM_ALIGNMENT: 0.25,
    ScoreDimension.ACTION_COVERAGE: 0.20,
    ScoreDimension.DATA_SUPPORT: 0.20,
    ScoreDimension.UI_ACCESS: 0.15,
    ScoreDimension.CAPABILITY_COMPLETENESS: 0.10,
    ScoreDimension.USER_JOURNEY_FIT: 0.10,
}


@dataclass
class DimensionScore:
    """Score for a single dimension."""

    dimension: ScoreDimension
    raw_score: float  # 0-100 before normalization
    normalized_score: float  # 0-95 (always room for improvement)
    weight: float  # Weight in final score
    components: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "dimension": self.dimension.value,
            "raw": self.raw_score,
            "normalized": self.normalized_score,
            "weight": self.weight,
            "components": self.components,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DimensionScore":
        """Deserialize from storage."""
        return cls(
            dimension=ScoreDimension(data["dimension"]),
            raw_score=data["raw"],
            normalized_score=data["normalized"],
            weight=data["weight"],
            components=data.get("components", {}),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
        )


@dataclass
class QualityScore:
    """Complete quality score for a plugin."""

    plugin_name: str
    timestamp: str
    dimension_scores: Dict[ScoreDimension, DimensionScore]
    overall_score: float  # Weighted average, normalized 0-95
    tier: str  # "excellent" (85+), "good" (70-84), "needs-work" (50-69), "poor" (<50)
    problem_statement: str  # Extracted from dashboard.yaml/SKILL.md
    user_expectations: List[str]
    gaps_identified: List[str]
    improvement_priority: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for YAML storage."""
        return {
            "plugin_name": self.plugin_name,
            "timestamp": self.timestamp,
            "overall_score": self.overall_score,
            "tier": self.tier,
            "dimensions": {d.value: ds.to_dict() for d, ds in self.dimension_scores.items()},
            "problem_statement": self.problem_statement,
            "user_expectations": self.user_expectations,
            "gaps_identified": self.gaps_identified,
            "improvement_priority": self.improvement_priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityScore":
        """Deserialize from storage."""
        dimension_scores = {}
        for dim_name, dim_data in data.get("dimensions", {}).items():
            dimension = ScoreDimension(dim_name)
            dimension_scores[dimension] = DimensionScore.from_dict(dim_data)

        return cls(
            plugin_name=data["plugin_name"],
            timestamp=data["timestamp"],
            dimension_scores=dimension_scores,
            overall_score=data["overall_score"],
            tier=data["tier"],
            problem_statement=data.get("problem_statement", ""),
            user_expectations=data.get("user_expectations", []),
            gaps_identified=data.get("gaps_identified", []),
            improvement_priority=data.get("improvement_priority", []),
        )

    @classmethod
    def create_empty(cls, plugin_name: str) -> "QualityScore":
        """Create an empty quality score for initialization."""
        return cls(
            plugin_name=plugin_name,
            timestamp=datetime.utcnow().isoformat() + "Z",
            dimension_scores={},
            overall_score=0.0,
            tier="poor",
            problem_statement="",
            user_expectations=[],
            gaps_identified=[],
            improvement_priority=[],
        )
