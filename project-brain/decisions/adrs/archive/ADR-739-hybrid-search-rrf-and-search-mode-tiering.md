---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-738
  - ADR-742
hub: brain
tags:
  - search
  - retrieval
  - rag
  - rrf
  - token-budget
superseded_by: null
spec_file: 2026-05-14-hybrid-search-rrf-design.md
plan_file: 2026-05-14-hybrid-search-rrf.md
---

# ADR-739: Hybrid Search with Reciprocal Rank Fusion and Search Budget Tiering

## Status

Implemented.

## Context

`unified-search`, `memory-search`, and the `rag` skill currently perform a mix of full-text (ripgrep) and keyword (BM25) retrieval — both lexical; there is no vector retriever. There is no canonical fusion algorithm and no user-facing knob to control retrieval token budget. As context windows for downstream LLM calls grow, retrieval that is "always large" is wasteful; retrieval that is "always small" misses on deep questions.

A reference second-brain implementation (gbrain) using **Reciprocal Rank Fusion (RRF)** to combine multiple ranked retrieval sources achieves benchmarked P@5 49.1% and R@5 97.9% on a 17K-page corpus. RRF is a well-known, public algorithm (`score(d) = Σ 1/(k + rank_i)`), implementable in a few dozen lines.

Separately, the same reference system exposes three named **search budgets** with stated token estimates and cost labels so the user can choose retrieval depth per situation.

## Decision

Adopt RRF as the canonical fusion algorithm across `unified-search`, `memory-search`, and the `rag` skill. Add three named search budgets with token budgets and cost labels. RRF is a pure function over ranked lists — it introduces no index of its own. **No embedded database** (no SQLite-vec, no PGLite, no LanceDB). Augur has no vector retriever today; RRF fuses the lexical sources that exist (ripgrep + BM25) plus the ADR-738 typed graph, and stays provider-agnostic so a vector retriever can be added later as another source via its own ADR.

Concretely:

1. **RRF formula**: `score(doc) = Σ 1/(k + rank_i)` summed across all registered retrieval sources (ripgrep full-text, BM25 keyword, and the ADR-738 typed graph). `k = 60` (literature default; configurable in `config/system/search.yaml`).
2. **Search budgets** declared in `config/system/search.yaml`:
   - `conservative`: top-K=5, ~4K tokens
   - `balanced`: top-K=10, ~10K tokens (default)
   - `tokenmax`: top-K=20, ~20K tokens
3. Budget is selectable via:
   - `unified-search` / `memory-search` `budget` argument
   - dashboard `/browse` semantic search budget picker
   - `aug unified-search --budget <name>` CLI flag
4. **Cost labels** computed from the active LLM tier (`config/system/llm.yaml`) — display only, never enforce a hard cap on the user.
5. Retrieval sources implement a `RetrieverSource` protocol — the extension seam. ADR-739 ships `RipgrepSource`, `BM25Source`, and the ADR-738 cache-backed `GraphSource`; any future vector retriever registers through the same protocol with no refork.
6. New MCP tools: `search-tune` (recommends a budget based on simple heuristics), `search-stats` (returns BM25 index freshness, RRF settings, and budget/cost labels).

## Non-Goals

- No embedded relational/vector database. RRF is pure fusion math over ranked lists; it needs no index of its own.
- No new retrieval provider. RRF fuses the ranked lists Augur's existing retrievers already produce; a vector retriever is a separate future ADR.
- No replacement of `unified-search` callers — RRF is internal to fusion; the surface stays compatible.
- No autonomous budget-switching by Augur. The user (or the active AI client, per Rule #11) picks the budget.

## Consequences

- Fusion math implemented in `src/lib/index/` (beside `unified_search.py` — core retrieval cannot import a skill).
- New `config/system/search.yaml` (schema validated per ADR-733).
- Dashboard browse-page gains a semantic-search budget picker; CLI gains `--budget`.
- `unified-search` results gain explicit `score`, `budget`, and `provenance` fields, which the eval harness (ADR-742) consumes.
- Graph source (ADR-738) plugs into RRF without a fork through the cache-backed `GraphSource`.

## Implementation

- `src/lib/index/rrf.py` implements pure RRF fusion and the `RetrieverSource` protocol.
- `src/lib/index/sources.py` implements `RipgrepSource`, `BM25Source`, and `GraphSource`.
- `src/lib/index/unified_search.py` fuses registered sources through RRF and threads `budget` through the public search path.
- `shared-vault/skills/knowledge/scripts/mcp/rag_search.py`, `tools_memory_core.py`, and the `rag` skill search wrapper expose the budget/result-shape changes.
- `/browse` semantic search exposes the budget picker and renders fused results from the real MCP search tool.

## Related

- ADR-738 (typed graph as a third retrieval source)
- ADR-742 (evals measure precision/recall against captured queries)
- ADR-733 (system config schemas)
