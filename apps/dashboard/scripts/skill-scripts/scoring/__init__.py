"""
Scoring Module.

Plugin quality scoring system that evaluates plugins across multiple dimensions
before and after refactoring.
"""

from .dimensions import (
    ScoreDimension,
    DimensionScore,
    QualityScore,
    DIMENSION_WEIGHTS,
)
from .analyzer import PluginCapabilities, extract_problem_statement
from .normalizer import normalize_score, calculate_overall_score, classify_tier
from .comparator import DimensionComparison, ScoreComparison, compare_scores
from .quality_scorer import QualityScorer

__all__ = [
    # Dimensions
    "ScoreDimension",
    "DimensionScore",
    "QualityScore",
    "DIMENSION_WEIGHTS",
    # Analyzer
    "PluginCapabilities",
    "extract_problem_statement",
    # Normalizer
    "normalize_score",
    "calculate_overall_score",
    "classify_tier",
    # Comparator
    "DimensionComparison",
    "ScoreComparison",
    "compare_scores",
    # Main scorer
    "QualityScorer",
]
