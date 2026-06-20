---
status: Implemented
date: 2026-05-10
deciders:
  - gsannikov
related:
  - ADR-560
  - ADR-564
hub: command
tags:
  - wiki
  - ingest
  - daemon
  - knowledge-compounding
  - cross-platform-memory
  - token-economy
superseded_by: null
spec_file: 2026-05-10-wiki-signal-priority-design.md
plan_file: 2026-05-10-wiki-signal-priority.md
---

# ADR-607: Wiki Signal Priority and Batched Update

> **ADR-607 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Introduce tier-tagged scanner output, a client-neutral memory/session adapter, vault-mtime promotion for recent writes, a single token-conscious daily routine, and a skip-if-unchanged guard so the wiki compounder runs daily on a fixed token budget across macOS and Windows. All changes are bundled because they are mutually reinforcing — the priority tags only matter once the configured client sources surface them, the mtime promotion only matters once the daily routine reads them, and the skip-if-unchanged guard is the cost ceiling that makes the whole thing affordable.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-10-wiki-signal-priority-design.md`](../superpowers/specs/2026-05-10-wiki-signal-priority-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-10-wiki-signal-priority.md`](../superpowers/plans/2026-05-10-wiki-signal-priority.md)

## Status notes

This index ADR was reconstructed on 2026-05-12 from the existing spec + plan to align with the new thin-index ADR workflow (Codex's original `/adr write` runs in this batch wrote the spec and plan but did not generate the markdown index file). No design content was changed in reconstruction.

## Related

- ADR-560 — Semantic Wiki Page Compiler
- ADR-564 — Open-Source Brain Inbox and Wiki Insights
