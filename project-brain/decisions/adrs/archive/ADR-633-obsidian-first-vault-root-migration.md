---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-602
hub: null
tags: []
superseded_by: null
spec_file: 2026-05-02-obsidian-first-vault-root-migration-design.md
plan_file: 2026-05-03-obsidian-first-vault-root-migration.md
---

# ADR-633: Obsidian-First Vault Root Migration

## Decision summary

Restrict the vault root to `inbox/`, `notes/`, `sources/`, `wiki/`, `skills/`, `drafts/`, `archive/`, and `config/`. Use `drafts/` (not `_drafts/`) and keep both `drafts/` and `archive/` tracked in git but excluded from normal discovery, `/ask`, wiki compounding, dashboards, MCP registration,...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
