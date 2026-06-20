from __future__ import annotations

from typing import Any

from src.lib.index.sources import (
    FRESH_DOCUMENT_STATUSES,
    bm25_query_limit,
    document_index_status,
    document_status_is_searchable,
    document_status_warning,
)

__all__ = ["FRESH_DOCUMENT_STATUSES", "RAGSearchEngine"]


class RAGSearchEngine:
    """Simplified RAG search: ripgrep groups plus optional document BM25."""

    def __init__(self, search_func, bm25_index: Any = None):
        self.search_func = search_func
        self._bm25_index = bm25_index

    def _document_hits(
        self,
        query: str,
        top_k: int,
        *,
        include_stale_documents: bool = False,
    ) -> list[dict]:
        if self._bm25_index is None or not query.strip():
            return []

        results = self._bm25_index.query(query, top_k=bm25_query_limit(top_k))
        hits: list[dict] = []
        for result in results:
            meta = result.get("meta", {}) or {}
            category = meta.get("category")
            if category and category != "documents":
                continue

            index_status = document_index_status(meta)
            if not document_status_is_searchable(
                index_status,
                include_stale_documents=include_stale_documents,
            ):
                continue

            hit = {
                "file": result.get("path", ""),
                "content": f"BM25 score: {result.get('score', 0.0):.3f}",
                "score": result.get("score", 0.0),
                "source": meta.get("source", ""),
                "heading": meta.get("heading", ""),
                "hub": meta.get("hub", ""),
                "remote_id": meta.get("remote_id", ""),
                "index_status": index_status,
                "indexed_revision": meta.get("indexed_revision", ""),
            }
            warning = document_status_warning(index_status)
            if warning:
                hit["stale_source_warning"] = warning
            hits.append(hit)
            if len(hits) >= top_k:
                break
        return hits[:top_k]

    def iterative_search(
        self,
        query: str,
        max_rounds: int = 3,
        top_k: int = 10,
        *,
        include_stale_documents: bool = False,
    ) -> list:
        del max_rounds  # Retained for caller compatibility.

        raw_results = self.search_func(query)
        trimmed_results: list[dict] = []
        for group in raw_results:
            if isinstance(group, dict) and "hits" in group:
                trimmed = dict(group)
                trimmed["hits"] = list(group.get("hits", []))[:top_k]
                trimmed_results.append(trimmed)
            else:
                trimmed_results.append(group)

        document_hits = self._document_hits(
            query,
            top_k,
            include_stale_documents=include_stale_documents,
        )
        if document_hits:
            trimmed_results.append({"type": "documents", "hits": document_hits})

        return trimmed_results
