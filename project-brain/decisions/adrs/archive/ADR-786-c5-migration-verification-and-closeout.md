---
status: Implemented
date: 2026-05-25
deciders:
  - gsannikov
related: [781, 782, 783, 784, 785]
hub: null
tags: [multi-brain, harness, verification, migration, closeout, validation]
superseded_by: null
spec_file: 2026-05-25-harness-layering-family-design.md
plan_file: 2026-05-25-harness-c5-migration-verification-closeout.md
---

# ADR-786: C5 — Migration Verification & Closeout

> Child of the **ADR-781** harness-layering family. Canonical design: [`2026-05-25-harness-layering-family-design.md`](../superpowers/specs/2026-05-25-harness-layering-family-design.md).

## Decision summary

The whole-family closeout: a single end-to-end verification run proving **every migration across C1–C4 landed correctly** — no data loss, no orphaned references, every client and tier correct, parity holds, and cross-client memory awareness round-trips — on **real data and real clients**. The family is "landed" only when C5 is green.

## Status notes

Implemented 2026-05-25. The family closeout is encoded in
`src/lib/brain_closeout.py` and exposed through
`project-brain/capabilities/skills/platform-admin/scripts/harness_closeout.py`.
The real-stack closeout returned `all_ok: true`: Claude, Codex, Gemini, and
OpenCode had no missing effective skills; parity preserved all project-tier
skills with no drops; the family orphan-reference scan found 0 stale migrated
path references; and tiered memory projection reported 40 records with checked
Codex and Gemini targets. The closeout also caught and drove removal of stale
`Au-vault/skills` and `private-vault/skills` references before this status
flip.

## Context

Each child carries its own per-step gate (`verify-harness`, migration harness). C5 is the **cross-family** proof the user requested: the per-child gates verify each piece as it lands; C5 verifies the assembled system. This guards against integration drift that individual children can't catch (e.g., a path moved in C1 that C3 still references, or a tier that projects correctly alone but collides once all caps are merged).

## Decision

1. **End-to-end migration audit** — confirm every migration in the family completed: vault skill canonicalization, the C1–C4 path/config moves, the parity-gated cutover, the tier-keyed memory store move. Reuse the migration harness (781 §2b) count-checks + rule-23 reference scan, family-wide.
2. **Cross-client × cross-tier verification** — `verify-harness` (781 §2a) run for every enabled client across the full Global+User+Project stack; assert non-empty, correctly-merged, precedence-honored, loads.
3. **Cross-client memory round-trip** — assert the C3 ingest/project loop works end-to-end on real clients (write in A → review-gated → visible in B).
4. **Closeout report** — a generated report naming exact URLs/clients/tiers checked, real records seen, and any remaining empty/error/stale state (rules 31/34). The family is closed only on a fully-green report.

## Completion gate

The whole-system run is green on real data + real clients: zero data loss (counts match), zero orphaned references, every client/tier correct, parity confirmed, memory round-trip proven. Anything less is a finding to fix, not to paper over.

## Consequences

**Positive:** a single authoritative proof that the core feature landed correctly; integration drift is caught before closeout. **Negative:** depends on all of C1–C4. **Neutral:** mostly assembles existing per-child gates into one family-wide run.

## Dependencies

C1, C2, C3, C4 (all must be implemented). Final ADR in the family.

## References

- ADR-781 (parent) + shared infra §2a/§2b · C1–C4 · family spec · CLAUDE.md rules 23, 28, 31, 34
