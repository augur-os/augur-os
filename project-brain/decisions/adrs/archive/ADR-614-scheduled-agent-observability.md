---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-614: Scheduled Agent Observability

## Decision summary

Make Augur the observability surface for scheduled agent work without becoming the scheduler. Native scheduling stays in each client. Add a new browse entity type `scheduled-executions` with two kinds (`native-schedule`, `internal-schedule`) and three source families (`augur-internal`,...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
