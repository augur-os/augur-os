---
status: Implemented
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-404
- ADR-478
- ADR-546
- ADR-559
- ADR-560
hub: brain
tags:
- wiki
- compiler
- concepts
- rag
- ask
- llm-wiki
superseded_by: null
implemented_date: '2026-04-20'
implementation_commits:
- 'da905960d9 docs(wiki): mark rag-backed compiler plans superseded'
- '9c99dc9f5a feat(wiki): add concept compiler models'
- 'c761fa063a fix(wiki): validate concept model payloads'
- '9cdbd1b8a0 feat(wiki): add concept compiler runtime state'
- '16a85807e7 fix(wiki): validate compiler state payloads'
- '7132f5bc64 fix(wiki): reject malformed compiler state'
- '8f1af4f23f feat(wiki): add concept source inventory'
- '7f1e4f1fca fix(wiki): harden source inventory exclusions'
- '8fe84f014f fix(wiki): repair source inventory title fallback'
- 'a52787621f feat(wiki): add concept extraction contract'
- '3e0d59b789 fix(wiki): reject non-finite extraction confidence'
- 'fb6b235999 feat(wiki): merge extracted concepts before page writes'
- '19b2feeea9 fix(wiki): normalize merged concept slugs'
- '8cd2792dbd feat(wiki): write concept pages and compact index'
- 'b0072f7466 fix(wiki): prioritize concept schema resolution'
- '59593d7598 feat(wiki): lint concept links and legacy page types'
- '2887840951 fix(wiki): fail lint on ambiguous concept aliases'
- '59cd49b382 fix(wiki): make concept lint findings actionable'
- 'bd0d1e3c96 feat(wiki): coordinate concept extraction batches'
- 'cd5d650479 fix(wiki): preserve concepts across partial batches'
- '970ef62975 feat(wiki): replace compile backlog tools with concept workflow'
- 'b2167f6fc3 fix(wiki): refresh metadata after concept apply'
- '4c9a8c8aad feat(wiki): reset through concept compiler'
- '456d72f2d0 fix(wiki): keep reset concept-only'
- '68ec0f2dfc fix(wiki): write concept overview on reset'
- '5ecdbc337c fix(wiki): store concept prompts outside MCP responses'
- '6c8e490790 fix(wiki): report concept overview writes'
- '4240282aab feat(wiki): route ambient import through concept batches'
- '7640ddc8fe fix(wiki): keep ambient status read-only'
- 'a4a4599ed3 fix(wiki): defer ambient scan commit until batch write'
- '4abc4c4c6e refactor(wiki): remove rag-owned compile metadata'
- '361d540eea fix(wiki): scrub cached rag compile metadata'
- 'bca8226381 refactor(wiki): remove legacy rag-backed compiler'
- '6daf737bfe docs(wiki): expose concept-first wiki commands'
- '41c6e86dd1 fix(wiki): align agent surfaces with concept compiler'
- '0fb706b153 fix(wiki): count concept index links in lint'
- '49464290d2 docs(adr): mark concept wiki compiler implemented'
- '5b8ffbd442 fix(wiki): generate query pages and prune legacy pages'
- '624731f3f9 test(wiki): cover update apply legacy cleanup'
---




# ADR-561: Concept-First Wiki Compiler Replacement

## Context

Augur's compiled wiki is intended to be a second-brain synthesis layer, not an index mirror. The current implementation violated that product contract by treating RAG/source entries as page candidates and then trying to filter the resulting explosion after the fact. A full rebuild could create source-shaped pages, timestamp-shaped pages, single-source topic wrappers, and `source-summary` pages. That is why the wiki grew by roughly an order of magnitude more than expected.

The comparison target, `atomicmemory/llm-wiki-compiler`, uses the right primitive: source hashes feed LLM concept extraction, extracted concepts merge across sources, concept and query pages are generated, wikilinks are resolved, and a compact index is rebuilt. Augur should adopt that architecture while preserving Augur-specific path resolution, MCP contracts, agent orchestration rules, and source surfaces.

ADR-560 implemented a semantic page compiler using `wiki_signal_graph.py`, `wiki_page_identity.py`, `wiki_page_candidates.py`, deterministic article sections, and `source-summary` output. That ADR improved thin token overlap, but it kept the wrong root abstraction: source/backlog records still shaped the generated wiki. This ADR supersedes ADR-560.

ADR-559's ambient file import loop remains a useful product flow, but its coupling to the RAG-backed wiki compile backlog must be rewired to the new concept-first compiler state.

## Decision

Replace the active RAG-backed wiki compile path with a concept-first compiler. The replacement is intentionally breaking: old `wiki-compile-*` backlog semantics, `source-summary`, RAG-owned wiki compile fields, and source-row-to-page generation are removed or rewritten instead of preserved as compatibility behavior.

### Source Inventory

Add a source inventory layer that discovers eligible material from retained `/ask` outcomes, syntheses, vault notes, documents, extracted document text, skills, commands, actions, integrations, ADRs, and project docs when relevant.

The inventory returns source descriptors with stable source id, kind, path or URI, title, body loader, checksum, modified time, and priority metadata. Generated wiki pages are excluded by default. RAG can help discover and search source material, but RAG metadata is not compiler state.

### Compiler State

Move wiki compile state to `get_runtime_dir()/wiki/`. State tracks source checksums, extracted concepts, source-to-concept edges, frozen slugs, deleted-source handling, extraction timestamps, generation timestamps, and compiler version.

This replaces these RAG frontmatter fields as active compiler state:

- `wiki_compile_status`
- `wiki_compiled_at`
- `wiki_compiled_checksum`
- `wiki_targets`

RAG reindexing should stop preserving those fields once the new state exists.

### Concept Extraction

For each new or changed source, the agent-orchestrated compiler extracts a bounded set of durable concepts, usually 3-8 for meaningful sources. Each extracted concept includes title, slug, summary, evidence, source id, confidence, aliases, and related hints.

Sources with no durable knowledge are marked processed in compiler state without creating a page.

### Concept Merge

Merge extracted concepts before page generation using slug, normalized title, aliases, source overlap, existing page frontmatter, and semantic similarity when available. The merge output owns the canonical slug, title, aliases, related concepts, source evidence, and stale-source markers.

New page creation requires a durable merged concept. A single-source concept can create a page only when the source is high value and the concept is durable. File existence alone is never sufficient.

### Page Generation

Write only concept and query pages as primary wiki outputs:

- `concepts/<slug>.md`
- `queries/<slug>.md`

Support pages are limited to `index.md`, `overview.md`, and maintenance `log.md` when needed. Concept and query pages use YAML frontmatter with title, page type, summary, sources, aliases, related links, timestamps, and compiler version.

The page body is authored synthesis with source citations. It is not a mechanical table of source records.

### Wikilink Resolution And Indexing

After page generation, build a title and alias index, resolve wikilinks, detect duplicate concept identities, detect broken links, and rebuild a compact concept/query index. The index must not become a source inventory.

Generated wiki pages still flow into RAG/search through `wiki-reindex`. Reindexing remains index-only and never creates pages.

### Command Contract

The command surface becomes:

- `wiki-status`: page counts, compiler state counts, changed-source counts, lint summary
- `wiki-reindex`: index existing wiki pages only
- `wiki-lint`: validate schema, links, duplicates, source refs, stale state, and legacy page types
- `wiki-purge`: remove compiled wiki pages and compiler state when requested
- `wiki-rebuild`: full concept-first compile from current sources
- `wiki-update`: incremental compile for new and changed sources
- `wiki-reset`: purge, rebuild, reindex, and lint

Old `wiki-compile-*` tools are removed or replaced with these semantics. There is no command that means "turn top RAG backlog rows into wiki pages."

### Agent-Orchestrated Execution

MCP/Python code performs deterministic operations: source discovery, source reads, state reads/writes, locking, page file writes, link resolution, linting, reindexing, and status reporting.

The agent performs judgment-heavy LLM work: extraction prompt execution, synthesized page prose, ambiguous concept merge decisions, and durability decisions. Dashboard actions must dispatch wiki rebuild/update to an IDE/CLI agent. Dashboard code must not call LLM APIs directly.

If no agent LLM execution surface is available, rebuild/update fails clearly. It does not fall back to source-summary generation.

## Consequences

### Positive

- Full rebuild page count becomes proportional to durable concepts instead of source count.
- The wiki becomes a learning layer rather than a generated source inventory.
- RAG remains useful for discovery and search without owning compile state.
- `wiki-reset` and `wiki-rebuild` gain semantics that match the user's mental model.
- Tests can directly prevent future source-summary and RAG-backed compile-state regressions.

### Negative

- This is a breaking cleanup across compiler modules, MCP tools, tests, docs, and generated skill surfaces.
- The LLM-heavy compiler needs an agent execution path, so fully unattended rebuilds require an agent runner rather than a pure script fallback.
- Ambient import must be rewired because it currently depends on the old backlog/compiler coupling.

### Neutral

- Markdown with YAML frontmatter remains the durable wiki artifact format.
- `wiki-reindex` continues to refresh browse/search indexing for existing wiki pages.
- RAG still indexes generated wiki pages after compilation.
- Document extraction and source discovery remain useful inputs.

## Implementation Order

1. Freeze and document the legacy deletion scope.
   - Run `git log --oneline -5 -- <file>` for each legacy compiler module before deletion.
   - Confirm this ADR supersedes ADR-560 for those files.
   - Mark old RAG-backed wiki docs as superseded.

2. Add concept compiler state and source inventory.
   - Create runtime-state helpers under the wiki/ingest implementation.
   - Add source descriptor models.
   - Ensure generated wiki pages are excluded from source inventory.
   - Add tests for new, changed, unchanged, and deleted sources.

3. Add extraction and merge contracts.
   - Define extraction result schema.
   - Add validation for title, slug, summary, evidence, source id, and confidence.
   - Add deterministic merge helpers for slug/title/alias/source overlap.
   - Add fake-agent/fake-LLM tests for bounded concept extraction.

4. Replace page generation.
   - Remove `source-summary` as an active page type.
   - Write `concepts/<slug>.md` and `queries/<slug>.md` with frontmatter.
   - Rebuild compact `index.md` and `overview.md` support pages.
   - Add lint failures for legacy source-summary output.

5. Replace MCP and command surfaces.
   - Remove or rewrite old `wiki-compile-*` registrations.
   - Add `wiki-rebuild` and `wiki-update` semantics.
   - Update `/wiki reset` to purge and run the concept compiler.
   - Update skill docs and regenerate agent surfaces.

6. Rewire ambient import.
   - Change ambient import to enqueue or prioritize source descriptors for the concept compiler.
   - Remove restamping of RAG `wiki_targets` metadata.
   - Preserve relocation and reindex behavior where still valid.

7. Remove legacy code and metadata preservation.
   - Delete inactive old compiler modules after reference checks.
   - Remove RAG preservation of wiki compile frontmatter.
   - Update tests to assert legacy terms are absent from active code.

8. Verify end to end.
   - Run targeted unit and MCP tests.
   - Run `wiki-reset`, `wiki-lint`, and `wiki-reindex`.
   - Confirm no `sources/` source-summary pages are generated.
   - Confirm RAG search can find generated concept pages.

## Alternatives Considered

### Patch the RAG-backed compiler with stricter filters

Rejected. This keeps the wrong primitive alive. The failure is not just weak thresholds; it is that source inventory rows are treated as page candidates.

### Directly port `atomicmemory/llm-wiki-compiler`

Rejected. The reference architecture is valuable, but a direct port would ignore Augur's path system, external vault/doc roots, MCP contracts, agent-orchestrated execution rules, and generated skill surfaces.

### Keep source-summary as a fallback for low-confidence sources

Rejected. This would recreate the page explosion under a different branch. Low-confidence or non-durable sources should update compiler state without creating pages.

### Let RAG continue to store compile state

Rejected. RAG is the retrieval substrate. Compiler state needs concept extraction records, source-to-concept edges, frozen slugs, and generation timestamps that belong to the compiler, not the search index.

## References

- Design spec: `docs/superpowers/specs/2026-04-20-concept-first-wiki-compiler-replacement-design.md`
- External reference: `https://github.com/atomicmemory/llm-wiki-compiler`
- ADR-404: Markdown frontmatter user-facing files
- ADR-478: Browse index freshness
- ADR-546: LLM wiki maintenance
- ADR-559: Ambient file import to wiki
- ADR-560: Semantic wiki page compiler, superseded by this ADR

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - skills/ingest/scripts/mcp/wiki_tools.py: remove or replace wiki-compile-* backlog tools with concept-first wiki-rebuild and wiki-update semantics
    - skills/ingest/scripts/wiki_reset.py: reset purges legacy state and runs concept-first rebuild instead of RAG-backed source-scope compile
    - skills/ingest/scripts/ambient_import_worker.py: ambient import prioritizes source descriptors for concept compile instead of restamping RAG wiki_targets
    - skills/rag/scripts/_indexer_helpers.py: stop preserving wiki_compile_status, wiki_compiled_at, wiki_compiled_checksum, and wiki_targets
  patterns_deprecated:
    - RAG entries as wiki compiler state
    - source-summary as an active wiki page type
    - source inventory rows as page candidates
    - heuristic signal graph/page identity/page candidate compiler as the active wiki compile path
    - deterministic article sections as the main wiki authoring engine
  files_affected:
    - skills/ingest/scripts/wiki_compile_backlog.py
    - skills/ingest/scripts/wiki_compile_worker.py
    - skills/ingest/scripts/wiki_compiler.py
    - skills/ingest/scripts/wiki_page_candidates.py
    - skills/ingest/scripts/wiki_page_identity.py
    - skills/ingest/scripts/wiki_signal_graph.py
    - skills/ingest/scripts/wiki_article_sections.py
    - skills/ingest/scripts/wiki_page_writer.py
    - skills/ingest/scripts/wiki_pages.py
    - skills/ingest/scripts/wiki_schema.py
    - skills/ingest/scripts/wiki_reset.py
    - skills/ingest/scripts/mcp/wiki_tools.py
    - skills/ingest/assets/seeds/wiki-schema/page-types.yaml
    - skills/ingest/assets/seeds/wiki-schema/lint-rules.yaml
    - skills/rag/scripts/_indexer_helpers.py
    - skills/rag/scripts/unified_indexer.py
    - skills/ingest/SKILL.md
```

## Implementation Evidence

Implemented on 2026-04-20 as a breaking concept-first replacement. The implementation adds source descriptors, runtime compiler state, extraction payload validation, concept merge/page generation, concept link linting, MCP `wiki-rebuild`/`wiki-update`/`wiki-apply-concept-batch`, concept-first reset, ambient import concept batching, RAG compile metadata scrubbing, and generated command/agent surface updates.

Verification covered targeted ingest/RAG/dashboard tests, legacy-term audits, and an isolated registered-tool reset/apply/reindex harness. The harness confirmed that `wiki-reset` prepares an agent-action concept batch, `wiki-apply-concept-batch` writes `concepts/<slug>.md` plus compact support pages, `wiki-reindex` indexes generated concept pages without creating wiki content, and no `sources/` or `source-summary` pages survive reset.

## Implementation Prompt

Implement ADR-561 as a breaking replacement of the active wiki compiler. Use the approved design spec at `docs/superpowers/specs/2026-04-20-concept-first-wiki-compiler-replacement-design.md` as the source of truth.

**Team name**: `adr-561-concept-first-wiki-compiler`

### Phase 1: Governance And Legacy Scope
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | high | Read ADR-559, ADR-560, and the design spec; map each legacy file to keep, rewrite, or delete. | ADRs, design spec, `skills/ingest/scripts/wiki_*.py` |
| 1.2 | validator | medium | Run `git log --oneline -5 -- <file>` for every deletion candidate and record the governing ADR decision in the implementation notes. | legacy compiler files |
| 1.3 | developer | medium | Mark superseded design/plan docs and generated skill docs so they no longer present RAG-backed compile state as current. | `docs/superpowers/specs`, `docs/superpowers/plans`, `skills/ingest/SKILL.md` |

### Phase 2: Concept Compiler Core
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Add source descriptor and compiler state modules under ingest/wiki code, using `get_runtime_dir()/wiki/` for state. | new ingest wiki compiler modules |
| 2.2 | developer | high | Add concept extraction result schemas and validation with fake-agent tests. | new concept extraction module and tests |
| 2.3 | developer | high | Add concept merge helpers for slug, title, aliases, source overlap, and existing page frontmatter. | new merge module and tests |
| 2.4 | developer | high | Add concept/query page writer and compact index builder. | page writer, index builder, tests |

### Phase 3: Command And Integration Replacement
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Replace old `wiki-compile-*` MCP tools with `wiki-rebuild` and `wiki-update` semantics. | `skills/ingest/scripts/mcp/wiki_tools.py` |
| 3.2 | developer | medium | Update `wiki-reset` to purge legacy pages/state and run the concept compiler, then lint and reindex. | `skills/ingest/scripts/wiki_reset.py` |
| 3.3 | developer | medium | Rewire ambient import to prioritize source descriptors and stop restamping RAG `wiki_targets`. | ambient import modules and tests |
| 3.4 | developer | medium | Remove RAG preservation of wiki compile fields and update RAG tests. | `skills/rag/scripts/_indexer_helpers.py`, RAG tests |

### Phase 4: Legacy Removal And Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | high | Delete or rewrite inactive legacy modules after dependency searches show no active callers. | legacy compiler modules |
| 4.2 | validator | medium | Run repository audits for `source-summary`, `wiki_compile_status`, `wiki_compiled`, `wiki_targets`, and `wiki-compile-`; ensure only superseded docs mention removed terms. | docs and skills |
| 4.3 | validator | high | Run targeted tests, `wiki-reset`, `wiki-lint`, `wiki-reindex`, and verify generated wiki pages are concept-sized with no `sources/` output. | tests, runtime wiki |
| 4.4 | architect | medium | Update ADR-561 status and implementation evidence once verification passes. | ADR-561, ADR index |

### Completion Criteria

- [x] Full rebuild creates concept/query pages, not source inventory pages.
- [x] `source-summary` is not an active page type.
- [x] RAG entries no longer own wiki compile state.
- [x] Old `wiki-compile-*` backlog semantics are absent.
- [x] Ambient import works through the concept compiler.
- [x] `wiki-reset`, `wiki-lint`, and `wiki-reindex` pass.
- [x] ADR index, RAG ADR index, and agent surfaces are regenerated.
