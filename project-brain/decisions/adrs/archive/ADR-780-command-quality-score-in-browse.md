---
status: Implemented
date: 2026-05-24
deciders:
- gsannikov
related:
- ADR-741
hub: null
tags:
- browse
- dashboard
- commands
- quality
- score
- scorer
superseded_by: null
spec_file: 2026-05-24-command-quality-score-browse-design.md
plan_file: 2026-05-24-command-quality-score-browse.md
---


# ADR-780: Command Quality Score in Browse

> **ADR-780 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Give every command a docs+wiring health score (0-100, tier A–F) on its Browse card with a score filter, plus a side `KPI ✓/✗` chip on the command-KPI-tested commands — reusing the existing skills score pipeline rather than a bespoke panel.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-24-command-quality-score-browse-design.md`](../superpowers/specs/2026-05-24-command-quality-score-browse-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-24-command-quality-score-browse.md`](../superpowers/plans/2026-05-24-command-quality-score-browse.md)

## Status notes

Implemented 2026-05-24 — command docs+wiring scoring is live in `src/lib/command_scorer.py`, Browse command metadata is enriched through the MCP Browse index, and the dashboard command view now renders `Quality` / `Docs` / `Wiring` / `KPI` signals on the existing shared card and detail surfaces. Real-data validation scored 114 discovered commands, enriched 95 of 122 Browse command records, and verified `/browse` at `http://localhost:3002/browse` with desktop/mobile Playwright screenshots and a working Quality=A filter.

Accepted 2026-05-24 — design and 8-task TDD plan approved in the brainstorming session. Skills already filter by score in Browse; this extends the same `qualityTier`/`qualityScore` pipeline to commands via a new `src/lib/command_scorer.py`, a `_populate_command_enrichment` hook in `browse/index.py`, and a commands-view score filter + KPI chip. Ready for `/adr implement ADR-780` in a fresh session.

## Related

- ADR-741 — Skill Resolvability and MECE Coverage Audit (the check-resolvable audit reused as a wiring signal).
