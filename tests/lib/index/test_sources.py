"""Tests for src/lib/index/sources.py -- core RetrieverSources (ADR-739)."""

from __future__ import annotations

from pathlib import Path

from src.lib.index.rrf import RankedHit, RetrieverSource
from src.lib.index.sources import BM25Source, GraphSource, RipgrepSource


class _FakeBM25:
    def __init__(self, results: list[dict] | None = None) -> None:
        self.results = results or [
            {"path": "doc-A.md", "score": 9.1, "meta": {}},
            {"path": "doc-B.md", "score": 4.2, "meta": {}},
        ]
        self.requested_top_k: int | None = None

    def query(self, query: str, top_k: int = 50) -> list[dict]:
        self.requested_top_k = top_k
        return self.results[:top_k]


def _write_document_pointer(path: Path, *, index_status: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" "category: documents\n" f"index_status: {index_status}\n" "---\n" f"{body}\n",
        encoding="utf-8",
    )


def test_bm25_source_conforms_and_ranks_1_indexed() -> None:
    src = BM25Source(_FakeBM25())

    assert isinstance(src, RetrieverSource)
    assert src.name == "bm25"
    hits = src.search("anything", limit=10)
    assert [(h.doc_id, h.rank) for h in hits] == [("doc-A.md", 1), ("doc-B.md", 2)]
    assert all(isinstance(h, RankedHit) for h in hits)


def test_bm25_source_with_no_index_returns_empty() -> None:
    assert BM25Source(None).search("anything", limit=10) == []


def test_bm25_source_limit_zero_returns_empty() -> None:
    assert BM25Source(_FakeBM25()).search("anything", limit=0) == []


def test_bm25_source_filters_stale_documents_after_overfetch() -> None:
    bm25 = _FakeBM25(
        [
            {
                "path": "chunks/documents/stale/chunk.md",
                "score": 10.0,
                "meta": {
                    "category": "documents",
                    "source": "Stale",
                    "index_status": "source_changed",
                },
            },
            {
                "path": "chunks/documents/fresh/chunk.md",
                "score": 9.0,
                "meta": {
                    "category": "documents",
                    "source": "Fresh",
                    "index_status": "synced",
                },
            },
        ]
    )
    src = BM25Source(bm25)

    hits = src.search("deck", limit=1)

    assert bm25.requested_top_k and bm25.requested_top_k > 1
    assert [hit.payload["source"] for hit in hits] == ["Fresh"]


def test_bm25_source_keeps_summary_stale_documents_with_warning() -> None:
    src = BM25Source(
        _FakeBM25(
            [
                {
                    "path": "chunks/documents/summary-stale/chunk.md",
                    "score": 8.0,
                    "meta": {
                        "category": "documents",
                        "source": "Summary Stale",
                        "index_status": "summary_stale",
                    },
                }
            ]
        )
    )

    hits = src.search("deck", limit=10)

    assert hits[0].payload["source"] == "Summary Stale"
    assert hits[0].payload["stale_source_warning"] == "summary_stale"


def test_bm25_source_can_include_source_changed_documents_when_requested() -> None:
    src = BM25Source(
        _FakeBM25(
            [
                {
                    "path": "chunks/documents/stale/chunk.md",
                    "score": 10.0,
                    "meta": {
                        "category": "documents",
                        "source": "Stale",
                        "index_status": "source_changed",
                    },
                }
            ]
        ),
        include_stale_documents=True,
    )

    hits = src.search("deck", limit=10)

    assert hits[0].payload["source"] == "Stale"
    assert hits[0].payload["stale_source_warning"] == "source_changed"


def test_ripgrep_source_filters_source_changed_document_pointers(tmp_path) -> None:
    rag = tmp_path / "rag"
    documents_dir = rag / "documents"
    _write_document_pointer(
        documents_dir / "stale-deck.md",
        index_status="source_changed",
        body="needledeck stale body",
    )
    _write_document_pointer(
        documents_dir / "fresh-deck.md",
        index_status="synced",
        body="needledeck fresh body",
    )

    hits = RipgrepSource([documents_dir], rag_dirs=[rag]).search("needledeck", limit=10)

    assert [Path(hit.doc_id).name for hit in hits] == ["fresh-deck.md"]


def test_ripgrep_source_can_include_source_changed_document_pointers(tmp_path) -> None:
    rag = tmp_path / "rag"
    documents_dir = rag / "documents"
    _write_document_pointer(
        documents_dir / "stale-deck.md",
        index_status="source_changed",
        body="needledeck stale body",
    )

    hits = RipgrepSource(
        [documents_dir],
        rag_dirs=[rag],
        include_stale_documents=True,
    ).search("needledeck", limit=10)

    assert [Path(hit.doc_id).name for hit in hits] == ["stale-deck.md"]
    assert hits[0].payload["index_status"] == "source_changed"
    assert hits[0].payload["stale_source_warning"] == "source_changed"


def test_graph_source_reads_rebuildable_cache(tmp_path) -> None:
    cache_dir = tmp_path / "graph"
    cache_dir.mkdir()
    (cache_dir / "entities.jsonl").write_text(
        '{"id": "RRF", "tier": 1, "inbound_count": 12}\n' '{"id": "unrelated", "tier": 3, "inbound_count": 1}\n',
        encoding="utf-8",
    )
    (cache_dir / "edges.jsonl").write_text(
        '{"src": "hybrid-search.md", "dst": "RRF", "type": "mentions"}\n',
        encoding="utf-8",
    )

    src = GraphSource(cache_dir)

    assert isinstance(src, RetrieverSource)
    assert src.name == "graph"
    hits = src.search("RRF", limit=10)
    assert [hit.rank for hit in hits] == [1, 2]
    assert hits[0].doc_id == "RRF"
    assert hits[0].payload["graph_kind"] == "entity"
    assert hits[1].doc_id == "hybrid-search.md"


def test_graph_source_absent_cache_returns_empty(tmp_path) -> None:
    assert GraphSource(tmp_path / "missing").search("RRF", limit=10) == []
