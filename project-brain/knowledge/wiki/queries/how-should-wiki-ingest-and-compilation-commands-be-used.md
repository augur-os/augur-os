---
title: How should Wiki Ingest And Compilation Commands be used?
summary: A reusable answer for applying [[concepts/wiki-ingest-and-compilation-commands]].
tags:
- how-should-wiki-ingest-and-compilation-commands-be-used
- wiki-ingest-and-compilation-commands
- agent-learning-compounding-pipeline
- knowledge-automation-command-loops
- query
- command
- ingest
- compilation
related:
- '[[wiki-ingest-and-compilation-commands]]'
- '[[agent-learning-compounding-pipeline]]'
- '[[knowledge-automation-command-loops]]'
created: '2026-05-03T13:41:02Z'
_page_type:
- e
- q
- r
- u
- y
_hub:
- a
- c
- d
- m
- n
- o
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
_source_fingerprint:
- '0'
- '1'
- '2'
- '3'
- '4'
- '5'
- '6'
- '7'
- '8'
- '9'
- a
- b
- c
- d
- e
- f
_compiler_version:
- '-'
- '3'
- a
- c
- e
- i
- l
- n
- o
- p
- r
- t
- v
_updated:
- '-'
- '0'
- '1'
- '2'
- '3'
- '4'
- '5'
- '6'
- ':'
- T
- Z
compiler_version: concept-article-v3
hub: command
page_type: query
source_fingerprint: f54edc12f9bb05325d00f67ed996aa493928f05f69cb3f75950ae6db0a500665
sources:
- vault:skills/ingest/commands/ask-sync.md
- vault:skills/ingest/commands/auto-wiki-maintenance.md
- vault:skills/ingest/commands/ingest-url.md
- vault:skills/ingest/commands/ingest.md
- vault:skills/ingest/commands/wiki-full-index.md
- vault:skills/ingest/commands/wiki-rebuild.md
- vault:skills/ingest/commands/wiki-report.md
- vault:skills/ingest/commands/wiki-reset.md
- vault:skills/ingest/commands/wiki-update.md
updated: '2026-05-03T13:41:02Z'
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
- '[[concepts/wiki-ingest-and-compilation-commands]]'
_relates_to:
- '[[agent-learning-compounding-pipeline]]'
- '[[command]]'
- '[[compilation]]'
- '[[ingest]]'
- '[[knowledge-automation-command-loops]]'
- '[[query]]'
- '[[wiki-ingest-and-compilation-commands]]'
---


# How should Wiki Ingest And Compilation Commands be used?

## Summary

A reusable answer for applying [[concepts/wiki-ingest-and-compilation-commands]].

## Answer

Wiki ingest and compilation commands capture raw sources, prepare concept batches, apply agent synthesis, reindex compiled pages, and report knowledge health without hand-writing wiki pages.

Use [[concepts/wiki-ingest-and-compilation-commands]] as the source-backed synthesis page before returning to raw evidence.

## Evidence

- `vault:skills/ingest/commands/ask-sync.md`: Compound retained /ask outcomes into memory, synthesis, and wiki
- `vault:skills/ingest/commands/auto-wiki-maintenance.md`: Autonomous wiki maintenance command.
- `vault:skills/ingest/commands/ingest-url.md`: Capture one URL into the Augur vault as an Obsidian-native source card.
- `vault:skills/ingest/commands/ingest.md`: Ingest content into the Augur knowledge base.
- `vault:skills/ingest/commands/wiki-full-index.md`: Drain the wiki concept backlog through repeated update batches
- `vault:skills/ingest/commands/wiki-rebuild.md`: Prepare a concept-first extraction batch from current Augur knowledge sources.
- `vault:skills/ingest/commands/wiki-report.md`: Generate a polished "Second Brain Intelligence Report"
- `vault:skills/ingest/commands/wiki-reset.md`: Run a safe clean-slate reset for the shared wiki
- `vault:skills/ingest/commands/wiki-update.md`: Prepare an incremental concept extraction batch for sources whose checksums changed or have not yet been processed.

## Related

- [[concepts/wiki-ingest-and-compilation-commands]]
- [[concepts/agent-learning-compounding-pipeline]]
- [[concepts/knowledge-automation-command-loops]]
