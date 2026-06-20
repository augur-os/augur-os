---
status: Superseded
date: 2026-04-14
deciders:
- Gur Sannikov
related: []
hub: null
tags: []
superseded_by: ADR-561
---

# ADR-587: Wiki Backlog Worker and Page Quality

## Context

The semantic wiki compiler exists but is not driven as a steady backlog loop. Compilation decisions (write a new page vs. update an existing one, what title and body to use) happen inline in `wiki_compiler.py` with shallow handling. Repeated source clusters create new pages instead of strengthening existing ones, and compiled pages tend to be thin generic excerpts rather than written-through bodies that reflect retained `/ask` outcomes plus source meaning.

The compile backlog itself is implicit: there is no operator-facing surface to inspect "what is pending vs. compiled," and no rate-limited cycle that consumes top-priority items in bounded batches. This makes wiki compounding hard to operate honestly.

This artifact has since been **superseded by ADR-561** (Semantic Wiki Page Compiler). The RAG-backed compile-state model described here — `source-summary`, `wiki_compile_status`, `wiki_targets`, `wiki-compile-*` backlog semantics — was retired. The ADR is recorded here for historical traceability of the design direction at the time.

## Decision

(Historical, not implemented as designed.) Reuse the RAG-backed compile backlog and semantic page compiler rather than adding another registry or queue:

1. Add a small `wiki_compile_worker.py` that consumes top-priority backlog items in rate-limited batches with `/ask`-weighted prioritization (`source_limit`, `page_limit`, short-circuits when backlog is empty).
2. Introduce a `wiki_page_merge.py` resolver so repeated source clusters update existing wiki pages instead of always creating new ones (matches by source path and page-type prefix).
3. Split page writing into a dedicated `wiki_page_writer.py` (`build_page_title`, `build_page_body`) that prefers `/ask` summaries over slug noise and writes structured sections (Current Thesis, What This Page Knows, Source Basis).
4. Surface compile status through MCP tools (`wiki-compile-cycle`, `wiki-compile-status`) and the support pages so the backlog becomes visible.

## Consequences

### Positive (had it shipped)
- Steady, rate-limited compile cycles instead of one-shot manual runs
- Existing pages strengthened by repeated clusters instead of duplicates proliferating
- Compiled pages with real titles and written-through bodies
- Operator-visible backlog state via MCP tools and overview support page

### Negative
- The RAG-backed compile-state model accreted complexity that ADR-561 chose to retire entirely

### Neutral
- ADR superseded; do not extend the `wiki-compile-*` backlog semantics from this design

## Alternatives Considered

### Alternative 1: Add a separate registry/queue for the backlog
Rejected at the time in favor of reusing the existing RAG-backed compile state.

### Alternative 2: Keep all decisions inline in `wiki_compiler.py`
Rejected at the time for poor testability and weak page quality.

## References
- Plan: docs/superpowers/plans/2026-04-14-wiki-backlog-worker-and-page-quality.md
- Superseded by: ADR-561 (Semantic Wiki Page Compiler)
