---
name: rag
x-augur-type: domain
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
x-augur-tags: []
description: 'Core plugin for RAG indexing and knowledge retrieval in the AI hub..
  Covers: commands. Use when working with rag features or data.'
x-augur-tab: memory
x-augur-requires-platform: true
x-augur-mcp-tools:
- search-skill-knowledge
- rag-status
- rag-sync
x-augur-dashboard-pages:
- route: /workspace/rag
  title: RAG
  icon: LayoutDashboard
x-augur-data-dir: rag
x-augur-config:
  loop:
    name: knowledge-enrichment
    tier: 0
    trigger: nightly
    callable: skills/ai/scripts/ops/rag_reindex.py
  contributions:
    blocks:
    - id: rag
      type: stat-card
      title: RAG Status
      label: RAG Status
      icon: Database
      expandTo: /browse?view=profile
      config_schema: {}
      action:
        label: Sync now
        mcp_tool: rag-sync
      data_source:
        mcp_tool: rag-status
    commands:
    - id: search
      type: workflow
      visibility: core
      description: Search knowledge across all plugins via RAG indexes. Also supports
        status, reindex, and cleanup.
---















# Rag

Three-tier knowledge retrieval: ripgrep for source markdown, BM25 for extracted documents, and wiki-driven compiled knowledge.

## Overview

Manages search artifacts across all skills, providing search, status, reindex, and cleanup capabilities. Nightly reindexing keeps extracted document search current while source markdown is searched directly.

Key components: direct ripgrep search over source content, BM25 sparse retrieval for extracted documents, and a static content index for navigation.

## Commands

Knowledge search is exposed through `/ask` (ADR-766 consolidation merged the
former `/search` command into it). `/ask` routes structured index queries —
`search`, `status`, `reindex`, `cleanup`, `purge` — to the RAG surface and
conversational queries to the reflective second-brain flow. RAG reindexing also
runs automatically through the daemon's `knowledge-enrichment` loop and can be
triggered manually with `/a-loops scan index`.

### `/wiki`

Manage the shared vault wiki used for cross-client knowledge compounding.

- `/wiki status` — show wiki structure, compiler backlog, batch, coverage, and index status
- `/wiki reindex` — refresh browse/search indexing for existing wiki pages
- `/wiki rebuild` — prepare a concept-first compile from current sources
- `/wiki update` — prepare an incremental concept-first compile for changed sources
- `/wiki migrate-v4` — dry-run the ADR-740 v3-to-v4 concept page migration; use `--apply` only after reviewing diffs
- `/wiki lint` — detect missing required pages, broken wiki links, and orphan pages
- `/wiki purge` — remove the compiled wiki plus runtime/browse artifacts before rebuilding from scratch
- `/wiki reset` — run a safe clean-slate reset; bounded by default, exhaustive only with `--all`
- `/wiki report` — generate a Second Brain Intelligence Report through the agent-orchestrated report flow

## Index Freshness

Three layers keep the central index current (spec 2026-06-10):

1. **rag_watcher daemon service** — watches all registered brain roots
   (brain registry) plus document sources via FSEvents; changed vault/wiki/
   document files are incrementally reindexed within seconds.
2. **Daily reconcile** — the watcher runs a full `reindex_all()` at 03:00
   local, covering repo-structure categories and anything missed offline.
   (This replaces the Codex-scheduled nightly trigger, which required an AI
   client session and did not reliably fire.)
3. **Headless manual sync** — `aug rag sync [--full] [--category X]`,
   the `rag-sync` MCP tool, and the dashboard RAG card's "Sync now" button
   all dispatch the same engine (`src/lib/index/incremental.py`). `/ask
   reindex` delegates there too — no long-running chat session.

`aug rag status` reports per-category freshness and the watcher heartbeat.
Binary documents index their tier-0 offline extraction immediately; pages
needing LLM-assisted OCR are flagged (`llm_assisted`) and enriched by the
next AI session via the pending-enrichment queue.

## Setup

No additional setup required for the starter page.

## Data

Data for this skill lives in `~/Library/Application Support/Augur/rag/`.
Shared compiled wiki pages live in the git-tracked vault wiki; runtime wiki
state stores only compiler mechanics such as batches, tags, and logs.

## Development

- Dashboard entry point: `/browse?view=profile`
- Config: `skills/rag/SKILL.md`
- API routes: `skills/rag/scripts/mcp/` (create as needed)
- Reindex script: `skills/ai/scripts/ops/rag_reindex.py`

## Additional resources
- [evals/rank.json](evals/rank.json)
- [assets/seeds/rag/pages/career/analytics.md](assets/seeds/rag/pages/career/analytics.md)
- [assets/seeds/rag/pages/career/demo.md](assets/seeds/rag/pages/career/demo.md)
- [assets/seeds/rag/pages/career/financials.md](assets/seeds/rag/pages/career/financials.md)
- [assets/seeds/rag/pages/career/gtm.md](assets/seeds/rag/pages/career/gtm.md)
- [assets/seeds/rag/pages/career/gtm__community.md](assets/seeds/rag/pages/career/gtm__community.md)
- [assets/seeds/rag/pages/career/gtm__content.md](assets/seeds/rag/pages/career/gtm__content.md)
- [assets/seeds/rag/pages/career/gtm__marketing.md](assets/seeds/rag/pages/career/gtm__marketing.md)
- [assets/seeds/rag/pages/career/gtm__social.md](assets/seeds/rag/pages/career/gtm__social.md)
- [assets/seeds/rag/pages/career/investors.md](assets/seeds/rag/pages/career/investors.md)
- [assets/seeds/rag/pages/career/market.md](assets/seeds/rag/pages/career/market.md)
- [assets/seeds/rag/pages/career/market__comparison.md](assets/seeds/rag/pages/career/market__comparison.md)
- [assets/seeds/rag/pages/career/market__competition.md](assets/seeds/rag/pages/career/market__competition.md)
- [assets/seeds/rag/pages/career/market__positioning.md](assets/seeds/rag/pages/career/market__positioning.md)
- [assets/seeds/rag/pages/career/media.md](assets/seeds/rag/pages/career/media.md)
- [assets/seeds/rag/pages/career/overview.md](assets/seeds/rag/pages/career/overview.md)
- [assets/seeds/rag/pages/career/sales.md](assets/seeds/rag/pages/career/sales.md)
- [assets/seeds/rag/pages/career/sales__contracts.md](assets/seeds/rag/pages/career/sales__contracts.md)
- [assets/seeds/rag/pages/career/sales__outreach.md](assets/seeds/rag/pages/career/sales__outreach.md)
- [assets/seeds/rag/pages/career/startups.md](assets/seeds/rag/pages/career/startups.md)
- [assets/seeds/rag/pages/career/strategy.md](assets/seeds/rag/pages/career/strategy.md)
- [assets/seeds/rag/pages/career/telemetry.md](assets/seeds/rag/pages/career/telemetry.md)
- [assets/seeds/rag/pages/life/apple.md](assets/seeds/rag/pages/life/apple.md)
- [assets/seeds/rag/pages/life/overview.md](assets/seeds/rag/pages/life/overview.md)
- [assets/seeds/rag/pages/life/recipes__[id].md](assets/seeds/rag/pages/life/recipes__[id].md)
- [assets/seeds/rag/pages/life/voice.md](assets/seeds/rag/pages/life/voice.md)
- [assets/seeds/rag/pages/studio/overview.md](assets/seeds/rag/pages/studio/overview.md)
- [assets/seeds/rag/pages/studio/refactor.md](assets/seeds/rag/pages/studio/refactor.md)
- [assets/seeds/quality_baseline.yaml](assets/seeds/quality_baseline.yaml)
