---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related:
  - ADR-759
hub: dev
tags:
  - dev-clean
  - pnpm
  - disk-efficiency
  - tier-2
superseded_by: null
spec_file: 2026-05-16-dev-clean-pnpm-store-prune-design.md
plan_file: 2026-05-16-dev-clean-pnpm-store-prune.md
---

# ADR-761: /dev-clean pnpm-store-prune

> **ADR-761 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Add `pnpm-store-prune` as a Tier 2 operation in `/dev-clean` so `--include-git` / `--all` invocations reclaim unreferenced versions from the global pnpm content-addressable store — measured ~2.4 GB on a long-lived dev machine.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-16-dev-clean-pnpm-store-prune-design.md`](../superpowers/specs/2026-05-16-dev-clean-pnpm-store-prune-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-16-dev-clean-pnpm-store-prune.md`](../superpowers/plans/2026-05-16-dev-clean-pnpm-store-prune.md)

## Status notes

**Implemented** (2026-05-16). Added `pnpm-store-prune` as a Tier 2 `/dev-clean` operation, wired into `--include-git` / `--all`, documented the network re-download trade-off, and covered pnpm/corepack, dry-run fallback, timeout, nonzero exit, parsing, and dispatch behavior in `tests/scripts/test_dev_clean_pnpm_store.py`. Real-data validation on this machine ran `/dev-clean --all` and produced a `pnpm-store-prune` row reclaiming 643.4 MB / 36,370 files from the real pnpm store; later validation installs repopulated the store as expected.

Historical gap context: during ADR-759 verification, manual `pnpm store prune` reclaimed 2,461 MB on this machine (store dropped 2,967 MB → 0; volume free +2,461 MB), with zero impact on running worktrees (APFS clones survive store deletion — block references persist). `/dev-clean` is the canonical "reclaim regenerable artifacts" surface but did not invoke pnpm store prune, leaving the largest single source of reclaimable disk one command away from where users look. Tier 2 fits because the next `pnpm install` requires network re-downloads, violating Tier 1's "regenerable from local state alone" guarantee.

The implementation landed with one new function (`_prune_pnpm_store`), one Tier 2 dispatch entry, focused tests, and the `/dev-clean` command/reference documentation updates.

## Related

- ADR-759 (sibling work: dashboard worktree toolchain sharing — verification surfaced this gap)
- CLAUDE.md rule #19 (slash-command-driven test/build)
- CLAUDE.md rule #34 (verification proves user value)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected:
    - shared-vault/skills/platform-admin/scripts/dev_clean.py     # add _prune_pnpm_store + Tier 2 entry
    - shared-vault/skills/platform-admin/commands/dev-clean.md    # new row in "What Gets Reclaimed" table
    - tests/scripts/test_dev_clean_pnpm_store.py                  # new (6 unit tests)
```
