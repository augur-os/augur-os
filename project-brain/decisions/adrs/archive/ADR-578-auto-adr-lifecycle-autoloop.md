---
status: Cancelled
date: '2026-04-02'
deciders:
- Gur Sannikov
related: []
hub: adaptive
tags:
- autoloop
- adr
- hardening
- automation
- ops-protocol
superseded_by: null
spec_file: 2026-04-02-auto-adr-lifecycle-design.md
plan_file: 2026-04-02-auto-adr-lifecycle.md
---

# ADR-578: Auto ADR Lifecycle Autoloop

## Decision summary

Add `auto-adr-lifecycle` as a tier-3 autoloop in the `hardening` loop, with a single ops module (`adr_lifecycle_ops.py`) implementing `scan()` and `fix()` per `src.lib.ops_protocol`. Delete `auto-orphan-plans` (and its ops module under `skills/ai/scripts/ops/orphan_plans.py`) entirely.

## Status notes

 | Cancelled 2026-05-10 — no adr_lifecycle_ops.py module exists; only test fixtures reference the name. Precedent: ADR-641 cancelled on same grounds.
