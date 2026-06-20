---
status: Implemented
date: 2026-04-11
deciders:
  - gsannikov
related:
  - ADR-545
  - ADR-532
hub: brain
tags:
  - wiki
  - llm
  - knowledge
  - memory
  - synthesis
superseded_by: null
---

# ADR-546: LLM Wiki Maintenance

## Context

Augur's wiki was a passive file listing — pages created manually or by `/wiki seed`, rarely updated, invisible to agents as a live knowledge source. Knowledge was scattered across `vault/memory/syntheses/` (one-off syntheses), `vault/memory/daily/` (daily logs), MEMORY.md (mixing behavioral rules with domain knowledge), and raw vault data. There was no mechanism to synthesize incoming content into durable, structured wiki pages. After ingest (ADR-545), content went into the vault but nothing synthesized it into an organized knowledge base.

Inspired by Karpathy's LLM Wiki pattern: the agent maintains a small set of high-quality pages rather than an ever-growing pile of raw notes.

## Decision

Transform the wiki into the synthesis layer between raw sources and behavioral context via four operations and a knowledge ring model.

### Knowledge Ring Model

| Ring | Location | Role |
|------|----------|------|
| 1 — Raw Sources | `vault/**`, `get_documents_dir()` | Ground truth — never deleted by wiki ops |
| 2 — Synthesized Knowledge | `vault/wiki/{hub}/*.md` | LLM-maintained topic pages (the new synthesis layer) |
| 3 — Behavioral Context | `vault/memory/MEMORY.md` | Agent instructions only — no domain knowledge |
| 4 — Indexes (runtime) | `{runtime}/rag/`, `{runtime}/wiki/` | Rebuildable — tags.yaml, logs, snapshots |

### Four Wiki Operations

**1. Ingest-update** — after Phase 1 pipeline routes content, the agent calls `wiki-tags`, extracts key topics, matches against existing page tags, and rewrites matching pages or creates new ones. One ingest may touch 5–15 pages.

**2. Session-update** — before a session ends, the agent reviews what was learned and updates relevant pages, then logs a summary entry to `wiki/log.md`.

**3. Nightly lint** (`auto-wiki-maintenance` autoloop) — full editorial pass: stale page rewrites, duplicate merging, cross-reference fixing, gap filling, page budget enforcement (500-word limit per page → split into sub-topics), infrastructure rebuild (tags.yaml, index.md, overview.md).

**4. Bootstrap** — `/wiki seed` (metadata-only, no LLM, instant skeleton) and `/wiki rebuild [--hub <hub>]` (deep LLM synthesis from all sources, scopeable by hub).

### 7 MCP Tools (in `ingest` skill)

| Tool | Type | Purpose |
|------|------|---------|
| `wiki-read` | read | Fetch page content + frontmatter |
| `wiki-write` | mutation | Write page, auto-update tags.yaml + index.md |
| `wiki-list` | read | All pages, optionally filtered by hub |
| `wiki-tags` | read | Full tag manifest (fast lookup for topic matching) |
| `wiki-log` | mutation | Append session summary entry |
| `wiki-search` | read | RAG + tag-based search across wiki pages |
| `wiki-scan-sources` | read | All vault/docs content that could feed wiki pages |

`wiki-write` atomically creates hub directories, updates `tags.yaml`, refreshes `index.md`, and stamps `updated` on the frontmatter.

### 5 Commands

`/ingest` (extended with wiki-update step), `/wiki update`, `/wiki rebuild [--hub]`, `/wiki seed`, `/auto-wiki-maintenance`.

### Knowledge Stack Consolidation

| System | Change |
|--------|--------|
| Daily logs | Moved from `vault/memory/daily/` to `{runtime}/memory/daily/` (ephemeral, rebuildable) |
| Knowledge syntheses | Deprecated — wiki replaces; existing syntheses ingested via `/wiki rebuild` |
| HUMAN_API.md | Moved to `{runtime}/memory/` |
| MEMORY.md | Narrowed to behavioral context only (instructions, preferences) |
| Scraper vault | 90-day retention policy added |
| RAG indexer | `wiki` category added to unified indexer |

**Cross-client rule 27** (generated agent files frontmatter) added to CLAUDE.md as a direct output of this ADR's wiki-builder agent work.

## Consequences

### Positive

- Wiki becomes the authoritative synthesis layer — agents get curated knowledge, not raw files
- MEMORY.md stays small and behavioral; domain knowledge lives in wiki pages
- Nightly autoloop maintains quality without user intervention
- Tag manifest enables fast topic routing without scanning all pages
- LLM rewrites pages (never appends) — prevents unbounded growth
- Daily logs move to runtime, keeping the vault clean

### Negative

- Initial bootstrap (`/wiki rebuild`) is expensive — processes all vault content through LLM
- Wiki diverges from raw sources over time; provenance tracked via `sources:` frontmatter but not enforced
- Hub directories created organically by the agent — no schema guard, naming consistency depends on agent judgment
- 90-day scraper retention removes content that was previously kept indefinitely

### Neutral

- ADRs, vault skill data, documents, attention inbox unchanged
- Phase 1 ingest pipeline unchanged — wiki update is an additive step post-route
- Unified search gains a `wiki` scope alongside existing scopes
- Snapshots (pre-rewrite) kept 7 days in runtime, then purged automatically

## Alternatives Considered

### Alternative 1: Extend knowledge syntheses

Keep `vault/memory/syntheses/` and add an update mechanism. Rejected: syntheses were created per-topic without cross-linking, grew as append-only files, and had no quality enforcement. The wiki page budget model (500 words → split) solves the unbounded growth problem that syntheses didn't address.

### Alternative 2: Vector-only knowledge (no wiki pages)

Store knowledge purely as RAG embeddings, no human-readable pages. Rejected: loses the human-readable synthesis that makes wiki pages useful for browsing and sharing (ADR-547 depends on readable pages), and embeddings can't surface patterns or blind spots.

### Alternative 3: Full graph database for knowledge

Neo4j or similar for entity-relationship modeling. Rejected: too complex to bootstrap, requires schema design upfront, can't be edited as plain markdown files, and doesn't fit the local-first / vault-as-files model.

## References

- Source spec: `docs/superpowers/specs/2026-04-11-llm-wiki-maintenance-design.md`
- Phase 1 ADR: ADR-545 (Unified Content Ingest Pipeline)
- Phase 3 ADR: ADR-547 (Second Brain Intelligence Report)
- ADR-532: Query Compounding and Content Index
- Karpathy's LLM Wiki: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

## Implementation Prompt

> Already implemented. Wiki MCP tools in ingest skill, 5 commands registered, cross-client rule 27 added.

**Team name**: `adr-546-llm-wiki`

### Completion Criteria

- [x] All phases executed
- [x] 7 MCP wiki tools implemented and registered
- [x] 5 commands defined (ingest extended + 4 new wiki commands)
- [x] auto-wiki-maintenance autoloop registered in daemon config
- [x] Daily logs migrated to runtime path
- [x] Knowledge syntheses deprecated in docs
- [x] Cross-client rule 27 added to CLAUDE.md
- [x] ADR status updated to Implemented
