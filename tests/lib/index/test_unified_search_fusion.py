"""Tests for unified_search RRF integration (ADR-739)."""

from __future__ import annotations

import json
from pathlib import Path

from src.lib.index import unified_search
from src.lib.index.rrf import RankedHit


def test_fuse_results_uses_rrf_and_carries_provenance() -> None:
    ranked = {
        "ripgrep": [RankedHit("doc-A", 1, 9.0), RankedHit("doc-B", 2, 8.0)],
        "bm25": [RankedHit("doc-A", 1, 0.9)],
    }

    fused = unified_search.fuse_results(ranked, budget="conservative")

    assert fused[0]["doc_id"] == "doc-A"
    assert fused[0]["budget"] == "conservative"
    assert "score" in fused[0] and "provenance" in fused[0]
    assert len(fused) <= 5


def _stub_gate(monkeypatch) -> None:
    """Keep unit tests off the real staleness gate (it runs a real inline sync)."""
    from src.lib.index import staleness

    monkeypatch.setattr(
        staleness,
        "ensure_fresh_index",
        lambda *a, **k: {"stale": False, "synced": False, "warning": None},
    )


def test_unified_rag_search_still_returns_target_and_results(monkeypatch) -> None:
    _stub_gate(monkeypatch)
    out = json.loads(unified_search.unified_rag_search({"query": "augur"}))

    assert "target" in out and "results" in out
    assert isinstance(out["results"], list)


def test_iterative_search_without_rag_dirs_does_not_query_global_graph(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "memory"
    source.mkdir()
    (source / "MEMORY.md").write_text("needle local memory\n", encoding="utf-8")

    from src.lib.index.sources import GraphSource

    calls = {"count": 0}

    def count_if_called(self, query: str, *, limit: int):  # noqa: ANN001
        calls["count"] += 1
        return []

    monkeypatch.setattr(GraphSource, "search", count_if_called)

    results = unified_search.iterative_search(
        "needle",
        [source],
        [],
        [],
        top_k=5,
    )

    hits = [hit for group in results for hit in group["hits"]]
    assert any(hit["file"].endswith("MEMORY.md") for hit in hits)
    assert calls["count"] == 0


def test_rg_pattern_omits_stopwords_from_natural_language_queries() -> None:
    pattern = unified_search._to_rg_pattern("pitch slide I am working on")

    assert "pitch" in pattern
    assert "slide" in pattern
    assert "working" in pattern
    assert "|I|" not in pattern
    assert "am" not in pattern
    assert "on" not in pattern


def test_document_query_searches_rag_documents_before_catalog_noise(tmp_path: Path) -> None:
    rag = tmp_path / "rag"
    for index in range(60):
        path = rag / "adrs" / f"adr-{index:03}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pitch slide working catalog noise\n", encoding="utf-8")

    deck = rag / "documents" / "venture-augur" / "augur-angel-deck-v20.md"
    deck.parent.mkdir(parents=True, exist_ok=True)
    deck.write_text(
        "---\n"
        "name: augur-angel-deck-v20\n"
        "modified: '2026-05-18T06:59:20+00:00'\n"
        "---\n"
        "pitch slide working deck\n",
        encoding="utf-8",
    )

    results = unified_search.iterative_search(
        "pitch slide I am working on",
        [],
        [],
        [rag],
        top_k=5,
    )

    hits = [hit for group in results for hit in group["hits"]]
    assert any("augur-angel-deck-v20" in hit["file"] for hit in hits[:3])


class _FakeBM25:
    def __init__(self, results: list[dict]) -> None:
        self.results = results

    def query(self, query: str, top_k: int = 50) -> list[dict]:
        return self.results[:top_k]


def test_iterative_search_filters_stale_bm25_documents_on_live_path(monkeypatch) -> None:
    monkeypatch.setattr(
        unified_search,
        "_load_bm25_cached",
        lambda _rag_dirs: _FakeBM25(
            [
                {
                    "path": "chunks/documents/stale/chunk.md",
                    "score": 10.0,
                    "meta": {
                        "category": "documents",
                        "source": "Stale Deck",
                        "index_status": "source_changed",
                    },
                },
                {
                    "path": "chunks/documents/fresh/chunk.md",
                    "score": 9.0,
                    "meta": {
                        "category": "documents",
                        "source": "Fresh Deck",
                        "index_status": "synced",
                    },
                },
            ]
        ),
    )

    results = unified_search.iterative_search(
        "deck",
        [],
        [],
        [],
        top_k=5,
    )

    hits = [hit for group in results for hit in group["hits"]]
    assert [hit["source"] for hit in hits] == ["Fresh Deck"]


def test_iterative_search_filters_stale_ripgrep_document_pointers(tmp_path: Path) -> None:
    rag = tmp_path / "rag"
    documents_dir = rag / "documents"
    documents_dir.mkdir(parents=True)
    (documents_dir / "stale-deck.md").write_text(
        "---\n" "category: documents\n" "index_status: source_changed\n" "---\n" "needledeck stale body\n",
        encoding="utf-8",
    )
    (documents_dir / "fresh-deck.md").write_text(
        "---\n" "category: documents\n" "index_status: synced\n" "---\n" "needledeck fresh body\n",
        encoding="utf-8",
    )

    results = unified_search.iterative_search(
        "needledeck document",
        [],
        [],
        [rag],
        top_k=10,
    )

    hits = [hit for group in results for hit in group["hits"]]
    hit_names = [Path(hit["file"]).name for hit in hits]
    assert "fresh-deck.md" in hit_names
    assert "stale-deck.md" not in hit_names


def test_iterative_search_can_include_stale_ripgrep_document_pointers(tmp_path: Path) -> None:
    rag = tmp_path / "rag"
    documents_dir = rag / "documents"
    documents_dir.mkdir(parents=True)
    (documents_dir / "stale-deck.md").write_text(
        "---\n" "category: documents\n" "index_status: source_changed\n" "---\n" "needledeck stale body\n",
        encoding="utf-8",
    )

    results = unified_search.iterative_search(
        "needledeck document",
        [],
        [],
        [rag],
        top_k=10,
        include_stale_documents=True,
    )

    hits = [hit for group in results for hit in group["hits"]]
    stale_hit = next(hit for hit in hits if Path(hit["file"]).name == "stale-deck.md")
    assert stale_hit["index_status"] == "source_changed"
    assert stale_hit["stale_source_warning"] == "source_changed"


def test_unified_rag_search_can_include_stale_bm25_documents(monkeypatch, tmp_path: Path) -> None:
    _stub_gate(monkeypatch)
    monkeypatch.setattr(
        unified_search,
        "resolve_scope_paths",
        lambda _project: ([], [], [tmp_path / "rag"], "test"),
    )
    monkeypatch.setattr(
        unified_search,
        "_load_bm25_cached",
        lambda _rag_dirs: _FakeBM25(
            [
                {
                    "path": "chunks/documents/stale/chunk.md",
                    "score": 10.0,
                    "meta": {
                        "category": "documents",
                        "source": "Stale Deck",
                        "index_status": "source_changed",
                        "indexed_revision": "drive-revision-41",
                    },
                }
            ]
        ),
    )

    out = json.loads(unified_search.unified_rag_search({"query": "deck", "include_stale_documents": True}))

    hits = [hit for group in out["results"] for hit in group["hits"]]
    assert hits[0]["source"] == "Stale Deck"
    assert hits[0]["stale_source_warning"] == "source_changed"
    assert hits[0]["indexed_revision"] == "drive-revision-41"
