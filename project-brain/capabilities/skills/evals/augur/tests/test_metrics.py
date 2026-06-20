"""Tests for metrics.py — the spec §4.4 regression contract (ADR-742).

Every later slate ADR that touches retrieval is tested against these. The
worked examples below are the contract; they must not drift.

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load(module_name: str, file_name: str) -> Any:
    full_name = f"evals_{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, SCRIPTS_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def metrics() -> Any:
    return _load("metrics", "metrics.py")


# --------------------------------------------------------------------------
# P@k — denominator is k, NOT min(k, |retrieved|)  (spec §4.4.1)
# --------------------------------------------------------------------------


def test_precision_denominator_is_k_when_fewer_retrieved(metrics: Any) -> None:
    """3 retrieved, 2 of them relevant, k=5 -> 2/5 = 0.4 (NOT 2/3)."""
    retrieved = ["a", "b", "c"]
    relevant = {"a", "c"}
    assert metrics.precision_at_k(retrieved, relevant, 5) == pytest.approx(2 / 5)


def test_precision_full_window(metrics: Any) -> None:
    """5 retrieved, 3 relevant in top 5, k=5 -> 3/5."""
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c", "e"}
    assert metrics.precision_at_k(retrieved, relevant, 5) == pytest.approx(3 / 5)


def test_precision_perfect_at_k(metrics: Any) -> None:
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    assert metrics.precision_at_k(retrieved, relevant, 3) == pytest.approx(1.0)


def test_precision_zero_when_no_hits(metrics: Any) -> None:
    assert metrics.precision_at_k(["x", "y"], {"a"}, 5) == 0.0


def test_precision_only_counts_top_k(metrics: Any) -> None:
    """A relevant doc at rank 6 does not count toward P@5."""
    retrieved = ["x", "x", "x", "x", "x", "hit"]
    assert metrics.precision_at_k(retrieved, {"hit"}, 5) == 0.0


# --------------------------------------------------------------------------
# R@k — None on empty relevant  (spec §4.4.2)
# --------------------------------------------------------------------------


def test_recall_none_on_empty_relevant(metrics: Any) -> None:
    assert metrics.recall_at_k(["a", "b"], [], 5) is None
    assert metrics.recall_at_k(["a", "b"], set(), 10) is None


def test_recall_basic(metrics: Any) -> None:
    """2 of 4 relevant docs appear in top 5 -> 2/4 = 0.5."""
    retrieved = ["a", "x", "b", "y", "z"]
    relevant = {"a", "b", "c", "d"}
    assert metrics.recall_at_k(retrieved, relevant, 5) == pytest.approx(0.5)


def test_recall_full(metrics: Any) -> None:
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    assert metrics.recall_at_k(retrieved, relevant, 10) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# MRR — full retrieved list, 1-indexed  (spec §4.4.3)
# --------------------------------------------------------------------------


def test_mrr_first_relevant_at_rank_1(metrics: Any) -> None:
    assert metrics.mrr(["hit", "x", "y"], {"hit"}) == pytest.approx(1.0)


def test_mrr_full_list_rank_50(metrics: Any) -> None:
    """A relevant doc at rank 50 yields 1/50 — MRR is over the FULL list."""
    retrieved = ["x"] * 49 + ["hit"]
    assert metrics.mrr(retrieved, {"hit"}) == pytest.approx(1 / 50)


def test_mrr_zero_when_no_relevant_in_list(metrics: Any) -> None:
    assert metrics.mrr(["x", "y", "z"], {"hit"}) == 0.0


def test_mrr_zero_when_relevant_set_empty(metrics: Any) -> None:
    assert metrics.mrr(["a", "b"], set()) == 0.0


def test_mrr_uses_first_relevant(metrics: Any) -> None:
    """rank_of_first_relevant — second relevant doc does not change the value."""
    retrieved = ["x", "hit1", "hit2"]
    assert metrics.mrr(retrieved, {"hit1", "hit2"}) == pytest.approx(1 / 2)


# --------------------------------------------------------------------------
# nDCG@10 — binary gain, IDCG over min(10, |R|)  (spec §4.4.4)
# --------------------------------------------------------------------------


def test_ndcg_single_relevant_at_rank_1_is_one(metrics: Any) -> None:
    """One relevant doc, retrieved at rank 1 -> DCG = IDCG = 1.0 -> nDCG = 1.0."""
    assert metrics.ndcg_at_10(["hit"], {"hit"}) == pytest.approx(1.0)


def test_ndcg_single_relevant_at_rank_2(metrics: Any) -> None:
    """|R|=1, hit at rank 2 -> DCG = 1/log2(3), IDCG = 1/log2(2) = 1."""
    expected = (1 / math.log2(3)) / 1.0
    assert metrics.ndcg_at_10(["x", "hit"], {"hit"}) == pytest.approx(expected)


def test_ndcg_binary_gain_not_graded(metrics: Any) -> None:
    """Gain is binary {0,1}: two relevant docs at ranks 1,2 with |R|=2.

    DCG = 1/log2(2) + 1/log2(3); IDCG = 1/log2(2) + 1/log2(3); nDCG = 1.0.
    """
    retrieved = ["hitA", "hitB", "x", "y"]
    assert metrics.ndcg_at_10(retrieved, {"hitA", "hitB"}) == pytest.approx(1.0)


def test_ndcg_none_on_empty_relevant(metrics: Any) -> None:
    assert metrics.ndcg_at_10(["a", "b"], []) is None


def test_ndcg_only_top_10(metrics: Any) -> None:
    """A relevant doc at rank 11 does not contribute to nDCG@10."""
    retrieved = ["x"] * 10 + ["hit"]
    # |R|=1, IDCG = 1/log2(2) = 1, DCG = 0 -> nDCG = 0.0
    assert metrics.ndcg_at_10(retrieved, {"hit"}) == pytest.approx(0.0)


def test_idcg_caps_at_relevant_count(metrics: Any) -> None:
    """IDCG@10 sums over min(10, |R|) — 3 relevant docs -> 3 ideal slots."""
    idcg = metrics.idcg_at_k({"a", "b", "c"}, 10)
    expected = sum(1 / math.log2(i + 1) for i in range(1, 4))
    assert idcg == pytest.approx(expected)


# --------------------------------------------------------------------------
# score_query — skips |R| == 0
# --------------------------------------------------------------------------


def test_score_query_skips_empty_relevant(metrics: Any) -> None:
    """A query with zero labeled relevant docs is skipped (returns None)."""
    assert metrics.score_query(["a", "b", "c"], []) is None
    assert metrics.score_query(["a"], set()) is None


def test_score_query_returns_all_metrics(metrics: Any) -> None:
    scores = metrics.score_query(["hit", "x"], {"hit"})
    assert scores is not None
    for key in ("P_at_1", "P_at_5", "P_at_10", "R_at_1", "R_at_5", "R_at_10", "MRR", "nDCG_at_10"):
        assert key in scores
    assert scores["P_at_1"] == pytest.approx(1.0)
    assert scores["MRR"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# aggregate — mean / stderr / bootstrap CI
# --------------------------------------------------------------------------


def test_aggregate_mean(metrics: Any) -> None:
    agg = metrics.aggregate([{"P_at_5": 0.4}, {"P_at_5": 0.6}])
    assert agg["P_at_5"]["mean"] == pytest.approx(0.5)
    assert agg["P_at_5"]["n"] == 2


def test_aggregate_stderr(metrics: Any) -> None:
    """stderr = stdev / sqrt(n)."""
    agg = metrics.aggregate([{"m": 0.0}, {"m": 1.0}])
    # stdev of [0,1] is sqrt(0.5); stderr = sqrt(0.5)/sqrt(2) = 0.5
    assert agg["m"]["stderr"] == pytest.approx(0.5)


def test_aggregate_bootstrap_ci_is_deterministic(metrics: Any) -> None:
    """Same input + same seed -> identical CI (replay determinism)."""
    rows = [{"m": v / 10.0} for v in range(10)]
    a = metrics.aggregate(rows, with_ci=True, resamples=500, seed=42)
    b = metrics.aggregate(rows, with_ci=True, resamples=500, seed=42)
    assert a["m"]["bootstrap_ci_95"] == b["m"]["bootstrap_ci_95"]
    lo, hi = a["m"]["bootstrap_ci_95"]
    assert lo <= a["m"]["mean"] <= hi


def test_aggregate_no_ci_by_default(metrics: Any) -> None:
    agg = metrics.aggregate([{"m": 0.5}])
    assert "bootstrap_ci_95" not in agg["m"]


def test_aggregate_empty_input(metrics: Any) -> None:
    assert metrics.aggregate([]) == {}
