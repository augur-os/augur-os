# Concept-First Wiki Compiler Replacement Design

**Date:** 2026-04-20
**Status:** Review
**Scope:** Breaking replacement of the RAG-backed wiki compile backlog, source-summary page model, and heuristic page candidate compiler with a concept-first LLM wiki compiler.

## Summary

Augur's wiki compiler must stop treating indexed source records as page candidates. A wiki page is not an index entry, a source summary, or a report row. It is a durable synthesis of concepts learned from many inputs.

This design replaces the current RAG-backed compile path with a concept-first compiler modeled on the useful parts of `atomicmemory/llm-wiki-compiler`:

1. discover eligible source material
2. hash sources and compare with compiler state
3. extract meaningful concepts from source content
4. merge extracted concepts across sources
5. write compact concept and query pages
6. resolve wikilinks and backlinks
7. rebuild a small navigable index

The replacement is intentionally breaking. The old RAG-backed compile-state model, source-summary page type, heuristic signal graph, page-candidate path, and `wiki-compile-*` command semantics should be removed or rewritten rather than preserved as compatibility behavior.

## Reference Baseline

The reference implementation reviewed for this design is `atomicmemory/llm-wiki-compiler` at commit `de0b47e88a57a12e0861bd957234934b1cd07921`.

Important reference properties:

- source files are discovered under `sources/`
- source change detection is based on SHA-256 hashes
- LLM extraction produces a small set of concepts per source
- concept pages are written under `wiki/concepts/`
- query outputs are written under `wiki/queries/`
- `index.md` summarizes concept and query pages
- wikilinks are resolved after page generation
- compiler state is explicit and separate from the generated wiki pages

Augur should adopt the architecture, not copy the implementation directly. Augur has different source locations, path helpers, MCP contracts, skill commands, dashboard restrictions, and agent-orchestrated execution rules.

## Superseded Designs

This design supersedes these prior wiki architecture artifacts:

- `docs/superpowers/specs/2026-04-14-llm-wiki-architecture-design.md`
- `docs/superpowers/plans/2026-04-14-rag-backed-wiki-compile-state.md`
- `docs/superpowers/plans/2026-04-14-backlog-driven-wiki-page-compiler.md`
- `docs/superpowers/plans/2026-04-14-wiki-backlog-worker-and-page-quality.md`

Those artifacts were directionally correct that the wiki should become a compiled knowledge layer, but they chose the wrong implementation primitive: RAG entries as compile state and source records as candidate pages. The implementation phase must update or mark these docs as superseded so future agents do not reintroduce the old model.

## Problem

The current compiler can create too many wiki pages because it starts from source inventory rows and then tries to filter after the fact. A full rebuild can produce source-shaped pages, timestamp-shaped pages, and single-source topic wrappers. That is structurally incompatible with a useful wiki.

The core failures are:

- RAG entries double as compiler state.
- `wiki_targets` maps source rows to generated page paths.
- `source-summary` is treated as a first-class page type.
- signal graph and page identity code infer page structure from source names and paths.
- deterministic article sections create wiki-shaped text without first proving a durable concept exists.
- `index.md` and metadata pages can become an inventory of generated files instead of a concept map.

The fix is to change the compiler model, not tune thresholds.

## Product Contract

The compiled wiki should contain:

- stable concept pages
- saved query pages
- compact overview and index pages
- source citations and evidence summaries
- meaningful wikilinks between concepts

The compiled wiki should not contain:

- one page per source file
- one page per RAG entry
- one page per report/event/timestamp unless that event is itself a durable concept
- source inventory mirror pages
- pages created only because a file exists

The expected page count after a full rebuild should be proportional to durable concepts, not source count. Large source collections should strengthen existing concept pages before creating new pages.

## Non-Goals

- Do not build a second raw-source mirror inside the wiki.
- Do not keep the old source-summary model as a fallback.
- Do not use dashboard code to call LLM APIs directly.
- Do not keep compatibility aliases for broken command semantics.
- Do not hide old behavior behind stricter filters.
- Do not make RAG responsible for deciding which wiki pages exist.

## Target Architecture

### 1. Source Inventory

The source inventory discovers eligible material from Augur's existing knowledge surfaces:

- retained `/ask` outcomes
- syntheses
- vault notes
- documents and extracted document text
- skills, commands, actions, and integrations
- ADRs and project docs when relevant

The inventory returns source descriptors:

- stable source id
- source kind
- source path or URI
- title
- body text or body loader
- checksum
- modified time
- priority metadata

The inventory must exclude generated wiki pages by default. The compiler can read existing wiki pages for context, but wiki pages must not become new source records for page creation.

RAG can help discover and search source material, but RAG metadata is not compiler state.

### 2. Compiler State

Compiler state lives outside the repo and outside user-authored wiki pages, under `get_runtime_dir()/wiki/`.

State should track:

- source id
- source checksum
- source title and kind
- extracted concepts for that source
- concept slugs associated with each source
- last extraction time
- last page generation time
- deleted source handling
- frozen slugs for concepts that still have live sources
- compiler version

This state replaces these RAG frontmatter fields:

- `wiki_compile_status`
- `wiki_compiled_at`
- `wiki_compiled_checksum`
- `wiki_targets`

The implementation should provide a migration cleanup that removes or ignores those fields. RAG reindexing should not preserve wiki compile metadata after the new compiler state exists.

### 3. Concept Extraction

Concept extraction is the LLM-heavy step. For each new or changed source, the orchestrator asks for a small number of meaningful concepts, not source summaries.

Each extracted concept should include:

- title
- slug
- short summary
- evidence snippets or citations
- source id
- confidence
- optional aliases
- optional related concept hints

Extraction guidance should mirror the reference compiler's most important behavior: extract a bounded set of standalone concepts, usually 3-8 per meaningful source, and ignore trivial details.

If a source does not contain durable knowledge, extraction should return no concepts. The compiler should mark the source as processed in compiler state without creating a wiki page.

### 4. Concept Merge

The merge step groups extracted concepts by durable identity before page writing.

Merge inputs:

- slug match
- normalized title match
- alias match
- strong semantic similarity when available
- existing concept page frontmatter
- source overlap

Merge output:

- canonical concept slug
- canonical title
- source ids
- evidence groups
- aliases
- related concepts
- stale or removed source markers

Creating a new page should require a merged concept that is meaningful after cross-source merge. Single-source concepts are allowed only when the source is high value and the concept is durable, not merely because the source exists.

### 5. Page Generation

The page generator writes concept and query pages only.

Primary paths:

- `concepts/<slug>.md`
- `queries/<slug>.md`

Allowed support pages:

- `index.md`
- `overview.md`
- `log.md` if needed for maintenance chronology

Concept page frontmatter should include:

- `title`
- `page_type: concept`
- `summary`
- `sources`
- `aliases`
- `related`
- `created`
- `updated`
- `compiler_version`

Query page frontmatter should include:

- `title`
- `page_type: query`
- `query`
- `summary`
- `sources`
- `related`
- `created`
- `updated`

The body should be authored synthesis with citations, not a mechanical table of source entries.

### 6. Wikilink Resolver

After pages are generated, a resolver builds a title and alias index, then resolves internal links.

It should detect:

- broken wikilinks
- duplicate concept titles
- duplicate aliases
- orphaned concept pages
- missing reciprocal links when a strong relationship exists
- stale links to deleted or renamed concepts

Lint should fail for broken internal links and duplicate concept identities.

### 7. Index Builder

The index builder writes a compact concept/query index.

It should include:

- total concept and query counts
- recently updated pages
- concept groups or alphabetical sections
- saved queries
- lint status summary

It should not include every source, every RAG entry, every generated metadata file, or every low-level page as an inventory row.

### 8. Query Compounding

Retained `/ask` outcomes are high-priority source material.

They can:

- strengthen an existing concept
- create a saved query page
- create a new concept when repeated or clearly durable
- add a contradiction or open question to an existing concept

`/ask` results should feed the compiler as structured source records. They should not directly append raw answer text into wiki pages without the concept merge and page generation steps.

## Agent-Orchestrated Execution

Augur's workflow rule is that agents perform judgment and orchestration while MCP tools perform atomic operations. The new wiki compiler should follow that split.

Deterministic Python/MCP responsibilities:

- discover source descriptors
- read source bodies
- read and write compiler state
- acquire compiler lock
- write page files with frontmatter
- run wikilink resolution
- lint wiki structure
- reindex generated wiki pages into RAG/search
- report status

Agent responsibilities:

- decide extraction and generation prompts
- perform LLM concept extraction
- merge ambiguous concepts when deterministic merge is insufficient
- write synthesized page prose
- decide whether a borderline concept is durable enough

Dashboard actions must dispatch wiki rebuild/update work to an IDE/CLI agent. The dashboard must not call LLM APIs directly.

If no agent LLM execution surface is available, rebuild/update should fail clearly. It must not silently fall back to source-summary page generation.

## Command Contract

The command surface should become:

- `wiki-status`: report page counts, compiler state counts, pending changed sources, and lint summary
- `wiki-reindex`: index existing wiki pages only
- `wiki-lint`: validate concept schema, links, duplicates, source refs, and stale state
- `wiki-purge`: delete compiled wiki pages plus compiler state when requested
- `wiki-rebuild`: run a full concept-first compile from current sources
- `wiki-update`: run an incremental concept-first compile for new and changed sources
- `wiki-reset`: purge, rebuild, reindex, and lint

Old `wiki-compile-*` tools should be removed or replaced with the new semantics. There should be no command that means "turn top RAG backlog rows into wiki pages."

## Cleanup Scope

The implementation must remove or rewrite every active dependency on the old compiler model.

Known cleanup targets:

- `skills/ingest/scripts/wiki_compile_backlog.py`
- `skills/ingest/scripts/wiki_page_candidates.py`
- `skills/ingest/scripts/wiki_page_identity.py`
- `skills/ingest/scripts/wiki_signal_graph.py`
- `skills/ingest/scripts/wiki_article_sections.py`
- legacy functions in `skills/ingest/scripts/wiki_compiler.py`
- old `wiki-compile-*` registrations in `skills/ingest/scripts/mcp/wiki_tools.py`
- `source-summary` entries in wiki schema seeds
- RAG preservation of wiki compile fields in `skills/rag/scripts/_indexer_helpers.py`
- tests that assert `wiki_compile_status`, `wiki_targets`, or `source-summary`
- generated skill command docs that advertise old behavior
- review/spec/plan docs that present RAG-backed compile state as current design

Before deleting any module, the implementer must follow the repository deletion rule:

1. run `git log --oneline -5 -- <file>`
2. inspect any referenced ADR
3. state whether the new ADR supersedes that decision
4. delete only after confirming no current caller remains

The cleanup is not complete until `rg` shows no active references to removed semantics outside archived/superseded documentation.

## Migration

The migration should be explicit:

1. write and accept an ADR superseding the RAG-backed compiler design
2. add new compiler state under `get_runtime_dir()/wiki/`
3. remove source-summary pages from generated wiki output
4. strip or ignore legacy RAG wiki compile fields
5. replace command registrations and skill docs
6. rebuild the wiki from current sources using the concept compiler
7. reindex generated wiki pages
8. lint the final wiki

Existing generated wiki pages can be purged during `wiki-reset`. User-authored source material must not be deleted.

## Testing Strategy

Unit tests:

- source inventory excludes generated wiki pages
- source hashing detects new, changed, unchanged, and deleted sources
- compiler state persists source-to-concept extraction records
- extraction result validation rejects missing title/slug/source evidence
- concept merge deduplicates aliases and source evidence
- page writer writes concept/query frontmatter only
- link resolver detects broken links and duplicate titles
- index builder excludes source inventory rows
- lint fails on source-summary pages
- RAG indexer no longer preserves wiki compile metadata

Integration tests:

- full fake-LLM rebuild from fixture sources produces a small concept set
- incremental fake-LLM update rewrites affected concepts only
- deleted source does not delete a concept still supported by other sources
- `wiki-reset` purges legacy pages/state and rebuilds concept pages
- `wiki-reindex` does not create pages
- old `wiki-compile-*` tools are absent or map to new documented semantics

Repository audits:

- `rg "source-summary" docs skills -g '*.py' -g '*.md' -g '*.yaml'`
- `rg "wiki_compile_status|wiki_compiled|wiki_targets" docs skills -g '*.py' -g '*.md' -g '*.yaml'`
- `rg "wiki-compile-" docs skills -g '*.py' -g '*.md' -g '*.yaml'`

Expected result: only superseded historical docs may mention removed terms, and those docs must clearly say they are superseded.

Live verification:

- run `wiki-reset`
- confirm page count is concept-sized, not source-sized
- run `wiki-lint`
- run `wiki-reindex`
- inspect `wiki/index.md`
- verify no `sources/` source-summary output exists
- verify RAG search can find generated concept pages

## Success Criteria

The fix is complete when:

- a full rebuild no longer creates source inventory pages
- page count is driven by merged concepts, not source count
- `source-summary` is not an active page type
- RAG entries do not own wiki compile state
- old `wiki-compile-*` backlog semantics are gone
- `wiki-reset` uses the concept compiler
- `wiki-reindex` remains index-only
- lint catches duplicate concepts, broken links, stale source refs, and legacy page types
- docs, skill surfaces, and tests describe the new architecture only

## Implementation Boundaries

Keep useful infrastructure where it still matches the target:

- path helpers from `src.config.paths`
- frontmatter utilities
- wiki page file read/write primitives after schema changes
- RAG indexing of generated wiki pages
- document extraction and source discovery
- MCP tool registration patterns

Remove code whose only purpose is the old compiler model.

The final implementation should make the wrong architecture hard to reintroduce. Tests should fail if a future change recreates source-summary pages, writes compile state into RAG frontmatter, or turns source inventory rows directly into wiki pages.
