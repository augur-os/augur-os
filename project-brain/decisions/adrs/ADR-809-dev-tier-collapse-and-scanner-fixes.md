---
status: Accepted
date: 2026-06-09
deciders:
  - gsannikov
related:
  - ADR-802
  - ADR-491
hub: null
tags:
  - browse
  - dev-tier
  - scanners
  - inventory
superseded_by: null
spec_file: 2026-06-09-augur-dev-tier-collapse-design.md
plan_file: 2026-06-09-dev-tier-collapse.md
---

# ADR-809: Developer-tier collapse + dev-scanner fixes

> **ADR-809 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

The 11 developer Browse categories collapse into 3 presentation groups — CAPABILITIES, DIAGNOSTICS, REFERENCE — kept in-place inside the Browse "More ▾" Dev cluster (no third surface, no data-model merge); the `scripts` scanner indexes only project-root paths and skips `__init__.py`; and the `ai-artifact-inventory` classifier labels artifacts by provenance (`generated` for client-export projections, `source` for repo-authored files, `unknown` only when genuinely unrecognized).

## Spec (canonical)

- [`docs/superpowers/specs/2026-06-09-augur-dev-tier-collapse-design.md`](../superpowers/specs/)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-06-09-dev-tier-collapse.md`](../superpowers/plans/)

## Status notes

Accepted 2026-06-09. Workstream 5 of the "categorize around skills" refactor; closes the last parked §6 item from the parent spec.

## Related

- ADR-802 (hub removal — establishes the two-surface model this decision honors)
- ADR-491 (config-driven pages)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - "Browse JourneyGroup values: intent, wiring, orchestration (replaced by capabilities, reference; diagnostics retained)"
  files_affected:
    - src/lib/index/_scanners_structural.py
    - src/lib/ai_artifact_inventory.py
    - apps/dashboard/lib/browse/types.ts
```
