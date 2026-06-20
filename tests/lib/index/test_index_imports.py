"""Smoke tests for the src.lib.index public API."""

from __future__ import annotations


def test_public_api_importable():
    """11 documented public symbols importable from src.lib.index."""
    from src.lib.index import (  # noqa: F401
        BM25Index,
        RAGSearchEngine,
        count_category_entries,
        enrich_all,
        index_documents,
        index_skills,
        list_category_entries,
        read_index_entry,
        reindex_all,
        reindex_category,
        understand_document,
    )


def test_public_api_origins():
    """Symbols originate in the right submodules."""
    from src.lib.index import (
        BM25Index,
        RAGSearchEngine,
        count_category_entries,
        index_documents,
        index_skills,
        list_category_entries,
        reindex_all,
        understand_document,
    )

    assert understand_document.__module__ == "src.lib.index.document_understanding"
    assert BM25Index.__module__ == "src.lib.index.bm25_index"
    assert RAGSearchEngine.__module__ == "src.lib.index.search_engine"
    assert list_category_entries.__module__ == "src.lib.index.index_reader"
    assert count_category_entries.__module__ == "src.lib.index.index_reader"
    assert index_skills.__module__ == "src.lib.index._scanners_knowledge"
    assert reindex_all.__module__ == "src.lib.index.unified_indexer"
    assert index_documents.__module__ == "src.lib.index.unified_indexer"


def test_submodule_paths_reachable():
    """Submodule access works for callers that bypass __init__ re-exports."""
    from src.lib.index import _indexer_helpers, chunker, symbol_extractor  # noqa: F401
