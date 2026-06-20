---
status: Implemented
date: '2026-04-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- daemon
- codex
- dev-loops
- scheduling
superseded_by: null
spec_file: 2026-04-12-dev-loops-codex-migration-design.md
plan_file: 2026-04-12-dev-loops-codex-migration.md
---

# ADR-582: Dev Loops Codex Migration

## Decision summary

Move all slower scheduled `dev-loops` execution to local Codex automations. The daemon retains only fast self-heal sensing (`self-heal-fast`) and event capture / queue append. Augur becomes the observability and manifest source of truth.

## Status notes

 | Flipped to Implemented 2026-05-10 per pass-2 code-evidence triage.
