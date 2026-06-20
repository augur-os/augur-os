---
status: Cancelled
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-559
hub: null
tags: []
superseded_by: null
spec_file: 2026-05-10-obsidian-native-ingest-url-wiki-mvp-design.md
plan_file: 2026-05-10-obsidian-native-ingest-url-wiki-mvp.md
---

# ADR-624: Obsidian-Native Ingest URL Wiki MVP

## Decision summary

Promote the staged `obsidian` skill into live `skills/obsidian` (read, write, search, status, scaffold, convert) as the MVP browsing/editing layer for source cards and compiled wiki pages. Add a focused `ingest-url` MCP mutation on the live `ingest` skill that captures one markdown source card per...

## Status notes

 | Flipped to Accepted 2026-05-10 — concrete pending deliverable confirmed by code-evidence triage. | Spec + plan brainstormed 2026-05-10. | Cancelled 2026-05-10 — Track A duplicated the existing `vault` skill at ~/Projects/Au-vault/skills/vault/ (the subagent missed it because it searched only shared-vault/skills). Track B (ingest-url MCP tool) was the only genuine value-add and is promoted to a fresh ADR. The original spec+plan files travel into the archive zip as historical record.
