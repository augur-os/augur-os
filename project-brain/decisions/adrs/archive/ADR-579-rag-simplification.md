---
status: Implemented
date: 2026-04-07
deciders:
  - Gur Sannikov
related: []
hub: null
tags:
  - rag
  - knowledge
  - cost-reduction
superseded_by: null
---

# ADR-579: RAG Simplification

## Context

The existing RAG pipeline consumed roughly 27% of the Claude API quota nightly (1,031 `claude --print` sessions) for a search path that was actually invoked only 11 times across 2,982 sessions. AI clients overwhelmingly used `Grep` (10,554 calls) and `Read` (29,584 calls) instead. The system chunked 9,355 markdown files that were already natively readable, contextualized each chunk via an LLM call, and built a BM25 index that added marginal value over plain ripgrep.

The pipeline was monolithic: every category (skills, vault, ADRs, scripts, pages, etc.) was chunked, contextualized, and indexed identically. There was no differentiation between content types whose source files are already greppable markdown versus binary documents (PDFs, Office files) where extraction and BM25 are genuinely needed.

The cost was real and the value was marginal. A three-tier knowledge architecture matched to content type would eliminate the waste while preserving the legitimate document-extraction surface.

## Decision

Replace the monolithic RAG pipeline with a three-tier knowledge system, executing Phase 1 (deletion of waste) immediately and deferring Phase 2 (Wiki Tier) to a separate ADR.

- **Tier 1 (Simple):** ripgrep on source files for skills, vault, scripts, pages, blocks, mcp-tools, api-routes, tests, workflows, prompts, agents, integrations, cli-commands. No chunking, no BM25, no LLM.
- **Tier 2 (Extract):** binary document pipeline (PDFs, Office docs, images with OCR). Heading-aware chunking, BM25 over document chunks only, no LLM contextualization.
- **Tier 3 (Wiki):** Karpathy LLM Wiki pattern, maintained by AI clients during conversations. Deferred to separate ADR.

Phase 1 deletes `contextualizer.py`, `_circuit_breaker.py`, `retrieval.py`, and `ops/enrich_metadata.py`; restricts `_CHUNK_CATEGORIES` in `unified_indexer.py` to `{"documents"}`; rewrites `search_engine.py` as a thin ripgrep + document-BM25 wrapper with no LLM ranking; removes the `contextualize` parameter from all callers; sets `active_profile: local` in `llm.yaml` as a safety net; and cleans the runtime chunk directories and BM25 index for a fresh rebuild.

## Consequences

### Positive
- Nightly Claude API cost drops from ~27% of quota to $0.
- Chunk file count drops from 9,355 to under 500 (documents only).
- Search quality preserved: ripgrep on originals is the same or better for markdown; BM25 is unchanged for documents.
- Pipeline simpler and easier to reason about; fewer moving parts to fail.
- Strategy router pattern (categories mapped to tiers in config) makes future tier reassignment a one-line change.

### Negative
- LLM-based reranking and contextual enrichment are removed; queries that relied on synthesized context now get raw matches.
- BM25 over markdown is gone, so any latent value from sparse-index ranking on markdown is lost (offset by ripgrep being preferred in practice).
- Tier 3 (Wiki) is not delivered in this slice; the "compounding knowledge" story remains aspirational until Phase 2.

### Neutral
- Existing skill structure unchanged; only RAG internals shift.
- Document extraction pipeline preserved as-is.
- Runtime cleanup is regeneratable and outside the repo.

## Alternatives Considered

### Alternative 1: Optimize the existing pipeline
Tune contextualization (smaller model, fewer chunks, better caching) instead of deleting it. Rejected because the underlying assumption (that markdown chunks need LLM context) is wrong — AI clients already grep originals, so the chunks add cost without adding consumed value.

### Alternative 2: Defer until Wiki Tier is ready
Ship all three tiers together. Rejected because the cost is bleeding now (27% of quota nightly) and Phase 1 is pure deletion with negligible risk; Phase 2 is a real product change deserving its own ADR.

### Alternative 3: Keep BM25 over markdown, drop only LLM contextualization
Partial deletion. Rejected because BM25 over markdown that ripgrep already covers adds index maintenance cost (rebuilds, cache invalidation, RRF merging) for no measurable retrieval win.

## References
- Plan: docs/superpowers/plans/2026-04-07-rag-simplification.md
- Spec: docs/superpowers/specs/2026-04-07-rag-simplification-design.md
