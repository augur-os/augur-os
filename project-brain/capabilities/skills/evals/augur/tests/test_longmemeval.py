"""Tests for longmemeval.py -- external-corpus adapter (ADR-742).

Verifies a sample LongMemEval JSONL converts into the v1 query + judgment shape
and that replay buckets the external corpus separately.

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
def capture(records: Any) -> Any:
    return _load("capture", "capture.py")


@pytest.fixture()
def longmemeval(records: Any) -> Any:
    return _load("longmemeval", "longmemeval.py")


@pytest.fixture()
def replay(records: Any, metrics: Any, capture: Any) -> Any:
    return _load("replay", "replay.py")


@pytest.fixture()
def evals_tmp(records: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "evals"
    monkeypatch.setattr(records, "_docs_evals_dir", lambda: root)
    return root


def _sample_corpus(tmp_path: Path) -> Path:
    """Write a small LongMemEval-format JSONL sample."""
    rows = [
        {
            "question": "what year did the project start",
            "answer": "2024",
            "evidence_doc_ids": ["session-1", "session-7"],
            "corpus_id": "longmem-sample",
        },
        {
            "question": "who proposed the schema change",
            "answer": "the lead",
            "evidence_doc_ids": ["session-3"],
        },
        # Malformed: missing evidence_doc_ids -> skipped.
        {"question": "no evidence here"},
        # Malformed: missing question -> skipped.
        {"evidence_doc_ids": ["session-9"]},
    ]
    path = tmp_path / "longmem.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return path


# --------------------------------------------------------------------------
# import_corpus
# --------------------------------------------------------------------------


def test_import_corpus_emits_v1_files(
    longmemeval: Any, records: Any, evals_tmp: Path, tmp_path: Path
) -> None:
    sample = _sample_corpus(tmp_path)
    result = longmemeval.import_corpus(sample, "longmem-sample")

    assert result["query_count"] == 2  # 2 valid rows
    assert result["judgment_count"] == 2
    assert result["skipped"] == 2  # 2 malformed rows

    queries_path = Path(result["queries_path"])
    assert queries_path.is_file()
    lines = queries_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        rec = json.loads(line)
        assert rec["_schema"] == records.QUERY_SCHEMA
        assert rec["source"] == "external:longmem-sample"
        assert rec["tool"] == "unified-search"
        assert rec["returned"] == []


def test_import_corpus_judgments_parseable(
    longmemeval: Any, records: Any, evals_tmp: Path, tmp_path: Path
) -> None:
    sample = _sample_corpus(tmp_path)
    longmemeval.import_corpus(sample, "longmem-sample")
    judgments = records.read_judgments(include_external=True)
    # Two judgments imported, keyed by query id.
    assert len(judgments) == 2
    all_relevant = {tuple(sorted(j["relevant_doc_ids"])) for j in judgments.values()}
    assert ("session-1", "session-7") in all_relevant
    assert ("session-3",) in all_relevant


def test_import_corpus_is_idempotent(
    longmemeval: Any, records: Any, evals_tmp: Path, tmp_path: Path
) -> None:
    """Re-importing the same corpus does not duplicate query lines."""
    sample = _sample_corpus(tmp_path)
    longmemeval.import_corpus(sample, "longmem-sample")
    longmemeval.import_corpus(sample, "longmem-sample")
    queries = records.read_query_records(include_external=True)
    external = [q for q in queries if q["source"] == "external:longmem-sample"]
    assert len(external) == 2  # not 4


def test_import_corpus_missing_file(longmemeval: Any, evals_tmp: Path) -> None:
    result = longmemeval.import_corpus(Path("/nonexistent/corpus.jsonl"), "x")
    assert "error" in result
    assert result["query_count"] == 0


# --------------------------------------------------------------------------
# Replay buckets the external corpus separately
# --------------------------------------------------------------------------


def test_replay_buckets_external_corpus(
    longmemeval: Any, replay: Any, records: Any, evals_tmp: Path, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """An imported external corpus shows up under corpus='external:<id>' in replay."""
    sample = _sample_corpus(tmp_path)
    longmemeval.import_corpus(sample, "longmem-sample")

    # Also seed one captured query so both buckets exist.
    cap = records.build_query_record(
        query="captured query", source="direct", tool="unified-search",
        retrieval_config={"augur_commit": "c", "vault_manifest_hash": "m"},
    )
    records.write_query_record(cap, evals_tmp / "queries" / "2026-05-13.jsonl")
    records.write_judgment(
        records.build_judgment_record(
            query_id_value=cap["id"], query="captured query", relevant_doc_ids=["doc-a"]
        )
    )

    monkeypatch.setattr(replay, "run_retrieval", lambda *a, **k: ["doc-a", "session-1"])
    monkeypatch.setattr(records, "vault_manifest_hash", lambda: "m")

    result = replay.replay(corpus="all")
    buckets = {row["corpus"] for row in result["queries"]}
    assert "captured" in buckets
    assert "external:longmem-sample" in buckets
    # The aggregates carry a by_corpus breakdown.
    assert "by_corpus" in result["aggregates"]
    assert "external:longmem-sample" in result["aggregates"]["by_corpus"]
