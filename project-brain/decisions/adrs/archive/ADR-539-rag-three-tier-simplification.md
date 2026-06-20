---
status: Implemented
date: 2026-04-07
deciders:
  - gsannikov
related:
  - ADR-127
  - ADR-200
  - ADR-453
hub: brain
tags:
  - rag
  - search
  - wiki
  - karpathy
  - cost-reduction
superseded_by: null
---

# ADR-539: RAG Three-Tier Simplification

## Context

The monolithic RAG pipeline costs ~27% of Claude API quota nightly (1,031 `claude --print` sessions via the contextualizer) for a search path used 11 times across 2,982 sessions. AI clients overwhelmingly prefer native tools (Grep: 10,554 calls, Read: 29,584) over the RAG MCP tool.

The system chunks 9,355 markdown files that are already natively readable, contextualizes each with an LLM call via `claude --print` (because `llm.yaml` has no `active_profile`, so cli_detect auto-selects the Claude CLI), and builds a BM25 index that adds marginal value over ripgrep for markdown content.

Meanwhile, the website claims "AI creates, you curate. Knowledge compounds across every conversation" and "BM25 + ripgrep hybrid, content-aware chunking" -- the first claim is aspirational (no compounding mechanism exists), and the second describes infrastructure that nobody uses.

Karpathy published an [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) that addresses the knowledge compounding problem: a persistent wiki maintained by AI clients during conversations, not a batch indexing pipeline.

## Decision

Replace the monolithic RAG pipeline with a three-tier knowledge system matched to content type.

### Tier 1: Simple (ripgrep on source files)

Categories: skills, vault, scripts, pages, blocks, mcp-tools, api-routes, tests, workflows, prompts, agents, integrations, cli-commands.

Category scanners continue writing index entries (pointer .md files with frontmatter). `index.md` (Karpathy catalog) generated statically. Search uses ripgrep on original source files. No chunking, no BM25, no LLM.

### Tier 2: Extract (document pipeline)

Category: documents. Source: `Au-docs/` (558 PDFs, 60 docx, 28 pptx, 24 xlsx, 28 doc).

Document extractor converts to markdown. Content chunked (~1500 tokens, heading-aware). BM25 index built over document chunks only. Search uses BM25 + ripgrep on extracted text. No LLM contextualization.

### Tier 3: Wiki (Karpathy LLM Wiki pattern) -- Phase 2

Categories: adrs, memory, logs, docs, sessions. Output: `Au-vault/wiki/`.

No batch pipeline. AI clients maintain the wiki during normal conversations using a schema prompt adapted from Karpathy's gist. Wiki pages live in the vault (git-tracked) and serve as cross-client shared memory.

### Phase 1 Changes (this ADR)

**Delete:**
- `contextualizer.py` -- 1,031 Claude calls/night
- `_circuit_breaker.py` -- only used by contextualizer
- `retrieval.py` -- RRF merge no longer needed
- `ops/enrich_metadata.py` -- no markdown chunks to enrich
- Markdown chunking in `_chunk_all()` -- restrict `_CHUNK_CATEGORIES` to `{"documents"}` only
- LLM evaluation/ranking in `search_engine.py`
- `contextualize` parameter from `reindex_all()` and all callers
- `auto-enrich-metadata` auto-command from `rag/SKILL.md`

**Modify:**
- `unified_indexer.py` -- documents-only chunking + BM25
- `search_engine.py` -- ripgrep + optional document BM25, no LLM
- `mcp/rag_tools.py` -- simplified search dispatch
- `llm.yaml` -- add `active_profile: local` as safety net
- `rag/SKILL.md` -- update description

**Cleanup (runtime):**
- Delete `rag/chunks/` except `chunks/documents/`
- Delete `rag/_meta/bm25_index.json` (rebuild for documents only)
- Delete `state/adaptive/rag_context_cache.json`

### Phase 2 Components (separate ADR)

- `Au-vault/wiki/` directory with `index.md`, `log.md`, `overview.md`
- Wiki schema prompt in CLAUDE.md/AGENTS.md/CODEX.md
- Wiki dashboard tab in browse page
- Session learning hooks for knowledge compounding
- `/wiki lint` command

### Wiki as Cross-Client Memory

Per-client memory (`.claude/memory/`, Codex memory) remains as short-term scratch. The wiki becomes the shared long-term knowledge layer across all AI clients. Each client writes to `Au-vault/wiki/` during conversations. The vault is already accessible to all clients.

### Strategy Router

Categories mapped to tiers in config:

```yaml
strategies:
  simple:    [skills, vault, scripts, pages, blocks, mcp-tools,
              api-routes, tests, workflows, prompts, agents,
              integrations, cli-commands]
  extract:   [documents]
  wiki:      [adrs, memory, logs, docs, sessions]
```

### Website Messaging

Update `Au-docs/venture-augur/website-working/index.html`:
- Comparison table RAG row: "Three-tier: ripgrep for code, BM25 for documents, LLM Wiki for compiled knowledge"
- Architecture tag: "LLM Wiki + document search" (was "Plain text RAG")
- Add Karpathy wiki paragraph to knowledge section
- Skills description: "A living wiki compiles your knowledge" (was "RAG indexes connect everything")

## Consequences

### Positive

- Nightly cost drops from ~27% quota to $0
- Chunk files drop from 9,355 to ~150 (documents only)
- Codebase simplified: delete contextualizer, circuit breaker, retrieval module, enrich-metadata
- Search quality unchanged or better for markdown (ripgrep on originals is faster and more precise)
- "Knowledge compounds across every conversation" becomes a real mechanism via wiki tier
- Wiki pages are git-tracked, portable, version-controlled
- Cross-client memory problem solved by wiki in vault

### Negative

- No BM25 ranking for markdown content (ripgrep is keyword-only, no relevance scoring)
- Wiki tier (Phase 2) requires schema prompt design and session hooks -- not trivial
- Initial wiki seeding from 394 ADRs needs a dedicated session

### Neutral

- Document search (Tier 2) is unchanged from current behavior minus LLM contextualization
- Category scanners and index.md generation are unchanged
- `/search` command continues to work, with simplified backend

## Alternatives Considered

### Alternative 1: Keep BM25 for all content, drop only contextualization

Removes the expensive LLM calls but keeps 9,355 chunk files and the BM25 index for markdown. Rejected because BM25 over copies of greppable markdown adds complexity for marginal benefit (11 total searches vs 10,554 Grep calls).

### Alternative 2: Invest in RAG -- make AI clients use it

Inject `search-skill-knowledge` into CLAUDE.md, add system prompts directing clients to search before grepping. Rejected because it fights how AI clients naturally work -- they prefer Grep/Read because it's direct. Forcing them through RAG adds latency and indirection.

### Alternative 3: Full Karpathy wiki for all content (no tiers)

Use wiki for everything, including binary documents. Rejected because PDFs need extraction + chunking -- you can't wiki-summarize a 200-page contract in one conversation. Binary documents genuinely need the extract pipeline.

## References

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki) (reference implementation)
- ADR-127: Hybrid retrieval architecture (superseded by this ADR for markdown content)
- ADR-200: Knowledge enrichment loop decomposition
- ADR-453: MCP-direct data fetching
- Spec: `docs/superpowers/specs/2026-04-07-rag-simplification-design.md`
- Plan: `docs/superpowers/plans/2026-04-07-rag-simplification.md`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - search-skill-knowledge MCP tool: simplified return shape (no RRF scores, adds 'documents' result type)
  patterns_deprecated:
    - contextualizer.py LLM enrichment pattern
    - hybrid_search / RRF merge pattern
    - _circuit_breaker.py pattern in search path
    - contextualize parameter in reindex_all()
  files_affected:
    - skills/rag/scripts/unified_indexer.py
    - skills/rag/scripts/search_engine.py
    - skills/rag/scripts/retrieval.py (deleted)
    - skills/rag/scripts/contextualizer.py (deleted)
    - skills/rag/scripts/_circuit_breaker.py (deleted)
    - skills/rag/scripts/ops/enrich_metadata.py (deleted)
    - skills/rag/scripts/mcp/rag_tools.py
    - skills/rag/SKILL.md
    - skills/ai/scripts/ops/rag_reindex.py
    - skills/ai/scripts/ops/project_index.py
    - skills/auto-rag-reindex/scripts/rag_reindex_ops.py
    - llm.yaml
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using the implementation plan.

**Plan file**: `docs/superpowers/plans/2026-04-07-rag-simplification.md`

**Team name**: `adr-539-rag-simplification`

### Phase 1: Safety + Deletion
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | devops | low | Set active_profile: local in llm.yaml | `llm.yaml` |
| 1.2 | developer | low | Delete contextualizer.py, _circuit_breaker.py, remove imports from search_engine.py | `skills/rag/scripts/contextualizer.py`, `skills/rag/scripts/_circuit_breaker.py`, `skills/rag/scripts/search_engine.py` |
| 1.3 | developer | low | Delete enrich_metadata.py, retrieval.py, their tests | `skills/rag/scripts/ops/enrich_metadata.py`, `skills/rag/scripts/retrieval.py` |

### Phase 2: Core Pipeline Change
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Restrict _CHUNK_CATEGORIES to documents only, remove contextualize param | `skills/rag/scripts/unified_indexer.py` |
| 2.2 | developer | medium | Rewrite search_engine.py: ripgrep + document BM25, no LLM | `skills/rag/scripts/search_engine.py` |
| 2.3 | developer | low | Update MCP tool to use new search engine | `skills/rag/scripts/mcp/rag_tools.py` |

### Phase 3: Cleanup + Docs
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Remove contextualize param from all callers | `skills/ai/scripts/ops/rag_reindex.py`, `skills/ai/scripts/ops/project_index.py`, `skills/auto-rag-reindex/scripts/rag_reindex_ops.py` |
| 3.2 | developer | low | Delete stale tests, update remaining tests | `skills/rag/augur/tests/` |
| 3.3 | developer | low | Update SKILL.md description | `skills/rag/SKILL.md` |
| 3.4 | devops | low | Runtime cleanup: delete chunks, caches, rebuild | Runtime state |
| 3.5 | developer | low | Website messaging updates | `Au-docs/venture-augur/website-working/index.html` |

### Completion Criteria
- [ ] `llm.yaml` has `active_profile: local`
- [ ] No `contextualizer.py`, `_circuit_breaker.py`, `retrieval.py`, `enrich_metadata.py` in codebase
- [ ] `_CHUNK_CATEGORIES` is `{"documents"}` only
- [ ] `reindex_all()` has no `contextualize` parameter
- [ ] `search_engine.py` has no LLM imports or calls
- [ ] All RAG tests pass
- [ ] Runtime `chunks/` contains only `documents/` subdirectory
- [ ] `/search reindex` completes with < 500 chunk files
- [ ] Website comparison table updated
- [ ] ADR status updated to Implemented
