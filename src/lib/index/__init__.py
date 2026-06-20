"""RAG indexing and search library.

Migrated from project-brain/capabilities/skills/rag/scripts/ in Track 1 of the cross-client bundle
architecture migration. The rag bundle's MCP tool surface
(project-brain/capabilities/skills/rag/scripts/mcp/) consumes this library — the bundle no longer
hosts the library code itself.

Public API:
    understand_document(path) -> dict
        Document understanding orchestrator (PDF/DOCX/HTML/etc.).

    reindex_all(...), reindex_category(...), index_documents(...)
        Unified indexer entry points.

    index_skills(...)
        Skill-tier scanner (knowledge category).

    list_category_entries(...), count_category_entries(...), read_index_entry(...)
        RAG index reader API (used by dashboard browse).

    BM25Index, RAGSearchEngine
        Search backbones (consumed by rag's MCP tool surface).

    enrich_all(...)
        Description enrichment for indexed entries.

    unified_rag_search(...), iterative_search(...), resolve_scope_paths(...)
        Cross-bundle ripgrep+BM25 search (rag MCP wrapper and knowledge CLI).
"""

from __future__ import annotations

from src.lib.index.bm25_index import BM25Index
from src.lib.index.document_understanding import understand_document
from src.lib.index.enrich_descriptions import enrich_all
from src.lib.index.index_reader import (
    count_category_entries,
    list_category_entries,
    read_index_entry,
)
from src.lib.index._scanners_knowledge import index_skills
from src.lib.index.search_engine import RAGSearchEngine
from src.lib.index.unified_indexer import (
    index_documents,
    reindex_all,
    reindex_category,
)
from src.lib.index.unified_search import (
    iterative_search,
    resolve_scope_paths,
    unified_rag_search,
)

__all__ = [
    "BM25Index",
    "RAGSearchEngine",
    "count_category_entries",
    "enrich_all",
    "index_documents",
    "index_skills",
    "iterative_search",
    "list_category_entries",
    "read_index_entry",
    "reindex_all",
    "reindex_category",
    "resolve_scope_paths",
    "understand_document",
    "unified_rag_search",
]
