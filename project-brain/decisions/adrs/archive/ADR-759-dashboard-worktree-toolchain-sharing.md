---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related: []
hub: dev
tags:
  - dashboard
  - worktree
  - pnpm
  - filesystem
  - disk-efficiency
  - cross-os
superseded_by: null
spec_file: 2026-05-16-dashboard-worktree-toolchain-sharing-design.md
plan_file: 2026-05-16-dashboard-worktree-toolchain-sharing.md
---

# ADR-759: Dashboard Worktree Toolchain Sharing

> **ADR-759 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Share `apps/dashboard/node_modules` bytes across worktrees via pnpm hardlinks (Approach A) and CoW-clone `node_modules` on worktree creation where the filesystem supports it (Approach C), preserving the existing preflight invariant that every worktree owns its own real `node_modules`.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-16-dashboard-worktree-toolchain-sharing-design.md`](../superpowers/specs/2026-05-16-dashboard-worktree-toolchain-sharing-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-16-dashboard-worktree-toolchain-sharing.md`](../superpowers/plans/2026-05-16-dashboard-worktree-toolchain-sharing.md)

## Status notes

**Implemented** (2026-05-16). Plan executed in 11 TDD tasks on branch `adr-759-dashboard-worktree-toolchain-sharing` (commits 2336ad697..a1fb75041). All 50 tests pass (16 toolchain + 34 preflight). Layer 3 real-data verification (run from a throwaway worktree off this branch) shows:

- `apps/dashboard/node_modules` materialized via CoW clone in ~22.6s preflight wall-time (clone itself sub-second; remainder is sync bootstrap + MCP gen).
- Apparent size 1360 MB, but volume free-space delta only 81 MB → **94% CoW byte-sharing** with main worktree.
- `.bin/next` present and functional.
- Net disk delta after teardown: 0 MB — confirms CoW shares are released cleanly.

**Post-merge closure** (2026-05-17). The deferred Task 11 migration is complete. Follow-up verification found that the repo-root `.npmrc` was not effective when `pnpm` was invoked from `apps/dashboard`, so the dashboard now carries its own `.npmrc` with the same hoisting directives plus `package-import-method=hardlink`, and `scripts/worktree_toolchain.py` forces `--package-import-method hardlink` on fallback installs.

All current dashboard worktrees were re-linked with `pnpm install --frozen-lockfile --force --package-import-method hardlink`. Real inode measurements after the run:

- `~/Projects/Augur`: `41791/41985` files hardlinked (**99%**), `.bin/next` present.
- `~/Projects/augur-wt-20260516-120601`: `41835/41964` files hardlinked (**99%**), `.bin/next` present.
- `~/Projects/augur-wt-20260516-234424`: `41835/41964` files hardlinked (**99%**), `.bin/next` present.
- `~/Projects/augur-wt-20260516-234933`: `41835/41964` files hardlinked (**99%**), `.bin/next` present.
- `~/Projects/Augur/.worktrees/browse-unified-card-list`: `41835/41964` files hardlinked (**99%**), `.bin/next` present.

**Proposed** (2026-05-16). Measurement-driven: probe across the four current worktrees showed pnpm hardlinking is broken (2 / 83k files in main, 0 / 41k in each of three sibling worktrees), costing ~3GB total disk for the dashboard toolchain alone with `/` at ~24GB free.

## Related

None directly — this is implementation of existing CLAUDE.md rules #28 (client-side verification), #29 (dashboard slash commands), #30 (cross-OS command surfaces), and #34 (verification proves user value). The preflight invariant being preserved was introduced alongside the original `scripts/worktree_preflight.py` design; the alignment check and CoW materialization extend that contract without weakening any existing guarantee.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected:
    - .npmrc                                                # append package-import-method=hardlink
    - apps/dashboard/.npmrc                                 # dashboard-local effective pnpm config
    - apps/dashboard/package-lock.json                       # delete (stale npm residue)
    - scripts/worktree_toolchain.py                          # new module
    - scripts/worktree_preflight.py                          # add _check_pnpm_alignment + materializer routing
    - scripts/verify_worktree_toolchain.py                   # new Layer 3 verification script
    - tests/scripts/test_worktree_toolchain.py               # new tests (16 cases)
    - tests/scripts/test_worktree_preflight.py               # +4 tests (alignment + materializer integration)
    - apps/dashboard/README.md                               # document pnpm same-volume requirement
    - docs/agent-topics/WORKFLOWS.md                         # cross-link toolchain sharing behavior
```
