"""Tests for src/lib/index/rrf.py -- Reciprocal Rank Fusion (ADR-739)."""

from __future__ import annotations

from src.lib.index.rrf import RankedHit, RetrieverSource, fuse


def test_doc_ranked_high_in_two_sources_beats_one() -> None:
    a = [RankedHit("doc-A", 1, 9.0), RankedHit("doc-B", 2, 8.0)]
    b = [RankedHit("doc-A", 1, 0.9), RankedHit("doc-C", 2, 0.8)]

    fused = fuse({"ripgrep": a, "bm25": b}, k=60, top_k=10)

    assert fused[0]["doc_id"] == "doc-A"
    assert sorted(fused[0]["provenance"]) == ["bm25", "ripgrep"]
    assert fused[0]["score"] > fused[1]["score"]


def test_absent_doc_contributes_nothing_and_k_is_configurable() -> None:
    a = [RankedHit("doc-A", 1, 1.0)]

    assert fuse({"a": a}, k=60, top_k=5)[0]["score"] == round(1 / 61, 6)
    assert fuse({"a": a}, k=10, top_k=5)[0]["score"] == round(1 / 11, 6)


def test_empty_sources_and_determinism() -> None:
    assert fuse({}, k=60, top_k=5) == []
    assert fuse({"a": []}, k=60, top_k=5) == []
    a = [RankedHit("d1", 1, 1.0), RankedHit("d2", 2, 0.5)]
    assert fuse({"a": a}, k=60, top_k=5) == fuse({"a": a}, k=60, top_k=5)


def test_ripgrep_source_satisfies_protocol() -> None:
    class _Stub:
        name = "stub"

        def search(self, query: str, *, limit: int) -> list[RankedHit]:
            return []

    assert isinstance(_Stub(), RetrieverSource)
