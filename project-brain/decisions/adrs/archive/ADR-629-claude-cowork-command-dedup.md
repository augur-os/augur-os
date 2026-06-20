---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-442
hub: null
tags: []
superseded_by: null
spec_file: 2026-04-27-claude-cowork-command-dedup-design.md
plan_file: 2026-04-27-claude-cowork-command-deduplication.md
---

# ADR-629: Claude/Cowork Command Dedup

## Decision summary

Establish a single-owner policy: Claude Code owns project-local slash commands via `.claude/commands`; Cowork owns the Claude Desktop plugin install (MCP connector, plugin skills, and any non-overlapping Cowork-only commands). Update the Cowork plugin-pack profile to omit `_CORE_COMMANDS` whose...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
