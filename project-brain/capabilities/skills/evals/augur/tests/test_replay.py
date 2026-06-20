"""Tests for replay.py -- determinism, unlabeled counting, drift, --config (ADR-742).

Live retrieval is mocked so the tests do not depend on a real vault/index state;
the determinism and scoring contract is what's under test, not retrieval itself.

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
"""

from __future__ import annotations

import importlib.util
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
def capture(records: Any) -> Any:
    return _load("capture", "capture.py")


@pytest.fixture()
def replay(records: Any, metrics: Any, capture: Any) -> Any:
    return _load("replay", "replay.py")


@pytest.fixture()
def evals_tmp(
    records: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    root = tmp_path / "evals"
    monkeypatch.setattr(records, "_docs_evals_dir", lambda: root)
    return root


def _seed_query(records: Any, evals_tmp: Path, query: str, source: str = "direct",
                manifest: str = "manifest-aaa") -> str:
    """Write one captured query record; return its id."""
    rec = records.build_query_record(
        query=query,
        source=source,
        tool="unified-search",
        retrieval_config={
            "augur_commit": "commit-1",
            "vault_manifest_hash": manifest,
            "rrf_k": None,
            "rrf_weights": None,
        },
    )
    records.write_query_record(rec, evals_tmp / "queries" / "2026-05-13.jsonl")
    return rec["id"]


def _seed_judgment(records: Any, qid: str, query: str, relevant: list[str]) -> None:
    records.write_judgment(
        records.build_judgment_record(
            query_id_value=qid, query=query, relevant_doc_ids=relevant
        )
    )


# --------------------------------------------------------------------------
# Determinism -- two runs produce identical scored rows
# --------------------------------------------------------------------------


def test_replay_is_deterministic(
    replay: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two consecutive replays of the same query set -> identical scored rows."""
    qid = _seed_query(records, evals_tmp, "alpha")
    _seed_judgment(records, qid, "alpha", ["doc-a", "doc-b"])

    # Deterministic mock retrieval: always returns the same ranked list.
    monkeypatch.setattr(
        replay, "run_retrieval", lambda *a, **k: ["doc-a", "doc-x", "doc-b"]
    )
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-aaa")

    first = replay.replay(corpus="all")
    second = replay.replay(corpus="all")

    assert first["queries"] == second["queries"]
    assert first["aggregates"] == second["aggregates"]
    assert first["counts"] == second["counts"]


def test_replay_scores_match_metrics_contract(
    replay: Any, records: Any, metrics: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-query scores in the replay result match a direct metrics call."""
    qid = _seed_query(records, evals_tmp, "alpha")
    _seed_judgment(records, qid, "alpha", ["doc-a", "doc-b"])
    retrieved = ["doc-a", "doc-x", "doc-b"]
    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: list(retrieved))
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-aaa")

    result = replay.replay(corpus="all")
    assert len(result["queries"]) == 1
    row = result["queries"][0]
    expected = metrics.score_query(retrieved, ["doc-a", "doc-b"])
    assert row["scores"] == expected


# --------------------------------------------------------------------------
# Unlabeled query counting -- skip, don't score 0
# --------------------------------------------------------------------------


def test_unlabeled_queries_are_skipped(
    replay: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A query with no judgment is skipped and counted under unlabeled_queries."""
    labeled_id = _seed_query(records, evals_tmp, "has-judgment")
    _seed_judgment(records, labeled_id, "has-judgment", ["doc-a"])
    _seed_query(records, evals_tmp, "no-judgment")  # no judgment authored

    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: ["doc-a"])
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-aaa")

    result = replay.replay(corpus="all")
    assert result["counts"]["scored"] == 1
    assert result["counts"]["unlabeled"] == 1
    assert len(result["unlabeled_queries"]) == 1
    assert result["unlabeled_queries"][0]["reason"] == "no_judgment"


def test_empty_relevant_judgment_is_unlabeled(
    replay: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A judgment with zero relevant docs counts as unlabeled, not scored 0."""
    qid = _seed_query(records, evals_tmp, "empty-judgment")
    _seed_judgment(records, qid, "empty-judgment", [])  # empty relevant list

    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: ["doc-a"])
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-aaa")

    result = replay.replay(corpus="all")
    assert result["counts"]["scored"] == 0
    assert result["counts"]["unlabeled"] == 1
    assert result["unlabeled_queries"][0]["reason"] == "empty_relevant"


# --------------------------------------------------------------------------
# index_drift detection
# --------------------------------------------------------------------------


def test_index_drift_detected(
    replay: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live manifest != recorded manifest -> index_drift flagged."""
    qid = _seed_query(records, evals_tmp, "alpha", manifest="manifest-OLD")
    _seed_judgment(records, qid, "alpha", ["doc-a"])

    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: ["doc-a"])
    # Live manifest differs from the recorded "manifest-OLD".
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-NEW")

    result = replay.replay(corpus="all")
    assert result["index_drift"] is True
    assert result["drift_detail"]["queries_with_drift"] == 1
    assert result["queries"][0]["index_drift"] is True


def test_no_drift_when_manifest_matches(
    replay: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qid = _seed_query(records, evals_tmp, "alpha", manifest="manifest-SAME")
    _seed_judgment(records, qid, "alpha", ["doc-a"])
    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: ["doc-a"])
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-SAME")
    result = replay.replay(corpus="all")
    assert result["index_drift"] is False
    assert result["drift_detail"] is None


# --------------------------------------------------------------------------
# --config override
# --------------------------------------------------------------------------


def test_config_override_changes_params(
    replay: Any, records: Any, evals_tmp: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A --config YAML overrides the recorded retrieval params passed to retrieval."""
    qid = _seed_query(records, evals_tmp, "alpha")
    _seed_judgment(records, qid, "alpha", ["doc-a"])

    captured_params: dict[str, Any] = {}

    def _spy_retrieval(tool, query, *, mode, top_k, scopes, project):
        captured_params["mode"] = mode
        captured_params["top_k"] = top_k
        return ["doc-a"]

    monkeypatch.setattr(replay, "run_retrieval", _spy_retrieval)
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-aaa")

    config_file = tmp_path / "override.yaml"
    config_file.write_text("mode: tokenmax\ntop_k: 25\n", encoding="utf-8")

    replay.replay(config_path=config_file, corpus="all")
    assert captured_params["mode"] == "tokenmax"
    assert captured_params["top_k"] == 25


def test_missing_config_falls_back_to_recorded(
    replay: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing --config path is logged and ignored -- recorded params are used."""
    qid = _seed_query(records, evals_tmp, "alpha")
    _seed_judgment(records, qid, "alpha", ["doc-a"])
    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: ["doc-a"])
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-aaa")
    result = replay.replay(config_path="/nonexistent/config.yaml", corpus="all")
    assert result["config_override"] == {}
    assert result["counts"]["scored"] == 1


# --------------------------------------------------------------------------
# Corpus filtering
# --------------------------------------------------------------------------


def test_corpus_filter_captured_vs_external(
    replay: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """corpus='captured' excludes external:* records and vice versa."""
    cap_id = _seed_query(records, evals_tmp, "captured-q", source="direct")
    _seed_judgment(records, cap_id, "captured-q", ["doc-a"])

    ext_rec = records.build_query_record(
        query="external-q",
        source="external:longmem-sample",
        tool="unified-search",
        retrieval_config={"augur_commit": "c", "vault_manifest_hash": "manifest-aaa"},
    )
    ext_qdir = evals_tmp / "external" / "longmem-sample" / "queries"
    records.write_query_record(ext_rec, ext_qdir / "longmem-sample.jsonl")
    records.write_judgment(
        records.build_judgment_record(
            query_id_value=ext_rec["id"], query="external-q", relevant_doc_ids=["doc-z"]
        ),
        evals_tmp / "external" / "longmem-sample" / "judgments" / f"{ext_rec['id']}.md",
    )

    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: ["doc-a"])
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "manifest-aaa")

    captured_only = replay.replay(corpus="captured")
    assert captured_only["counts"]["total_queries"] == 1
    assert captured_only["queries"][0]["corpus"] == "captured"

    external_only = replay.replay(corpus="external")
    assert external_only["counts"]["total_queries"] == 1
    assert external_only["queries"][0]["corpus"] == "external:longmem-sample"

    everything = replay.replay(corpus="all")
    assert everything["counts"]["total_queries"] == 2
