"""Tests for report.py -- summary.md / raw.jsonl / manifest.json (ADR-742).

Verifies the spec section 4.3.3 report schemas, per-bucket breakdown, delta-vs-
baseline rendering, alert computation, and byte-stable raw.jsonl ordering.

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
"""

from __future__ import annotations

import importlib.util
import json
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
def records() -> Any:
    return _load("records", "records.py")


@pytest.fixture()
def metrics() -> Any:
    return _load("metrics", "metrics.py")


@pytest.fixture()
def report(records: Any, metrics: Any) -> Any:
    return _load("report", "report.py")


@pytest.fixture()
def evals_tmp(records: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "evals"
    monkeypatch.setattr(records, "_docs_evals_dir", lambda: root)
    return root


def _replay_result(metrics: Any, rows: list[dict]) -> dict:
    """Build a minimal replay-result dict from (id, source, retrieved, relevant) rows."""
    scored = []
    for r in rows:
        scores = metrics.score_query(r["retrieved"], r["relevant"])
        scored.append(
            {
                "id": r["id"],
                "query": r.get("query", r["id"]),
                "source": r.get("source", "direct"),
                "tool": "unified-search",
                "mode": "hybrid",
                "corpus": r.get("corpus", "captured"),
                "retrieved": r["retrieved"],
                "relevant_doc_ids": r["relevant"],
                "index_drift": False,
                "scores": scores,
            }
        )

    def _agg(rs):
        return metrics.aggregate([x["scores"] for x in rs], with_ci=False, seed=1742)

    aggregates = {"overall": _agg(scored)}
    by_source: dict[str, list] = {}
    for row in scored:
        by_source.setdefault(row["source"], []).append(row)
    if len(by_source) > 1:
        aggregates["by_source"] = {k: _agg(v) for k, v in sorted(by_source.items())}
    aggregates["by_corpus"] = {
        c: _agg([x for x in scored if x["corpus"] == c])
        for c in sorted({x["corpus"] for x in scored})
    }
    return {
        "queries": scored,
        "unlabeled_queries": [],
        "aggregates": aggregates,
        "index_drift": False,
        "drift_detail": None,
        "live_commit": "abc1234",
        "live_vault_manifest_hash": "deadbeef0123",
        "config_override": {},
        "corpus": "all",
        "since": None,
        "started_at": "2026-05-13T03:00:00Z",
        "finished_at": "2026-05-13T03:00:05Z",
        "counts": {"total_queries": len(scored), "scored": len(scored), "unlabeled": 0},
    }


# --------------------------------------------------------------------------
# Report directory + the three files
# --------------------------------------------------------------------------


def test_write_report_produces_three_files(
    report: Any, metrics: Any, evals_tmp: Path
) -> None:
    result = _replay_result(
        metrics,
        [{"id": "q1", "retrieved": ["doc-a", "doc-b"], "relevant": ["doc-a"]}],
    )
    written = report.write_report(result, compare_baseline=False)
    rdir = Path(written["report_dir"])
    assert (rdir / "summary.md").is_file()
    assert (rdir / "raw.jsonl").is_file()
    assert (rdir / "manifest.json").is_file()


def test_run_id_format(report: Any) -> None:
    """<YYYY-MM-DD-HHMMSS>-<commit[:7]>."""
    run_id = report.make_run_id("abc1234567")
    parts = run_id.rsplit("-", 1)
    assert parts[1] == "abc1234"
    assert len(parts[0]) == len("2026-05-13-030000")


def test_manifest_schema(report: Any, metrics: Any, evals_tmp: Path) -> None:
    result = _replay_result(
        metrics, [{"id": "q1", "retrieved": ["doc-a"], "relevant": ["doc-a"]}]
    )
    written = report.write_report(result, compare_baseline=False)
    manifest = json.loads(Path(written["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["_schema"] == "eval.report.manifest.v1"
    for key in (
        "run_id",
        "augur_commit",
        "vault_manifest_hash",
        "query_set_hash",
        "counts",
        "index_drift",
    ):
        assert key in manifest


def test_raw_jsonl_one_line_per_scored_query(
    report: Any, metrics: Any, evals_tmp: Path
) -> None:
    result = _replay_result(
        metrics,
        [
            {"id": "q1", "retrieved": ["doc-a"], "relevant": ["doc-a"]},
            {"id": "q2", "retrieved": ["doc-b"], "relevant": ["doc-c"]},
        ],
    )
    written = report.write_report(result, compare_baseline=False)
    lines = Path(written["raw_path"]).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert {p["id"] for p in parsed} == {"q1", "q2"}
    for p in parsed:
        assert "scores" in p and "retrieved" in p and "relevant_doc_ids" in p


def test_raw_jsonl_is_byte_stable(report: Any, metrics: Any, evals_tmp: Path) -> None:
    """Two renders of the same replay result -> byte-identical raw.jsonl."""
    result = _replay_result(
        metrics,
        [
            {"id": "q1", "retrieved": ["doc-a"], "relevant": ["doc-a"]},
            {"id": "q2", "retrieved": ["doc-b"], "relevant": ["doc-c"]},
        ],
    )
    a = report.render_raw_jsonl(result)
    b = report.render_raw_jsonl(result)
    assert a == b


# --------------------------------------------------------------------------
# summary.md content
# --------------------------------------------------------------------------


def test_summary_has_overall_table(report: Any, metrics: Any, evals_tmp: Path) -> None:
    result = _replay_result(
        metrics, [{"id": "q1", "retrieved": ["doc-a"], "relevant": ["doc-a"]}]
    )
    summary = report.render_summary(result, "2026-05-13-030000-abc1234")
    assert "# Eval Replay Report" in summary
    assert "### Overall" in summary
    assert "P_at_5" in summary
    assert "MRR" in summary


def test_summary_per_bucket_breakdown(report: Any, metrics: Any, evals_tmp: Path) -> None:
    """Per-source breakdown appears when sources partition."""
    result = _replay_result(
        metrics,
        [
            {"id": "q1", "source": "/ask", "retrieved": ["doc-a"], "relevant": ["doc-a"]},
            {"id": "q2", "source": "direct", "retrieved": ["doc-b"], "relevant": ["doc-b"]},
        ],
    )
    summary = report.render_summary(result, "run-x")
    assert "## By source" in summary
    assert "/ask" in summary


def test_summary_unlabeled_section(report: Any, metrics: Any, evals_tmp: Path) -> None:
    result = _replay_result(
        metrics, [{"id": "q1", "retrieved": ["doc-a"], "relevant": ["doc-a"]}]
    )
    result["unlabeled_queries"] = [
        {"id": "u1", "source": "direct", "reason": "no_judgment"}
    ]
    summary = report.render_summary(result, "run-x")
    assert "## Unlabeled queries" in summary
    assert "u1" in summary


# --------------------------------------------------------------------------
# Delta vs. baseline + alerts
# --------------------------------------------------------------------------


def test_delta_vs_baseline_rendered(report: Any, metrics: Any, evals_tmp: Path) -> None:
    """A first run with no baseline, then a second run renders a delta table."""
    # First run -> becomes the "most recent prior run" baseline.
    first = _replay_result(
        metrics, [{"id": "q1", "retrieved": ["doc-a"], "relevant": ["doc-a"]}]
    )
    report.write_report(first, run_id="2026-05-13-010000-aaaaaaa", compare_baseline=False)
    # Second run -> a worse result, compare against the prior run.
    second = _replay_result(
        metrics, [{"id": "q1", "retrieved": ["doc-WRONG"], "relevant": ["doc-a"]}]
    )
    written = report.write_report(
        second, run_id="2026-05-13-020000-bbbbbbb", compare_baseline=True
    )
    summary = Path(written["summary_path"]).read_text(encoding="utf-8")
    assert "Delta vs. baseline" in summary


def test_compute_alerts_fires_on_big_drop(report: Any) -> None:
    """A headline metric dropping > threshold produces an alert row."""
    baseline = {"overall": {"P_at_5": {"mean": 0.80}, "MRR": {"mean": 0.70}}}
    current = {"overall": {"P_at_5": {"mean": 0.60}, "MRR": {"mean": 0.69}}}
    # P@5 dropped 20 points (> 5.0), MRR dropped 1 point (< 5.0).
    alerts = report.compute_alerts(current, baseline, {"P_at_5": 5.0, "MRR": 5.0})
    assert len(alerts) == 1
    assert alerts[0]["metric"] == "P_at_5"
    assert alerts[0]["severity"] == "WARN"


def test_compute_alerts_no_fire_on_equal_threshold(report: Any) -> None:
    """A drop EXACTLY equal to the threshold does not alert (strictly greater)."""
    baseline = {"overall": {"P_at_5": {"mean": 0.80}}}
    current = {"overall": {"P_at_5": {"mean": 0.75}}}  # exactly 5.0 points
    alerts = report.compute_alerts(current, baseline, {"P_at_5": 5.0})
    assert alerts == []


def test_compute_alerts_no_fire_on_improvement(report: Any) -> None:
    baseline = {"overall": {"P_at_5": {"mean": 0.50}}}
    current = {"overall": {"P_at_5": {"mean": 0.90}}}
    assert report.compute_alerts(current, baseline, {"P_at_5": 5.0}) == []


# --------------------------------------------------------------------------
# parse_summary_numbers
# --------------------------------------------------------------------------


def test_parse_summary_numbers_latest(report: Any, metrics: Any, evals_tmp: Path) -> None:
    result = _replay_result(
        metrics, [{"id": "q1", "retrieved": ["doc-a"], "relevant": ["doc-a"]}]
    )
    report.write_report(result, run_id="2026-05-13-030000-abc1234", compare_baseline=False)
    parsed = report.parse_summary_numbers()
    assert parsed["run_id"] == "2026-05-13-030000-abc1234"
    assert "P_at_5_mean" in parsed["scores"]
    assert parsed["scores"]["P_at_5_mean"] is not None
