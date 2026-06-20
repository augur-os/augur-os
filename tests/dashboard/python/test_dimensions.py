"""Tests for apps/dashboard/scripts/skill-scripts/scoring/dimensions.py — quality scoring types."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module via importlib (directory has hyphens). File lives at
# apps/dashboard/scripts/skill-scripts/scoring/dimensions.py — this test sits
# at tests/dashboard/python/test_dimensions.py so parents[3] is the project root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULE_PATH = _REPO_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts" / "scoring" / "dimensions.py"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location("dimensions", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
# Register in sys.modules before exec so @dataclass can resolve the module
sys.modules["dimensions"] = _mod
_spec.loader.exec_module(_mod)

ScoreDimension = _mod.ScoreDimension
DIMENSION_WEIGHTS = _mod.DIMENSION_WEIGHTS
DimensionScore = _mod.DimensionScore
QualityScore = _mod.QualityScore


# ---------------------------------------------------------------------------
# ScoreDimension enum
# ---------------------------------------------------------------------------


class TestScoreDimension:
    def test_all_dimensions_exist(self):
        expected = {
            "problem_alignment",
            "action_coverage",
            "data_support",
            "ui_access",
            "capability_completeness",
            "user_journey_fit",
        }
        actual = {d.value for d in ScoreDimension}
        assert actual == expected

    def test_string_enum(self):
        assert ScoreDimension.PROBLEM_ALIGNMENT == "problem_alignment"
        assert isinstance(ScoreDimension.PROBLEM_ALIGNMENT, str)


# ---------------------------------------------------------------------------
# DIMENSION_WEIGHTS
# ---------------------------------------------------------------------------


class TestDimensionWeights:
    def test_weights_sum_to_one(self):
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_dimensions_have_weights(self):
        for dim in ScoreDimension:
            assert dim in DIMENSION_WEIGHTS

    def test_weights_positive(self):
        for dim, weight in DIMENSION_WEIGHTS.items():
            assert weight > 0


# ---------------------------------------------------------------------------
# DimensionScore
# ---------------------------------------------------------------------------


class TestDimensionScore:
    def _make_score(self, **overrides):
        defaults = {
            "dimension": ScoreDimension.PROBLEM_ALIGNMENT,
            "raw_score": 80.0,
            "normalized_score": 75.0,
            "weight": 0.25,
        }
        defaults.update(overrides)
        return DimensionScore(**defaults)

    def test_to_dict(self):
        score = self._make_score(components={"x": 10}, issues=["i1"], suggestions=["s1"])
        d = score.to_dict()
        assert d["dimension"] == "problem_alignment"
        assert d["raw"] == 80.0
        assert d["normalized"] == 75.0
        assert d["weight"] == 0.25
        assert d["components"] == {"x": 10}
        assert d["issues"] == ["i1"]

    def test_from_dict_roundtrip(self):
        original = self._make_score(components={"a": 5}, issues=["bug"])
        d = original.to_dict()
        restored = DimensionScore.from_dict(d)
        assert restored.dimension == original.dimension
        assert restored.raw_score == original.raw_score
        assert restored.normalized_score == original.normalized_score

    def test_default_fields(self):
        score = self._make_score()
        assert score.components == {}
        assert score.issues == []
        assert score.suggestions == []


# ---------------------------------------------------------------------------
# QualityScore
# ---------------------------------------------------------------------------


class TestQualityScore:
    def _make_quality_score(self):
        dim_score = DimensionScore(
            dimension=ScoreDimension.PROBLEM_ALIGNMENT,
            raw_score=80.0,
            normalized_score=75.0,
            weight=0.25,
        )
        return QualityScore(
            plugin_name="test-plugin",
            timestamp="2025-01-01T00:00:00Z",
            dimension_scores={ScoreDimension.PROBLEM_ALIGNMENT: dim_score},
            overall_score=75.0,
            tier="good",
            problem_statement="Test problem",
            user_expectations=["fast", "reliable"],
            gaps_identified=["gap1"],
            improvement_priority=["fix gap1"],
        )

    def test_to_dict(self):
        qs = self._make_quality_score()
        d = qs.to_dict()
        assert d["plugin_name"] == "test-plugin"
        assert d["overall_score"] == 75.0
        assert d["tier"] == "good"
        assert "problem_alignment" in d["dimensions"]

    def test_from_dict_roundtrip(self):
        original = self._make_quality_score()
        d = original.to_dict()
        restored = QualityScore.from_dict(d)
        assert restored.plugin_name == "test-plugin"
        assert restored.overall_score == 75.0
        assert restored.tier == "good"
        assert ScoreDimension.PROBLEM_ALIGNMENT in restored.dimension_scores

    def test_create_empty(self):
        empty = QualityScore.create_empty("my-plugin")
        assert empty.plugin_name == "my-plugin"
        assert empty.overall_score == 0.0
        assert empty.tier == "poor"
        assert empty.dimension_scores == {}
