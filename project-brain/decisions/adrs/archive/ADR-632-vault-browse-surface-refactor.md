---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-600
hub: null
tags: []
superseded_by: null
spec_file: 2026-04-30-vault-browse-surface-refactor-design.md
plan_file: 2026-04-30-vault-browse-surface-refactor.md
---

# ADR-632: Vault Browse Surface Refactor

## Decision summary

Adopt a three-concept dashboard taxonomy: **App Surface** (custom product routes for real workflows under `apps/dashboard/features/pages/{app}/{surface}/page.tsx`), **Capability Profile** (generated per-skill profile rendered via `/browse/skills/{skillId}`), and **Developer Surface** (dev-only...

## Status notes

 | Flipped to Implemented per code-evidence triage 2026-05-10 — work already shipped.
