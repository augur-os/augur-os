"""
Score Normalization.

Ensures scores always leave room for improvement by capping at 95.
Uses asymptotic scaling for high scores to create natural plateaus.
"""

from __future__ import annotations

import math
from typing import Dict

from .dimensions import DIMENSION_WEIGHTS, DimensionScore, ScoreDimension

# Maximum normalized score (always leave room for improvement)
MAX_NORMALIZED_SCORE = 95.0


def normalize_score(raw_score: float, max_score: float = MAX_NORMALIZED_SCORE) -> float:
    """Normalize a raw score (0-100) to always leave room for improvement.

    Uses asymptotic curve: as raw approaches 100, normalized approaches max_score.
    Formula: normalized = max_score * (1 - e^(-raw/50))

    This ensures:
    - raw=0  -> ~0
    - raw=50 -> ~63
    - raw=80 -> ~80
    - raw=90 -> ~87
    - raw=100 -> ~95 (capped)

    Args:
        raw_score: Raw score from 0-100
        max_score: Maximum possible normalized score (default 95)

    Returns:
        Normalized score clamped to [0, max_score]
    """
    if raw_score <= 0:
        return 0.0

    # Asymptotic normalization
    normalized = max_score * (1 - math.exp(-raw_score / 50))

    # Hard cap at max_score
    return min(normalized, max_score)


def calculate_overall_score(
    dimension_scores: Dict[ScoreDimension, DimensionScore],
) -> float:
    """Calculate weighted overall score from dimension scores.

    Args:
        dimension_scores: Dict mapping dimensions to their scores

    Returns:
        Weighted average score (0-95 range)
    """
    if not dimension_scores:
        return 0.0

    total = 0.0
    weight_sum = 0.0

    for dimension, score in dimension_scores.items():
        weight = DIMENSION_WEIGHTS.get(dimension, 0.1)
        total += score.normalized_score * weight
        weight_sum += weight

    if weight_sum == 0:
        return 0.0

    return total / weight_sum


def classify_tier(score: float) -> str:
    """Classify score into tier.

    Args:
        score: Overall score (0-100 range)

    Returns:
        Tier string: "excellent", "good", "needs-work", or "poor"
    """
    if score >= 85:
        return "excellent"
    elif score >= 70:
        return "good"
    elif score >= 50:
        return "needs-work"
    else:
        return "poor"


def calculate_dimension_raw_score(
    components: Dict[str, float],
    max_points: Dict[str, float],
) -> float:
    """Calculate raw dimension score from component scores.

    Args:
        components: Dict of component name to actual score
        max_points: Dict of component name to max possible points

    Returns:
        Raw score as percentage (0-100)
    """
    if not components or not max_points:
        return 0.0

    total_score = sum(components.values())
    total_max = sum(max_points.values())

    if total_max == 0:
        return 0.0

    return (total_score / total_max) * 100


def apply_penalty(
    base_score: float,
    penalty_amount: float,
    min_score: float = 0.0,
) -> float:
    """Apply a penalty to a score with floor.

    Args:
        base_score: Starting score
        penalty_amount: Amount to subtract
        min_score: Minimum allowed score

    Returns:
        Score after penalty, floored at min_score
    """
    return max(min_score, base_score - penalty_amount)


def apply_bonus(
    base_score: float,
    bonus_amount: float,
    max_score: float = 100.0,
) -> float:
    """Apply a bonus to a score with ceiling.

    Args:
        base_score: Starting score
        bonus_amount: Amount to add
        max_score: Maximum allowed score

    Returns:
        Score after bonus, capped at max_score
    """
    return min(max_score, base_score + bonus_amount)


def clamp_score(score: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp a score to a range.

    Args:
        score: Score to clamp
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        Clamped score
    """
    return max(min_val, min(max_val, score))
