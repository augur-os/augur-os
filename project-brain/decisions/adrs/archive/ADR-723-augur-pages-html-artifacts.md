---
status: Implemented
date: '2026-05-10'
deciders:
- gsannikov
related:
- ADR-727
- ADR-728
hub: command
tags:
- dashboard
- page-system
- browse
- artifacts
- mcp-pages
superseded_by: null
spec_file: 2026-05-10-augur-pages-html-artifacts-design.md
plan_file: 2026-05-10-augur-pages-html-artifacts.md
---

# ADR-723: Augur Pages — HTML Artifacts

## Decision summary

Treat dashboard pages as HTML artifacts produced from a structured pipeline (page-as-blocks) rather than ad-hoc TSX, so GUI and agent surfaces converge on `/api/mcp/tool`. Every HTML thing the user can read becomes a first-class browseable, pinnable, openable object under one ViewMode. Static HTMLs...

## Status notes

Index ADR reconstructed on 2026-05-12 from the existing spec + plan to align with the new thin-index ADR workflow (the original `/adr write` run that produced this ADR's spec and plan did not generate the markdown index file). No design content was changed in reconstruction. Three ADRs touch `BROWSE_CATEGORIES`: ADR-727 (renames `scheduled-executions` → `background-routines`), ADR-728 (adds `journey_group` + `journey_order` schema and reserves `journey_group: knowledge, journey_order: 3` for this ADR's `pages` category), and this ADR (adds the new `pages` ViewMode). Implementation must honor ADR-728's reserved placement regardless of merge order.
