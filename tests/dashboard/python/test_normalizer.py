"""Tests for apps/dashboard/scripts/skill-scripts/scoring/normalizer.py — score normalization."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load modules via importlib (directory has hyphens). File lives at
# apps/dashboard/scripts/skill-scripts/scoring/normalizer.py — this test sits at
# tests/dashboard/python/test_normalizer.py so parents[3] is the project root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCORING_DIR = _REPO_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts" / "scoring"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load the dashboard scoring package under a NAMESPACED name to avoid colliding
# with project-brain/capabilities/skills/ai/scripts/ops/agent_digest/scoring.py (which other
# tests import as the bare name "scoring"). sys.modules is global across a
# pytest collection run, so the first test to register "scoring" shadows it for
# everyone else and breaks unrelated tests with cryptic ImportError. Namespace
# this one as "dashboard_scoring" instead.
_PKG_NAME = "dashboard_scoring"

# Load dimensions first (normalizer depends on it via .dimensions relative import).
_dim_spec = importlib.util.spec_from_file_location(f"{_PKG_NAME}.dimensions", _SCORING_DIR / "dimensions.py")
_dim_mod = importlib.util.module_from_spec(_dim_spec)
sys.modules[f"{_PKG_NAME}.dimensions"] = _dim_mod

# Load the package __init__ so the relative imports inside normalizer resolve.
_init_path = _SCORING_DIR / "__init__.py"
_pkg_spec = importlib.util.spec_from_file_location(
    _PKG_NAME,
    _init_path,
    submodule_search_locations=[str(_SCORING_DIR)],
)
_pkg_mod = importlib.util.module_from_spec(_pkg_spec)
sys.modules[_PKG_NAME] = _pkg_mod
_dim_mod.__package__ = _PKG_NAME
_dim_spec.loader.exec_module(_dim_mod)
if _init_path.exists():
    _pkg_spec.loader.exec_module(_pkg_mod)

_norm_spec = importlib.util.spec_from_file_location(f"{_PKG_NAME}.normalizer", _SCORING_DIR / "normalizer.py")
_norm_mod = importlib.util.module_from_spec(_norm_spec)
_norm_mod.__package__ = _PKG_NAME
_norm_spec.loader.exec_module(_norm_mod)

normalize_score = _norm_mod.normalize_score
calculate_overall_score = _norm_mod.calculate_overall_score
classify_tier = _norm_mod.classify_tier
calculate_dimension_raw_score = _norm_mod.calculate_dimension_raw_score
apply_penalty = _norm_mod.apply_penalty
apply_bonus = _norm_mod.apply_bonus
clamp_score = _norm_mod.clamp_score
MAX_NORMALIZED_SCORE = _norm_mod.MAX_NORMALIZED_SCORE

ScoreDimension = _dim_mod.ScoreDimension
DimensionScore = _dim_mod.DimensionScore
DIMENSION_WEIGHTS = _dim_mod.DIMENSION_WEIGHTS


# ---------------------------------------------------------------------------
# normalize_score
# ---------------------------------------------------------------------------


class TestNormalizeScore:
    def test_zero_returns_zero(self):
        assert normalize_score(0) == 0.0

    def test_negative_returns_zero(self):
        assert normalize_score(-10) == 0.0

    def test_high_score_capped_at_max(self):
        result = normalize_score(100)
        assert result <= MAX_NORMALIZED_SCORE
        assert result > 80  # Asymptotic curve: 100 -> ~82

    def test_mid_range_reasonable(self):
        result = normalize_score(50)
        assert 55 < result < 70

    def test_monotonically_increasing(self):
        scores = [normalize_score(x) for x in range(0, 101, 10)]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]

    def test_custom_max_score(self):
        result = normalize_score(100, max_score=80.0)
        assert result <= 80.0


# ---------------------------------------------------------------------------
# calculate_overall_score
# ---------------------------------------------------------------------------


class TestCalculateOverallScore:
    def test_empty_returns_zero(self):
        assert calculate_overall_score({}) == 0.0

    def test_single_dimension(self):
        scores = {
            ScoreDimension.PROBLEM_ALIGNMENT: DimensionScore(
                dimension=ScoreDimension.PROBLEM_ALIGNMENT,
                raw_score=80,
                normalized_score=80.0,
                weight=0.25,
            )
        }
        result = calculate_overall_score(scores)
        assert result == 80.0

    def test_multiple_dimensions_weighted(self):
        scores = {
            ScoreDimension.PROBLEM_ALIGNMENT: DimensionScore(
                dimension=ScoreDimension.PROBLEM_ALIGNMENT,
                raw_score=90,
                normalized_score=90.0,
                weight=0.25,
            ),
            ScoreDimension.ACTION_COVERAGE: DimensionScore(
                dimension=ScoreDimension.ACTION_COVERAGE,
                raw_score=60,
                normalized_score=60.0,
                weight=0.20,
            ),
        }
        result = calculate_overall_score(scores)
        assert 76 < result < 77


# ---------------------------------------------------------------------------
# classify_tier
# ---------------------------------------------------------------------------


class TestClassifyTier:
    def test_excellent(self):
        assert classify_tier(90) == "excellent"
        assert classify_tier(85) == "excellent"

    def test_good(self):
        assert classify_tier(75) == "good"
        assert classify_tier(70) == "good"

    def test_needs_work(self):
        assert classify_tier(60) == "needs-work"
        assert classify_tier(50) == "needs-work"

    def test_poor(self):
        assert classify_tier(30) == "poor"
        assert classify_tier(0) == "poor"


# ---------------------------------------------------------------------------
# calculate_dimension_raw_score
# ---------------------------------------------------------------------------


class TestCalculateDimensionRawScore:
    def test_empty_inputs(self):
        assert calculate_dimension_raw_score({}, {}) == 0.0

    def test_full_score(self):
        assert calculate_dimension_raw_score({"a": 10, "b": 20}, {"a": 10, "b": 20}) == 100.0

    def test_half_score(self):
        assert calculate_dimension_raw_score({"a": 5}, {"a": 10}) == 50.0

    def test_zero_max_returns_zero(self):
        assert calculate_dimension_raw_score({"a": 5}, {"a": 0}) == 0.0


# ---------------------------------------------------------------------------
# apply_penalty / apply_bonus / clamp_score
# ---------------------------------------------------------------------------


class TestPenaltyBonusClamp:
    def test_penalty_basic(self):
        assert apply_penalty(80, 10) == 70

    def test_penalty_floor(self):
        assert apply_penalty(5, 20, min_score=0) == 0

    def test_bonus_basic(self):
        assert apply_bonus(80, 10) == 90

    def test_bonus_ceiling(self):
        assert apply_bonus(95, 20, max_score=100) == 100

    def test_clamp_within_range(self):
        assert clamp_score(50) == 50

    def test_clamp_below_min(self):
        assert clamp_score(-5) == 0

    def test_clamp_above_max(self):
        assert clamp_score(150) == 100
