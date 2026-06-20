---
status: Implemented
date: '2026-04-05'
deciders:
  - Core team
related:
  - ADR-004
  - ADR-085
  - ADR-127
  - ADR-525
hub: adaptive
tags:
  - rag
  - knowledge
  - query-compounding
  - llm-wiki
  - index
superseded_by: null
---

# ADR-532: Query Compounding and Content-Oriented Index

## Context

Augur's RAG system (ADR-525) provides strong hybrid retrieval — BM25 + ripgrep with RRF fusion, LLM contextualizer, iterative reranking. However, two structural gaps remain:

1. **Queries are ephemeral.** When `/search` or `/ask` produces a valuable synthesis — connecting multiple ADRs, explaining a cross-cutting pattern, summarizing an architecture decision — that answer vanishes into chat history. The next time the same question (or a related one) is asked, the system re-derives everything from scratch. Knowledge doesn't compound.

2. **LLM navigation is machine-oriented.** The RAG manifest (`_meta/manifest.yaml`) is a flat machine catalog — 8,000+ entries listed by category with no topical organization. When an LLM needs to find relevant pages, it either reads the full manifest (expensive) or relies on BM25/ripgrep (misses conceptual connections). There's no lightweight entry point organized by domain and topic.

Both gaps were identified by comparing the current architecture against Karpathy's "LLM Wiki" pattern (April 2026), which proposes:
- A persistent, compounding wiki where query outputs are filed back as knowledge pages
- A content-oriented `index.md` the LLM reads first on every query to find relevant pages

The full LLM Wiki pattern (synthesized wiki layer, ingest hooks, semantic lint) was evaluated and rejected for Augur due to over-engineering risk — it adds a fourth knowledge tier with significant maintenance burden and LLM dependency. Instead, two lightweight pieces were cherry-picked that deliver concrete value without new infrastructure.

## Decision

### 1. Content-Oriented `index.md` Generation

A new `_generate_index_md()` function in `skills/rag/scripts/unified_indexer.py` generates `{rag_dir}/index.md` at the end of every `reindex_all()` cycle.

**Structure:**
- Organized by hub (Adaptive Engine, Brain, Career, etc.), then by category within each hub
- Each entry: `- **name** — description` (truncated to 120 chars)
- Cross-cutting entries (no hub) grouped under a separate section
- Header includes entry count, category count, and index date

**Properties:**
- **Derived, not synthesized** — generated from existing manifest entries, no LLM dependency
- **Zero maintenance burden** — regenerated on every reindex, never stale
- **LLM-optimized** — an LLM reads this first to find relevant pages, then drills into details
- **Human-readable** — browseable in Obsidian or any markdown viewer

**File:** `{rag_dir}/index.md` (alongside `_meta/manifest.yaml`)

### 2. `save-synthesis` MCP Tool

A new MCP tool that persists valuable search/query syntheses as vault notes under the knowledge skill.

**API:**
```
save-synthesis(query, synthesis, sources?, tags?)
```

**Storage:**
- Path: `knowledge` skill vault at `syntheses/{date}-{query-slug}.md`
- Frontmatter: `type: synthesis`, `query`, `date`, `created`, `sources`, `tags`
- Indexed automatically on next reindex cycle (appears under `vault` category in `index.md`)

**Implementation:**
- `src/mcp/augur_mcp/core/vault_ops.py` — `save_synthesis_impl()` function
- `src/mcp/augur_mcp/core/__init__.py` — tool registration as `save-synthesis`
- Uses existing `write_frontmatter()` and vault security patterns (path traversal prevention)

**Usage pattern:**
- After `/search` or `/ask` produces a valuable answer, call `save-synthesis` to persist it
- The synthesis becomes searchable in future queries via unified search
- Over time, syntheses accumulate as a lightweight knowledge layer without requiring a separate wiki infrastructure

## Consequences

### Positive

- Searches gain a navigable entry point — LLMs find relevant content faster by reading `index.md` first
- Valuable query results persist and compound instead of disappearing into chat history
- No new LLM dependencies — `index.md` is derived from manifest data, `save-synthesis` is a simple vault write
- No new autoloops or maintenance infrastructure
- Compatible with Obsidian graph view (vault notes are markdown with frontmatter)

### Negative

- `index.md` at ~3,600 lines is large — may need truncation or tiered generation as the system grows
- `save-synthesis` requires discipline to call — value depends on actual usage
- Syntheses can become stale if underlying sources change (but they're clearly dated)

### Neutral

- Existing manifest.yaml unchanged — `index.md` is an additional output, not a replacement
- No changes to search retrieval pipeline — `index.md` is for navigation, not ranking
- No changes to BM25 or ripgrep behavior

## Implementation Order

### Phase 1: Content-Oriented Index (completed)

1. Add `_generate_index_md()` to `skills/rag/scripts/unified_indexer.py`
2. Call it at the end of `reindex_all()` after manifest write
3. Verify output against live manifest data

### Phase 2: Save-Synthesis Tool (completed)

1. Add `save_synthesis_impl()` to `src/mcp/augur_mcp/core/vault_ops.py`
2. Register `save-synthesis` tool in `src/mcp/augur_mcp/core/__init__.py`
3. Verify slug generation and path security

## Alternatives Considered

### Alternative 1: Full LLM Wiki Layer

Adopt the complete Karpathy pattern — synthesized wiki pages, ingest hooks that update 10-15 pages per source, semantic lint for contradictions, cross-reference maintenance.

**Rejected because:**
- Adds a fourth knowledge tier (raw → index → wiki → memory) with significant maintenance burden
- Makes LLM a hard dependency for ingest, not just enrichment
- Requires new autoloops (`auto-wiki-freshness`, `auto-wiki-lint`, `auto-wiki-contradiction-check`)
- Risk of stale wiki contradicting raw sources
- 10-50x more tokens per ingest cycle
- Vault bloat risk (recently completed ADR-514 to reduce from 3,371 to 1,600 files)

### Alternative 2: Vector Embedding Index

Replace BM25 with vector embeddings for semantic search, using the index as a retrieval layer.

**Rejected because:**
- Violates ADR-004 (Markdown RAG over Vector Databases)
- Adds binary dependencies (FAISS, Chroma, etc.)
- Not human-readable or git-friendly
- BM25 + ripgrep hybrid already performs well (ADR-525)

### Alternative 3: Do Nothing

Rely on existing manifest.yaml and BM25 for all navigation.

**Rejected because:**
- manifest.yaml is machine-oriented, not content-navigable
- Query results remain ephemeral — repeated synthesis work
- Low-cost improvements available with minimal risk

## References

- [Karpathy LLM Wiki Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — pattern inspiration
- ADR-004: Markdown RAG over Vector Databases
- ADR-085: RAG Three-Tier Index
- ADR-127: Human-Readable RAG Indexing
- ADR-525: Hybrid BM25 + Contextual Retrieval
- ADR-514: Vault Cleanup — Phased Reduction

## Files Affected

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - name: save-synthesis
      type: mcp-tool
      action: added
  patterns_deprecated: []
  files_affected:
    - skills/rag/scripts/unified_indexer.py
    - src/mcp/augur_mcp/core/vault_ops.py
    - src/mcp/augur_mcp/core/__init__.py
```
