---
status: Implemented
date: '2026-04-02'
deciders:
  - Core team
related:
  - ADR-033
  - ADR-127
  - ADR-137
hub: adaptive
tags:
  - rag
  - bm25
  - contextual-retrieval
  - search
  - ollama
superseded_by: null
---

# ADR-525: Hybrid BM25 + Contextual Retrieval for RAG Search

## Context

Augur's RAG search pipeline (ADR-127) relies on ripgrep as the sole retrieval layer. While ripgrep excels at exact keyword matching across human-readable markdown indexes, it fundamentally cannot handle:

1. **Natural language queries** — "how do I configure notifications" returns nothing because ripgrep looks for literal substrings, not semantic matches against skill names like `channels` or `attention`.
2. **Synonym and concept matching** — "schedule recurring tasks" doesn't match `daemon` or `schedule` skill content because the query terms don't appear verbatim in the indexed files.
3. **Term frequency ranking** — ripgrep returns results in file-order, not relevance-order. A file mentioning "search" once ranks equally with one that's entirely about search.

Quality baseline measurement confirmed this: **ripgrep-only scored 4/20 (20%)** on a standardized 20-query benchmark covering natural language, technical, and exact-match categories.

The Anthropic Contextual Retrieval paper demonstrates that BM25 sparse retrieval combined with contextual chunk enrichment significantly improves recall without requiring vector embeddings — aligning with Augur's Unix-philosophy commitment to human-readable, text-based indexes (ADR-004, ADR-127).

## Decision

### 1. BM25 Sparse Index (`skills/rag/scripts/bm25_index.py`)

A pure-Python BM25 implementation using the Okapi BM25 scoring formula. The index:
- Builds from chunk data produced by the unified indexer
- Stores as JSON in `{rag_dir}/_meta/bm25_index.json` (human-readable, no binary formats)
- Supports `query(text, top_k)` returning ranked results with BM25 scores
- Uses a shared tokenizer (`src/lib/tokenizer.py`) for consistent text processing

### 2. Reciprocal Rank Fusion (`skills/rag/scripts/retrieval.py`)

Hybrid search merges ripgrep (lexical) and BM25 (sparse) results using RRF:
- `RRF_score(doc) = SUM(1 / (k + rank))` for each source containing the doc
- Smoothing constant `k=60` (per the original RRF paper)
- Results from both sources are deduplicated by path and merged into a single ranking
- The `hybrid_search()` function is the public API consumed by `RAGSearchEngine`

### 3. Contextual Chunk Enrichment (`skills/rag/scripts/contextualizer.py`)

Optional LLM-powered enrichment via local Ollama (Qwen 3.5 9B):
- Each chunk gets a 1-2 sentence context prefix situating it within its source document
- Context is stored in the chunk's YAML frontmatter (`context:` field) and prepended to the body
- Checksum-based caching (MD5 of chunk text) avoids reprocessing unchanged chunks
- Circuit breaker (3 failures, 300s cooldown) for graceful degradation
- `think: false` flag required for Qwen 3.5 to prevent thinking-mode token exhaustion
- 120s connect/read timeout to accommodate cold model loads

### 4. Auto-Start Ollama (`unified_indexer.py`)

The unified indexer auto-starts Ollama via `OllamaChecker.try_start()` if the server isn't running, eliminating manual `ollama serve` as a prerequisite.

### 5. Incremental Contextualization (`--max-chunks N`)

CLI flag to limit contextualization to N chunks per run, enabling incremental enrichment across multiple sessions instead of requiring a single multi-hour run.

### 6. Search Engine Integration (`skills/rag/scripts/search_engine.py`)

`RAGSearchEngine` now accepts an optional `bm25_index` parameter:
- When BM25 is available: runs hybrid retrieval (ripgrep + BM25 via RRF), then optional LLM reranking
- When BM25 is unavailable: falls back to ripgrep-only path (unchanged behavior)
- BM25 index is loaded with mtime-based caching in the MCP tool layer to avoid cold-load per query

## Consequences

### Positive

- Search quality improved from **20% to 90%** on the 20-query benchmark (+70 percentage points)
- Natural language queries now work — "how do I configure notifications" correctly finds `channels` and `attention` skills
- No binary dependencies — BM25 index is plain JSON, contextual enrichment uses local Ollama
- Fully backward compatible — ripgrep-only path unchanged when BM25 index doesn't exist
- Incremental contextualization via `--max-chunks` makes enrichment practical for large knowledge bases

### Negative

- Full contextualization of ~8,500 chunks takes 12-24 hours (one-time, cached thereafter)
- BM25 index adds ~2-5MB to `{rag_dir}/_meta/` (acceptable for the quality improvement)
- Ollama dependency for contextual enrichment (optional — search works without it)

### Neutral

- Existing ripgrep search path is untouched — no regression risk
- BM25 index rebuilds automatically during reindex — no separate maintenance
- Circuit breaker pattern already used elsewhere in the codebase (consistent)

## Implementation Order

1. **Phase 1** (Complete): Shared tokenizer (`src/lib/tokenizer.py`)
2. **Phase 2** (Complete): BM25 index builder and query engine
3. **Phase 3** (Complete): Content-aware chunking strategies
4. **Phase 4** (Complete): Hybrid retrieval with RRF merge
5. **Phase 5** (Complete): Contextualizer with Ollama integration
6. **Phase 6** (Complete): Unified indexer integration + auto-start + `--max-chunks`
7. **Phase 7** (Complete): Quality baseline measurement (20% → 90%)

## Alternatives Considered

### Alternative 1: Vector Embeddings (FAISS/ChromaDB)

Rejected. Introduces binary database dependencies, violates ADR-004/ADR-127 human-readable principle. Requires embedding model management. BM25 achieves 90% hit rate without embeddings.

### Alternative 2: Ollama-Only Reranking (No BM25)

Rejected. Would make every search query depend on Ollama availability and add 5-15s latency per query. BM25 provides fast, deterministic ranking without LLM dependency. Ollama reranking is available as an optional Layer 3 when the LLM client is configured.

### Alternative 3: External Search Service (Elasticsearch/Meilisearch)

Rejected. Adds infrastructure dependency incompatible with local-first architecture. BM25 in pure Python with JSON storage requires zero external services.

## References

- [ADR-033: RAG Search Hardening](ADR-033-rag-search-hardening.md)
- [ADR-127: Human-Readable RAG Indexing](ADR-127-human-readable-rag-indexing.md)
- [ADR-137: Eliminate Direct LLM Calls](ADR-137-eliminate-direct-llm-calls.md)
- [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — inspiration for the contextual enrichment approach
- [Reciprocal Rank Fusion paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) — RRF merge algorithm

## Files Changed

```yaml
files:
  created:
    - skills/rag/scripts/bm25_index.py
    - skills/rag/scripts/retrieval.py
    - skills/rag/scripts/contextualizer.py
    - skills/rag/scripts/_circuit_breaker.py
    - skills/rag/assets/seeds/quality_baseline.yaml
    - src/lib/tokenizer.py
  modified:
    - skills/rag/scripts/unified_indexer.py
    - skills/rag/scripts/search_engine.py
    - skills/rag/scripts/mcp/rag_tools.py
```
