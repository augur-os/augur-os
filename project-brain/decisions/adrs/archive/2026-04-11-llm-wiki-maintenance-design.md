# LLM Wiki Maintenance Design — Phase 2 of LLM Wiki

**Date:** 2026-04-11
**Status:** Draft
**Phase:** 2 of 2 (Phase 1: Ingest Pipeline — merged to main)
**Inspired by:** [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
**Depends on:** `docs/superpowers/specs/2026-04-11-ingest-pipeline-design.md`

## Summary

Phase 2 transforms Augur's wiki from a passive file listing into an LLM-maintained knowledge base — the synthesis layer between raw sources and the user. After content is ingested (Phase 1), the agent updates structured wiki pages, cross-references topics, and maintains consistency. A nightly autoloop does full editorial passes: rewriting stale pages, merging duplicates, and filling gaps.

This phase also consolidates Augur's knowledge stack: daily logs become ephemeral, knowledge syntheses are deprecated (replaced by wiki), and MEMORY.md narrows to behavioral context only.

## Architecture

### Knowledge Ring Model

```
Ring 1: Raw Sources (vault + documents)
├── vault/dev/adrs/          # architecture decisions
├── vault/{skill}/           # skill-specific data (finance, health, etc.)
├── vault/scraper/           # scraped web content (90-day retention)
├── vault/attention/         # inbox items
└── get_documents_dir()/     # binary files (PDFs, images)

Ring 2: Synthesized Knowledge (vault/wiki/)
├── vault/wiki/{hub}/*.md    # LLM-maintained topic pages
├── vault/wiki/index.md      # auto-generated catalog
└── vault/wiki/overview.md   # high-level summary

Ring 3: Behavioral Context (vault/memory/)
├── vault/memory/MEMORY.md   # agent behavioral instructions only
└── (narrowed scope — no domain knowledge)

Ring 4: Indexes & Operational (runtime — all rebuildable)
├── {runtime}/rag/           # RAG indexes, BM25, project index
├── {runtime}/wiki/          # tags, log, scan-state, lint, snapshots
├── {runtime}/memory/        # daily logs, HUMAN_API.md
└── {runtime}/ingest/        # job queue, staging
```

### Knowledge Flow

```
Raw Sources → Ingest Pipeline → Vault/Documents
                                      ↓
                               Wiki (LLM synthesis)
                                      ↓
                               RAG Index (searchable)
                                      ↓
                               Agent uses for answers

MEMORY.md (behavioral context, separate concern)
```

### Execution Model

All execution happens inside AI client sessions per `docs/references/ai-client-execution-model.md`. The agent is the orchestrator. MCP tools are stateless atomic operations. No daemon-owned processing.

## Wiki Operations

### 1. Ingest-Update

After Phase 1 pipeline routes content, the agent updates wiki pages:

1. Call `wiki-tags` — get the tag manifest (fast, small)
2. Extract key topics from the ingested content
3. Match topics against existing page tags
4. For matching pages: `wiki-read` → update content → `wiki-write`
5. For unmatched topics: create new page in appropriate hub
6. Call `wiki-log` with session summary

One ingest may touch 5-15 wiki pages. The agent decides which pages based on content relevance.

### 2. Session-Update

Before a session ends, the agent reviews what was learned:

1. Summarize session activity (ingested content, discussed topics, decisions made)
2. Update any wiki pages that gained knowledge from the conversation
3. Write one summary entry to `wiki/log.md`

### 3. Lint (Nightly Autoloop)

Full editorial pass via `auto-wiki-maintenance`:

1. **Scan for changes** — compare tag timestamps against source mtimes
2. **Update stale pages** — rewrite pages with newer sources available
3. **Merge duplicates** — detect overlapping pages, consolidate
4. **Fix cross-references** — validate `[[wikilinks]]`, add missing links
5. **Fill gaps** — find sources with no wiki coverage, create pages
6. **Rewrite for clarity** — pages not updated in 30+ days get a full editorial rewrite
7. **Enforce page budget** — split pages exceeding 500 words into sub-topics
8. **Update infrastructure** — rebuild tags.yaml, index.md, overview.md
9. **Log** — session summary to log.md

### 4. Bootstrap

Three entry points for initial wiki population:

- **`/wiki seed`** — lightweight, no LLM. Creates skeleton pages from file metadata (titles, paths, dates). Instant starting point.
- **`/wiki rebuild [--hub <hub>]`** — deep LLM synthesis from all sources. Expensive but thorough. Can scope to a single hub.
- **Nightly enrichment** — autoloop detects skeleton/sparse pages and enriches incrementally over successive nights.

Recommended first-time flow:
```
/wiki seed                  # instant: skeleton pages from existing content
/wiki rebuild --hub dev     # deep pass on most important hub
# nightly autoloop handles the rest
```

## Wiki Directory Structure

```
vault/wiki/
├── index.md              # auto-generated catalog with summaries
├── overview.md           # high-level knowledge summary
├── finance/
│   ├── budgeting.md      # agent-created topic pages
│   ├── investments.md
│   └── ...
├── career/
├── health/
├── lifestyle/
├── brain/
├── dev/
│   ├── architecture.md
│   ├── adrs-digest.md
│   └── ...
└── {hub}/                # new hubs emerge as content arrives
```

Hub directories are created organically by the agent. No config gates them. When content doesn't fit existing hubs, the agent creates a new directory. `index.md` reflects reality automatically.

Wiki hub names align with Augur dashboard hubs when possible but can diverge — the wiki can have hubs the dashboard doesn't.

## Wiki Page Format

```markdown
---
title: Mediterranean Diet
type: wiki-page
hub: lifestyle
tags: [nutrition, mediterranean, heart-health, meal-prep, olive-oil]
sources: [2026-04-11-mediterranean-diet-guide.md, 2026-04-08-heart-health-study.pdf]
updated: 2026-04-11T14:30:00Z
---

# Mediterranean Diet

The Mediterranean diet emphasizes whole grains, vegetables, fruits, and healthy fats...

## Key Principles
...

## See Also

- [[heart-health]]
- [[nutrition-basics]]
```

Key frontmatter fields:
- `tags` — keywords for matching incoming content to this page
- `sources` — list of ingested files that contributed (provenance)
- `hub` — which hub directory this belongs to
- `type: wiki-page` — distinguishes from index/overview

### Page Size Budget

| Type | Max words | Lint action if exceeded |
|------|-----------|----------------------|
| Topic page | 500 | Split into sub-topics |
| Hub overview | 300 | Summarize, link to details |
| index.md | No limit | One line per page (auto-generated) |

The LLM **rewrites**, never appends. When new sources arrive, the page is rewritten to incorporate new knowledge concisely — not extended with additional paragraphs.

## Tag Manifest

`{runtime}/wiki/tags.yaml` — auto-generated from page frontmatter after each write.

```yaml
pages:
  lifestyle/mediterranean-diet:
    tags: [nutrition, mediterranean, heart-health, meal-prep, olive-oil]
    title: Mediterranean Diet
    updated: 2026-04-11T14:30:00Z
  finance/budgeting:
    tags: [budget, expenses, monthly-planning, savings]
    title: Personal Budgeting
    updated: 2026-04-10T09:00:00Z
```

The agent reads `tags.yaml` to find relevant pages (fast, small) instead of scanning all page frontmatter. For edge cases where tags don't match (new topics), the agent falls back to RAG search across wiki page content.

## MCP Tools

Seven stateless tools in the `ingest` skill:

| Tool | Type | Args | Returns |
|------|------|------|---------|
| `wiki-read` | read | `{page}` | `{title, tags, sources, body, updated}` |
| `wiki-write` | mutation | `{page, title, tags, sources, body, hub}` | `{path, created_or_updated}` |
| `wiki-list` | read | `{hub?}` | `{pages: [{page, title, tags, updated}]}` |
| `wiki-tags` | read | `{}` | Full tags.yaml content |
| `wiki-log` | mutation | `{entry}` | `{logged_at}` |
| `wiki-search` | read | `{query, tags?}` | `{matches: [{page, title, score, snippet}]}` |
| `wiki-scan-sources` | read | `{hub?}` | `{sources: [{path, type, title, hub, tags}]}` |

`wiki-write` automatically:
- Creates hub directories if needed
- Updates `tags.yaml`
- Refreshes `index.md`
- Adds `updated` timestamp to frontmatter

`wiki-scan-sources` lists all content across vault, documents, and scraper that could feed wiki pages — used during rebuild and gap detection.

## Autoloop: `auto-wiki-maintenance`

Nightly editorial pass following Augur autoloop patterns.

### Difficulty Levels

| Level | Scope |
|-------|-------|
| 1 | Structural only — fix links, update index, rebuild tags |
| 2 | + stale page detection and rewrite |
| 3 | + gap detection, new page creation |
| 4 | + duplicate merging, cross-reference enrichment |
| 5 | + full editorial: rewrite for clarity, consistency across hubs, enforce page budget |

### Evolution

When all checks pass at max difficulty, the autoloop reports evolution gaps per CLAUDE.md rule 8 — untested source types, hubs with sparse coverage, cross-reference patterns not yet attempted.

## Agent Instructions

Three commands encode the wiki workflow:

### `/ingest` (modify existing command)

Add wiki update step after routing:
```
After routing content to the vault:
1. Call wiki-tags to get the tag manifest
2. Extract key topics from the ingested content
3. Match topics against existing page tags
4. For each matching page: wiki-read → update content → wiki-write
5. If no pages match: create a new page in the appropriate hub
6. Call wiki-log with a session summary before finishing
```

### `/wiki update` (new command)

Manual trigger for wiki updates:
```
Review recent session activity and update wiki pages:
1. wiki-scan-sources to find content not yet reflected in wiki
2. wiki-tags to find relevant existing pages
3. For each gap: read source, update or create wiki pages
4. Rebuild tags.yaml and index.md
5. Log changes
```

### `/wiki rebuild [--hub <hub>]` (new command)

Full bootstrap from existing sources:
```
Scan all knowledge sources and create synthesized wiki pages:
1. wiki-scan-sources for all or specified hub
2. Group sources by topic
3. For each topic cluster: synthesize a wiki page
4. Build tags.yaml and index.md from scratch
```

### `/wiki seed` (new command)

Lightweight skeleton without LLM:
```
Create skeleton wiki pages from file metadata:
1. Scan ADRs, vault data, documents, memory
2. Create one page per cluster with title, source list, and placeholder body
3. Build tags.yaml and index.md
```

### `/auto-wiki-maintenance` (new autoloop command)

Nightly editorial pass as described in the Autoloop section.

## Knowledge Stack Consolidation

### Changes to Existing Systems

| System | Change | Migration |
|--------|--------|-----------|
| **Daily logs** | Move from `vault/memory/daily/` to `{runtime}/memory/daily/` | Update `auto-memory-sync`, `memory-curate` path references |
| **Knowledge syntheses** | Deprecated — wiki replaces | Ingest existing syntheses into wiki during `/wiki rebuild` |
| **HUMAN_API.md** | Move from `vault/memory/` to `{runtime}/memory/` | Update `memory-profile-regenerate` path |
| **MEMORY.md** | Narrow scope to behavioral context only | No code change — agent instructions updated |
| **Scraper retention** | Add 90-day retention policy | Configure `clear-old-scraped-content` default |
| **RAG indexer** | Add `wiki` category to unified indexer | Index `vault/wiki/**/*.md` as a source |

### What Stays Unchanged

- ADRs, vault skill data, documents, attention — all stay in current locations
- RAG indexes, project index — stay in runtime
- Ingest pipeline (Phase 1) — unchanged
- Unified search — wiki becomes another scope alongside existing ones

## Vault Wiki Content Rules

- The LLM rewrites pages, never appends endlessly
- Pages exceeding 500 words are split by the lint
- `log.md` has a 30-entry rolling window (in runtime, not vault)
- `tags.yaml` is in runtime (generated, rebuildable)
- Snapshots (pre-rewrite) kept 7 days in runtime, then purged
- Hub directories created organically — no config registry

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| Phase 1 ingest pipeline | Existing (merged) | Content extraction and routing |
| Wiki ops (`wiki_ops.py`) | Existing (to modify) | Current seed/lint — refactor for new model |
| RAG unified indexer | Existing (to modify) | Add wiki category |
| Memory system | Existing (to modify) | Path changes, scope narrowing |
| Daemon config | Existing (to modify) | Register autoloop |
