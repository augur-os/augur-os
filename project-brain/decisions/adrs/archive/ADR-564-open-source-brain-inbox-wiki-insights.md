---
status: Implemented
date: '2026-04-24'
deciders:
- Gur Sannikov
- Codex
related:
- ADR-270
- ADR-559
- ADR-561
hub: brain
tags:
- brain
- inbox
- ingest
- wiki
- rag
- open-source-release
superseded_by: null
---

# ADR-564: Open-Source Brain Inbox and Wiki Insights

## Context

Augur's open-source first-use journey needs a concrete local knowledge-worker outcome. Users should be able to add folders such as Desktop or Downloads, click Consume, and receive organized files, searchable context, cross-source insights, and next actions.

Existing ingest, document extraction, RAG indexing, wiki compounding, and Brain dashboard pieces are present, but folder consume is not a first-class product workflow. Binary and rich-document files also need deeper, need-based analysis so the wiki can produce new cross-source insight instead of only source summaries.

## Decision

Add a Brain Inbox and Brain Insights journey:

- Store user-configured inbox folders in runtime state.
- Expose folder scan, consume, purge-to-trash, run history, run detail, and Brain insights through MCP tools owned by the ingest skill.
- Reuse existing ingest, document understanding, RAG, and wiki compounding primitives.
- Preserve agent-orchestrated wiki compounding through retained chat outcomes, consumed files, hooks, and update flags.
- Keep compiled wiki pages concept-first and source-compounded.
- Add flat Brain pages `/brain/inbox` and `/brain/insights`.
- Harden Browse wiki cards with cleaned tags, contextual primary actions, and overflow actions.

## Consequences

The dashboard remains MCP-first and does not directly touch local files. Folder Consume can be automatic after a user click, while Purge only moves files to OS trash and never permanently deletes them.

This creates a clear open-source user journey and a durable implementation boundary for later background scheduling, richer folder policies, and release-quality wiki insight surfacing.
