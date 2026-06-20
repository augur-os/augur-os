from __future__ import annotations

from src.lib.index.search_engine import RAGSearchEngine


class FakeBM25:
    def __init__(self, results):
        self.results = results
        self.requested_top_k = None

    def query(self, query: str, top_k: int):
        self.requested_top_k = top_k
        return self.results[:top_k]


def _document_hits(groups: list[dict]) -> list[dict]:
    return [hit for group in groups if group.get("type") == "documents" for hit in group["hits"]]


def test_document_bm25_excludes_stale_chunks_by_default():
    engine = RAGSearchEngine(
        lambda query: [],
        bm25_index=FakeBM25(
            [
                {
                    "path": "chunks/documents/stale/chunk.md",
                    "text": "stale",
                    "score": 10.0,
                    "meta": {
                        "category": "documents",
                        "source": "Stale Deck",
                        "index_status": "source_changed",
                        "remote_id": "google-drive:file:stale",
                    },
                },
                {
                    "path": "chunks/documents/blank-status/chunk.md",
                    "text": "fresh blank",
                    "score": 9.0,
                    "meta": {
                        "category": "documents",
                        "source": "Fresh Local Note",
                        "index_status": "",
                        "remote_id": "",
                    },
                },
                {
                    "path": "chunks/documents/fresh/chunk.md",
                    "text": "fresh",
                    "score": 8.0,
                    "meta": {
                        "category": "documents",
                        "source": "Fresh Deck",
                        "index_status": "synced",
                        "remote_id": "google-drive:file:fresh",
                    },
                },
            ]
        ),
    )

    hits = engine.iterative_search("deck", top_k=5)

    document_hits = _document_hits(hits)
    assert [hit["source"] for hit in document_hits] == [
        "Fresh Local Note",
        "Fresh Deck",
    ]
    assert all("stale_source_warning" not in hit for hit in document_hits)


def test_document_bm25_can_include_stale_chunks_when_enabled():
    engine = RAGSearchEngine(
        lambda query: [],
        bm25_index=FakeBM25(
            [
                {
                    "path": "chunks/documents/stale/chunk.md",
                    "text": "stale",
                    "score": 10.0,
                    "meta": {
                        "category": "documents",
                        "source": "Stale Deck",
                        "index_status": "source_changed",
                        "remote_id": "google-drive:file:stale",
                        "indexed_revision": "drive-revision-41",
                    },
                }
            ]
        ),
    )

    hits = engine.iterative_search("deck", top_k=5, include_stale_documents=True)

    document_hits = _document_hits(hits)
    assert document_hits[0]["source"] == "Stale Deck"
    assert document_hits[0]["stale_source_warning"] == "source_changed"
    assert document_hits[0]["remote_id"] == "google-drive:file:stale"
    assert document_hits[0]["index_status"] == "source_changed"
    assert document_hits[0]["indexed_revision"] == "drive-revision-41"


def test_document_bm25_overfetches_so_stale_hits_do_not_hide_fresh_hits():
    bm25 = FakeBM25(
        [
            {
                "path": "chunks/documents/stale/chunk.md",
                "text": "stale",
                "score": 10.0,
                "meta": {
                    "category": "documents",
                    "source": "Stale Deck",
                    "index_status": "source_changed",
                },
            },
            {
                "path": "chunks/documents/fresh/chunk.md",
                "text": "fresh",
                "score": 8.0,
                "meta": {
                    "category": "documents",
                    "source": "Fresh Deck",
                    "index_status": "synced",
                },
            },
        ]
    )
    engine = RAGSearchEngine(lambda query: [], bm25_index=bm25)

    hits = engine.iterative_search("deck", top_k=1)

    assert bm25.requested_top_k and bm25.requested_top_k > 1
    document_hits = _document_hits(hits)
    assert [hit["source"] for hit in document_hits] == ["Fresh Deck"]


def test_document_bm25_keeps_summary_stale_chunks_with_warning_by_default():
    engine = RAGSearchEngine(
        lambda query: [],
        bm25_index=FakeBM25(
            [
                {
                    "path": "chunks/documents/summary-stale/chunk.md",
                    "text": "summary stale",
                    "score": 9.0,
                    "meta": {
                        "category": "documents",
                        "source": "Summary Stale Deck",
                        "index_status": "summary_stale",
                    },
                }
            ]
        ),
    )

    hits = engine.iterative_search("deck", top_k=5)

    document_hits = _document_hits(hits)
    assert document_hits[0]["source"] == "Summary Stale Deck"
    assert document_hits[0]["stale_source_warning"] == "summary_stale"


def test_document_bm25_keeps_non_document_filtering_when_stale_enabled():
    engine = RAGSearchEngine(
        lambda query: [],
        bm25_index=FakeBM25(
            [
                {
                    "path": "chunks/skills/rag/chunk.md",
                    "text": "skill hit",
                    "score": 10.0,
                    "meta": {
                        "category": "skills",
                        "source": "RAG Skill",
                        "index_status": "source_changed",
                    },
                },
                {
                    "path": "chunks/documents/deck/chunk.md",
                    "text": "document hit",
                    "score": 8.0,
                    "meta": {
                        "category": "documents",
                        "source": "Fresh Deck",
                        "index_status": "synced",
                    },
                },
            ]
        ),
    )

    hits = engine.iterative_search("deck", top_k=5, include_stale_documents=True)

    document_hits = _document_hits(hits)
    assert [hit["source"] for hit in document_hits] == ["Fresh Deck"]


def test_iterative_search_preserves_max_rounds_and_trims_ripgrep_groups():
    engine = RAGSearchEngine(
        lambda query: [
            {
                "type": "ripgrep",
                "hits": [
                    {"file": "first.md", "content": "deck"},
                    {"file": "second.md", "content": "deck"},
                ],
            }
        ],
        bm25_index=FakeBM25([]),
    )

    hits = engine.iterative_search("deck", max_rounds=1, top_k=1)

    assert hits == [
        {
            "type": "ripgrep",
            "hits": [{"file": "first.md", "content": "deck"}],
        }
    ]
