"""Tests for records.py — eval.query.v1 / eval.judgment.v1 schemas + IO (ADR-742).

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
    # Sibling modules import each other by their bare name (records, capture, ...);
    # alias the bare name so a freshly loaded module resolves its siblings.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def records() -> Any:
    return _load("records", "records.py")


@pytest.fixture()
def evals_tmp(records: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect every eval artifact path to a tmp dir.

    `_docs_evals_dir` is the single chokepoint — every other path helper
    (queries_dir, judgments_dir, ...) is built on it, so patching it redirects
    the whole module.
    """
    root = tmp_path / "evals"
    monkeypatch.setattr(records, "_docs_evals_dir", lambda: root)
    return root


# --------------------------------------------------------------------------
# query_id — stability + collision
# --------------------------------------------------------------------------


def test_query_id_is_stable(records: Any) -> None:
    """Same query + source -> same id, every time."""
    a = records.query_id("typed knowledge graphs", "/ask")
    b = records.query_id("typed knowledge graphs", "/ask")
    assert a == b
    assert len(a) == 12


def test_query_id_distinguishes_source(records: Any) -> None:
    """Same query, different source -> different id."""
    ask = records.query_id("typed knowledge graphs", "/ask")
    direct = records.query_id("typed knowledge graphs", "direct")
    assert ask != direct


def test_query_id_distinguishes_query(records: Any) -> None:
    one = records.query_id("alpha", "/ask")
    two = records.query_id("beta", "/ask")
    assert one != two


# --------------------------------------------------------------------------
# Query record round-trip + dedupe
# --------------------------------------------------------------------------


def test_query_record_round_trip(records: Any, evals_tmp: Path) -> None:
    rec = records.build_query_record(
        query="what did I read about RRF",
        source="/ask",
        tool="unified-search",
        returned=[{"id": "vault://wiki/rrf", "rank": 1, "score": 0.9}],
        retrieval_config={"augur_commit": "abc", "vault_manifest_hash": "def"},
    )
    assert rec["_schema"] == records.QUERY_SCHEMA
    assert not records.validate_query_record(rec)
    path = records.write_query_record(rec)
    assert path.is_file()
    loaded = records.read_query_records()
    assert len(loaded) == 1
    assert loaded[0]["id"] == rec["id"]
    assert loaded[0]["query"] == "what did I read about RRF"


def test_read_query_records_dedupes_by_id_most_recent_wins(
    records: Any, evals_tmp: Path
) -> None:
    """Two records with the same id collapse to the most recent ts."""
    base = records.build_query_record(
        query="dedupe me", source="/ask", tool="unified-search", ts="2026-05-10T00:00:00Z"
    )
    newer = dict(base)
    newer["ts"] = "2026-05-12T00:00:00Z"
    newer["top_k"] = 99
    records.write_query_record(base, evals_tmp / "queries" / "2026-05-10.jsonl")
    records.write_query_record(newer, evals_tmp / "queries" / "2026-05-12.jsonl")
    loaded = records.read_query_records()
    assert len(loaded) == 1
    assert loaded[0]["top_k"] == 99  # newer wins


def test_read_query_records_since_until_filter(records: Any, evals_tmp: Path) -> None:
    for day, ts in (("2026-05-01", "2026-05-01T00:00:00Z"), ("2026-05-15", "2026-05-15T00:00:00Z")):
        rec = records.build_query_record(
            query=f"q-{day}", source="/ask", tool="unified-search", ts=ts
        )
        records.write_query_record(rec, evals_tmp / "queries" / f"{day}.jsonl")
    only_recent = records.read_query_records(since="2026-05-10T00:00:00Z")
    assert len(only_recent) == 1
    assert only_recent[0]["query"] == "q-2026-05-15"


def test_read_query_records_skips_malformed_lines(records: Any, evals_tmp: Path) -> None:
    """A torn / malformed JSONL line is skipped; the prefix survives."""
    qdir = evals_tmp / "queries"
    qdir.mkdir(parents=True)
    good = records.build_query_record(query="good", source="/ask", tool="unified-search")
    path = qdir / "2026-05-13.jsonl"
    path.write_text(
        json.dumps(good) + "\n" + "{not valid json" + "\n", encoding="utf-8"
    )
    loaded = records.read_query_records()
    assert len(loaded) == 1
    assert loaded[0]["query"] == "good"


# --------------------------------------------------------------------------
# Judgment frontmatter parse
# --------------------------------------------------------------------------


def test_judgment_round_trip(records: Any, evals_tmp: Path) -> None:
    judgment = records.build_judgment_record(
        query_id_value="a1b2c3d4e5f6",
        query="what did I read about typed knowledge graphs",
        relevant_doc_ids=[
            "vault://wiki/typed-knowledge-graphs",
            "source-cards://2026-05-08/gbrain-borrow-notes",
        ],
        labeled_by="gsannikov",
        notes="the second hit is the original derivation",
    )
    path = records.write_judgment(judgment)
    assert path.is_file()
    parsed = records.parse_judgment_file(path)
    assert parsed is not None
    assert parsed["_schema"] == records.JUDGMENT_SCHEMA
    assert parsed["query_id"] == "a1b2c3d4e5f6"
    assert parsed["relevant_doc_ids"] == [
        "vault://wiki/typed-knowledge-graphs",
        "source-cards://2026-05-08/gbrain-borrow-notes",
    ]


def test_read_judgments_keyed_by_query_id(records: Any, evals_tmp: Path) -> None:
    for qid in ("aaa111", "bbb222"):
        records.write_judgment(
            records.build_judgment_record(
                query_id_value=qid, query=f"q-{qid}", relevant_doc_ids=[f"doc-{qid}"]
            )
        )
    judgments = records.read_judgments()
    assert set(judgments) == {"aaa111", "bbb222"}
    assert judgments["aaa111"]["relevant_doc_ids"] == ["doc-aaa111"]


def test_parse_judgment_missing_frontmatter_returns_none(
    records: Any, evals_tmp: Path
) -> None:
    jdir = evals_tmp / "judgments"
    jdir.mkdir(parents=True)
    bad = jdir / "nofrontmatter.md"
    bad.write_text("# just a heading, no frontmatter\n", encoding="utf-8")
    assert records.parse_judgment_file(bad) is None


# --------------------------------------------------------------------------
# vault_manifest_hash determinism
# --------------------------------------------------------------------------


def test_vault_manifest_hash_is_deterministic(records: Any) -> None:
    """Two consecutive calls (no vault change) -> identical hash."""
    first = records.vault_manifest_hash()
    second = records.vault_manifest_hash()
    assert first == second
    # Hash is either empty (no vault) or a 12-char hex digest.
    assert first == "" or len(first) == 12


def test_validate_query_record_flags_bad_schema(records: Any) -> None:
    rec = records.build_query_record(query="x", source="/ask", tool="unified-search")
    rec["_schema"] = "eval.query.v0"
    problems = records.validate_query_record(rec)
    assert any("_schema" in p for p in problems)
