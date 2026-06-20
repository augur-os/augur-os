"""Retrieval quality metrics — the regression contract (spec §4.4).

These implementations are normative. Every later slate ADR that touches
retrieval is tested against them. The non-obvious choices, spelled out so they
cannot drift:

- **P@k denominator is `k`**, NOT `min(k, |retrieved|)`. If retrieval returns
  fewer than k results, the missing slots count as non-relevant. A system that
  returns too few is penalized. (spec §4.4.1)
- **MRR is over the FULL retrieved list**, not top_k. A relevant doc at rank 50
  yields 1/50, not 0 — MRR stays sensitive to deep-rank regressions. (spec §4.4.3)
- **nDCG@10 uses binary gain** ∈ {0, 1}; IDCG@10 sums over `min(10, |R|)`. (spec §4.4.4)
- **Queries with zero labeled relevant docs are SKIPPED**, not scored 0. They
  measure a labeling gap, surfaced separately as `unlabeled_queries`. R@k and
  nDCG return `None` for `|R| == 0`; the caller skips them. (spec §4.4)

No LLM calls. Pure stdlib + `math`.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Iterable, Sequence


# --------------------------------------------------------------------------
# Per-query metrics
# --------------------------------------------------------------------------


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """P@k = |set(top_k) ∩ R| / k.

    Denominator is **k**, not `min(k, |retrieved|)` — returning fewer than k
    results is penalized (spec §4.4.1).
    """
    if k <= 0:
        return 0.0
    relevant_set = set(relevant)
    top_k = list(retrieved[:k])
    hits = len(set(top_k) & relevant_set)
    return hits / k


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float | None:
    """R@k = |set(top_k) ∩ R| / |R|.

    Returns `None` when `|R| == 0` (undefined → caller skips the query and counts
    it under `unlabeled_queries`, spec §4.4.2).
    """
    relevant_set = set(relevant)
    if not relevant_set:
        return None
    if k <= 0:
        return 0.0
    top_k = list(retrieved[:k])
    hits = len(set(top_k) & relevant_set)
    return hits / len(relevant_set)


def mrr(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """MRR = 1 / rank_of_first_relevant_in_retrieved (1-indexed), 0 if none.

    Computed over the **full** retrieved list, not top_k (spec §4.4.3).
    """
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant_set:
            return 1.0 / rank
    return 0.0


def dcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int = 10) -> float:
    """DCG@k with binary gain ∈ {0, 1}: sum over i in [1..k] of gain_i / log2(i+1)."""
    relevant_set = set(relevant)
    total = 0.0
    for i, doc_id in enumerate(retrieved[:k], start=1):
        gain = 1.0 if doc_id in relevant_set else 0.0
        if gain:
            total += gain / math.log2(i + 1)
    return total


def idcg_at_k(relevant: Iterable[str], k: int = 10) -> float:
    """IDCG@k = sum over i in [1..min(k, |R|)] of 1 / log2(i+1)."""
    n = min(k, len(set(relevant)))
    return sum(1.0 / math.log2(i + 1) for i in range(1, n + 1))


def ndcg_at_10(retrieved: Sequence[str], relevant: Iterable[str]) -> float | None:
    """nDCG@10 = DCG@10 / IDCG@10, binary gain.

    Returns `None` when `|R| == 0` (IDCG is 0 → query skipped, spec §4.4.4).
    """
    relevant_set = set(relevant)
    if not relevant_set:
        return None
    idcg = idcg_at_k(relevant_set, 10)
    if idcg == 0:
        return None
    dcg = dcg_at_k(retrieved, relevant_set, 10)
    return dcg / idcg


# --------------------------------------------------------------------------
# Full per-query metric bundle
# --------------------------------------------------------------------------

# The k values P/R are computed at. P@1/P@5/P@10, R@1/R@5/R@10.
K_VALUES = (1, 5, 10)


def score_query(retrieved: Sequence[str], relevant: Iterable[str]) -> dict[str, float] | None:
    """Score one query → a dict of all metrics, or `None` if it must be skipped.

    Returns `None` when `|R| == 0` — the caller counts it under
    `unlabeled_queries` and excludes it from every aggregate (spec §4.4).
    """
    relevant_set = set(relevant)
    if not relevant_set:
        return None
    retrieved = list(retrieved)
    scores: dict[str, float] = {}
    for k in K_VALUES:
        scores[f"P_at_{k}"] = precision_at_k(retrieved, relevant_set, k)
        r = recall_at_k(retrieved, relevant_set, k)
        scores[f"R_at_{k}"] = r if r is not None else 0.0
    scores["MRR"] = mrr(retrieved, relevant_set)
    ndcg = ndcg_at_10(retrieved, relevant_set)
    scores["nDCG_at_10"] = ndcg if ndcg is not None else 0.0
    return scores


# --------------------------------------------------------------------------
# Aggregation + variance (spec §4.4.5)
# --------------------------------------------------------------------------


def _bootstrap_ci_95(
    values: Sequence[float], resamples: int = 1000, seed: int = 0
) -> tuple[float, float]:
    """95% bootstrap confidence interval over `resamples` resamples.

    Deterministic given `seed` — the replay path seeds from a fixed value so
    two consecutive replays produce identical CIs.
    """
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = max(0, int(0.025 * resamples) - 1)
    hi_idx = min(resamples - 1, int(0.975 * resamples) - 1)
    return (means[lo_idx], means[hi_idx])


def aggregate(
    per_query_scores: Sequence[dict[str, float]],
    *,
    with_ci: bool = False,
    resamples: int = 1000,
    seed: int = 0,
) -> dict[str, dict[str, object]]:
    """Aggregate per-query score dicts → mean / stderr / (optional) bootstrap CI.

    For each metric the report records:
    - `mean` across non-skipped queries (the headline number)
    - `stderr` = stdev / sqrt(n) (cheap, every replay)
    - `bootstrap_ci_95` = (lo, hi) over `resamples` resamples (only when
      `with_ci=True` — paid on baseline + nightly summary, not every replay)

    `n` is the count of scored (non-skipped) queries — identical for every
    metric since a query is scored on all metrics or skipped entirely.
    """
    n = len(per_query_scores)
    if n == 0:
        return {}

    metric_names = sorted({key for scores in per_query_scores for key in scores})
    out: dict[str, dict[str, object]] = {}
    for metric in metric_names:
        values = [float(scores.get(metric, 0.0)) for scores in per_query_scores]
        mean = sum(values) / n
        if n > 1:
            stderr = statistics.stdev(values) / math.sqrt(n)
        else:
            stderr = 0.0
        entry: dict[str, object] = {
            "mean": mean,
            "stderr": stderr,
            "n": n,
        }
        if with_ci:
            entry["bootstrap_ci_95"] = list(
                _bootstrap_ci_95(values, resamples=resamples, seed=seed)
            )
        out[metric] = entry
    return out
