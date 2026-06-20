---
title: Wiki Ingest And Compilation Commands
summary: Wiki ingest and compilation commands capture raw sources, prepare concept
  batches, apply agent synthesis, reindex compiled pages, and report knowledge health
  without hand-writing wiki pages.
tags:
- wiki-ingest-and-compilation-commands
- agent-learning-compounding-pipeline
- knowledge-automation-command-loops
- command
- ingest
- compilation
- commands
aliases:
- ingest command loop
- wiki compile commands
related:
- '[[agent-learning-compounding-pipeline]]'
- '[[knowledge-automation-command-loops]]'
created: '2026-05-03T13:41:02Z'
_page_type: concept
_hub: command
_sources:
- vault:skills/ingest/commands/ask-sync.md
- vault:skills/ingest/commands/auto-wiki-maintenance.md
- vault:skills/ingest/commands/ingest-url.md
- vault:skills/ingest/commands/ingest.md
- vault:skills/ingest/commands/wiki-full-index.md
- vault:skills/ingest/commands/wiki-rebuild.md
- vault:skills/ingest/commands/wiki-report.md
- vault:skills/ingest/commands/wiki-reset.md
- vault:skills/ingest/commands/wiki-update.md
_source_fingerprint: f54edc12f9bb05325d00f67ed996aa493928f05f69cb3f75950ae6db0a500665
_compiler_version: concept-article-v4
_updated: '2026-05-03T13:41:02Z'
_cites:
- '[[vault:skills/ingest/commands/ask-sync.md]]'
- '[[vault:skills/ingest/commands/auto-wiki-maintenance.md]]'
- '[[vault:skills/ingest/commands/ingest-url.md]]'
- '[[vault:skills/ingest/commands/ingest.md]]'
- '[[vault:skills/ingest/commands/wiki-full-index.md]]'
- '[[vault:skills/ingest/commands/wiki-rebuild.md]]'
- '[[vault:skills/ingest/commands/wiki-report.md]]'
- '[[vault:skills/ingest/commands/wiki-reset.md]]'
- '[[vault:skills/ingest/commands/wiki-update.md]]'
_mentions:
- '[[concepts/agent-learning-compounding-pipeline]]'
- '[[concepts/knowledge-automation-command-loops]]'
_relates_to:
- '[[agent-learning-compounding-pipeline]]'
- '[[command]]'
- '[[commands]]'
- '[[compilation]]'
- '[[ingest]]'
- '[[knowledge-automation-command-loops]]'
_entity_tier: 3
---

# Wiki Ingest And Compilation Commands

## Compiled truth

### Current Thesis

Wiki ingest and compilation commands are the controlled path from raw sources and retained answers into source cards, concept batches, compiled pages, reports, and search indexes.

### What This Page Knows

The command sources describe retained ask outcome sync, URL capture, general ingest, bounded wiki update and rebuild batches, full backlog draining, reset recovery, report generation, and the auto-maintenance loop. Read together, they enforce a sharp separation: MCP tools perform atomic operations, while the IDE or CLI agent performs concept extraction and applies payloads through the compiler. This keeps the wiki from becoming one page per source and makes backlog reduction auditable.

### Key Dimensions

- Ask sync compounds retained answers into memory, synthesis, and candidate wiki pages.
- Auto-wiki maintenance and full-index commands repeat update, extraction, apply, reindex, lint, report, and log cycles until stop rules fire.
- Ingest and ingest-url capture files, folders, text, URLs, and source cards with routing evidence.
- Reset and report commands handle recovery and human-readable intelligence outputs without breaking the concept-first contract.
- Wiki update and rebuild prepare bounded concept extraction batches; they do not synthesize pages inside Python.

### Recent Shifts

- Full-index is explicitly concept backlog draining, not plain RAG reindexing.
- The command family now documents the full agent-orchestrated compile loop instead of only individual wiki actions.

### Open Tensions

- Fast backlog draining must still stop on quality defects.
- Report generation should summarize compiled knowledge without becoming a source of new ungrounded wiki content.

### How to Use This

Use this when choosing which command should ingest a source, compile a concept batch, drain backlog, recover wiki state, or produce a report from compiled knowledge.

### Open Questions

- How should retained ask outcomes be selected for wiki compounding?
- Which compile steps should be visible in Browse for auditability?

### Source Basis

- `vault:skills/ingest/commands/ask-sync.md`: Compound retained /ask outcomes into memory, synthesis, and wiki
- `vault:skills/ingest/commands/auto-wiki-maintenance.md`: Autonomous wiki maintenance command.
- `vault:skills/ingest/commands/ingest-url.md`: Capture one URL into the Augur vault as an Obsidian-native source card.
- `vault:skills/ingest/commands/ingest.md`: Ingest content into the Augur knowledge base.
- `vault:skills/ingest/commands/wiki-full-index.md`: Drain the wiki concept backlog through repeated update batches
- `vault:skills/ingest/commands/wiki-rebuild.md`: Prepare a concept-first extraction batch from current Augur knowledge sources.
- `vault:skills/ingest/commands/wiki-report.md`: Generate a polished "Second Brain Intelligence Report"
- `vault:skills/ingest/commands/wiki-reset.md`: Run a safe clean-slate reset for the shared wiki
- `vault:skills/ingest/commands/wiki-update.md`: Prepare an incremental concept extraction batch for sources whose checksums changed or have not yet been processed.

### Related Concepts

- [[concepts/agent-learning-compounding-pipeline]]
- [[concepts/knowledge-automation-command-loops]]

## Timeline

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/ask-sync.md
  Compound retained /ask outcomes into memory, synthesis, and wiki.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/auto-wiki-maintenance.md
  Autonomous wiki maintenance command.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/ingest-url.md
  Capture one URL into the Augur vault as an Obsidian-native source card.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/ingest.md
  Ingest content into the Augur knowledge base.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/wiki-full-index.md
  Drain the wiki concept backlog through repeated update batches.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/wiki-rebuild.md
  Prepare a concept-first extraction batch from current Augur knowledge sources.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/wiki-report.md
  Generate a polished "Second Brain Intelligence Report".

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/wiki-reset.md
  Run a safe clean-slate reset for the shared wiki.

- _at: 2026-05-03T13:41:02Z  _source: vault:skills/ingest/commands/wiki-update.md
  Prepare an incremental concept extraction batch for sources whose checksums changed or have not yet been processed.
