---
date: 2026-05-16
status: Draft
deciders:
  - gsannikov
related:
  - ADR-759 dashboard worktree toolchain sharing (sibling work that surfaced the gap)
  - CLAUDE.md rule #19 (all test/build runs through slash commands and loops)
  - CLAUDE.md rule #34 (verification proves user value, not mechanical pass)
---

# /dev-clean pnpm-store-prune — Design

## Goal

Add `pnpm-store-prune` to `/dev-clean` Tier 2 so the command reclaims unreferenced package versions from the global pnpm content-addressable store (`~/Library/pnpm/store/` on macOS, equivalents on Linux/Windows). Today `/dev-clean` reclaims caches inside the repo tree but not the global pnpm store, which on a long-lived dev machine accumulates 1–3 GB of orphaned package versions that no current worktree references.

Concrete target: `/dev-clean --all` reclaims the pnpm store orphans alongside its existing Tier 2 git-gc work, with the same `--dry-run` audit semantics and the same JSON output shape. No flag changes; the existing `--include-git` / `--all` flag enables the new target.

## Problem

ADR-759 verification surfaced a measured 2,461 MB reclaim from a single `pnpm store prune` invocation on a working dev machine (store dropped 2,967 MB → 0 MB; volume free went from 22,286 MB to 24,747 MB). The pnpm store ratchets monotonically as `pnpm install` runs across worktrees — every version of every transitive dependency that has ever been installed remains until prune. `/dev-clean` is the canonical "reclaim regenerable artifacts" surface, but it does not invoke `pnpm store prune` and so leaves the largest single source of reclaimable disk on the table.

A user looking at high disk pressure is intuitively drawn to `/dev-clean`. Without this addition, they see the table report ~400 MB Tier 1 + small Tier 2, run it, and don't realize an order of magnitude more disk is sitting one command away.

## Non-goals

- **Not auto-pruning in Tier 1.** `pnpm store prune` is partially irreversible: the next `pnpm install` (in any worktree) must re-download packages from the registry to rebuild the store. Tier 1 is "regenerable from local state alone"; this requires network. Tier 2 fits.
- **Not adding `--prune-store-only` or new flags.** The existing `--include-git` / `--all` opens Tier 2; adding a third tier or third flag is unnecessary surface.
- **Not changing the pnpm store location.** Platform defaults stay (`~/Library/pnpm/store/`, `%LOCALAPPDATA%\pnpm\store\`, `~/.local/share/pnpm/store/`).
- **Not modifying pnpm-lock.yaml or any per-worktree state.** Store prune only touches the global content-addressable store.

## Approach

Add one entry to the existing Tier 2 list:

| Tier | Operation | Target | Why safe to remove |
|---|---|---|---|
| 2 | `pnpm-store-prune` | `~/Library/pnpm/store/v10/files/` orphans | `pnpm store prune` only removes versions no current `node_modules` references; next `pnpm install` re-downloads from registry |

Implementation surface (engine):
- The dev-clean script (Python, per CLAUDE.md rule #30 cross-OS shell-neutrality) gets one new operation function: `_prune_pnpm_store(dry_run: bool) -> ReclaimReport`.
- Dry-run uses `pnpm store prune --dry-run` (if pnpm supports it) or falls back to measuring store size, calling prune, and computing delta. Real-run executes `pnpm store prune` and parses its `Removed N files / N packages` summary.
- The function returns the standard `ReclaimReport` shape used by other Tier 2 operations, so the table output and JSON output gain the row automatically.
- Wired into the Tier 2 dispatch table so `--include-git` / `--all` includes it.

Cross-OS:
- macOS: `pnpm store prune` works against `~/Library/pnpm/store/`.
- Linux: works against `~/.local/share/pnpm/store/`.
- Windows: works against `%LOCALAPPDATA%\pnpm\store\`.

Pnpm handles the platform detection; we just shell out via the resolved `pnpm` binary (or `corepack pnpm` if pnpm isn't on PATH).

## Architecture

`/dev-clean` is a Python script today (e.g. `shared-vault/skills/platform-admin/scripts/dev_clean.py` or wherever the dispatch lives). It already iterates a list of `Operation` records — adding pnpm-store-prune is one more record:

```
TIER_2_OPERATIONS = [
    git_lfs_prune,
    git_gc,
    pnpm_store_prune,   # NEW
]
```

Each operation has `name`, `description`, `dry_run_fn`, `apply_fn`, and `safety_check_fn`. The new entry's safety check confirms pnpm is on PATH (or corepack is); falls through with a clear "pnpm not found" report row if neither is available.

## Invariants

Preserved:
1. `--dry-run` never mutates state, including the pnpm store.
2. Tier 1 operations remain the "no-network-needed regeneration" guarantee — the new operation is in Tier 2 explicitly.
3. The existing JSON output shape and table columns are unchanged; the new row joins the existing list.
4. The "refuses to operate outside the repo root" check stays — even though the pnpm store lives outside the repo, the dev-clean script's working directory remains constrained to the repo.

New:
5. Tier 2 includes pnpm-store-prune by default when `--include-git` / `--all` is passed. No opt-out flag for it; if the user doesn't want pnpm pruned, they should not pass `--include-git`. (Future split could add `--include-git-only` if demand emerges; not in scope here.)

## Data flow

### Event 1: `/dev-clean --dry-run --all`

```
dev-clean.py --dry-run --all
  ├─ tier 1 ops (existing): report bytes for .ignored, .venv shadow, __pycache__, tool caches
  ├─ tier 2 git_lfs_prune --dry-run (existing)
  ├─ tier 2 git_gc --dry-run (existing)
  └─ tier 2 pnpm_store_prune --dry-run (NEW)
      └─ run `pnpm store prune --dry-run` (if supported), parse "Would remove N files / N packages"
      └─ OR measure current store size as a conservative upper bound
Result: table row "pnpm-store-prune | ~N MB | dry-run"
```

### Event 2: `/dev-clean --all`

```
dev-clean.py --all
  ├─ tier 1 ops apply (existing)
  ├─ tier 2 git_lfs_prune apply (existing)
  ├─ tier 2 git_gc apply (existing)
  └─ tier 2 pnpm_store_prune apply (NEW)
      └─ `pnpm store prune` → parses "Removed N files / N packages"
      └─ measure df before/after for the volume containing the store
Result: table row "pnpm-store-prune | N MB | reclaimed (volume delta: M MB)"
```

### Behavioral note

`pnpm store prune` is safe even with a running dev server because APFS `clonefile()` clones in `node_modules` survive store deletion — block references persist independently of the source. See [[project-pnpm-store-prune-safe-mid-session]]. On non-CoW filesystems (ext4, NTFS) where hardlinks back to the store may exist, deleting a store file decrements its hardlink count; the node_modules hardlink keeps the bytes alive. Same end state, different mechanism.

## Error handling

| Failure | Detection | Response |
|---|---|---|
| pnpm not on PATH | `shutil.which("pnpm")` returns None | Try `corepack pnpm`. If still missing, emit a Tier 2 row with `skipped: pnpm not found` and a remediation hint. Do NOT fail the whole `/dev-clean` run. |
| pnpm store prune exits non-zero | subprocess return code | Emit Tier 2 row with `failed: <pnpm stderr first 200 chars>`. Continue with other Tier 2 ops. |
| pnpm store prune times out | subprocess timeout (default 300s) | Emit Tier 2 row with `failed: timeout`. Continue. |
| Pnpm version doesn't support `--dry-run` for store prune | older pnpm < 10 | Dry-run measures current store size as the upper-bound reclaim estimate. Real run still works (`pnpm store prune` is universal). |
| Volume-delta measurement returns negative | rare disk-pressure mid-prune | Report the raw "Removed N packages" count + a "volume delta unavailable" note. |

## Cross-OS behavior

Pure Python implementation, pnpm handles the platform-specific store path resolution. No `.ps1` / `.sh` adapter needed.

| Step | macOS | Linux | Windows |
|---|---|---|---|
| Resolve pnpm | `shutil.which("pnpm")` | same | same (handles `.cmd` / `.exe`) |
| Locate store | `pnpm config get store-dir` | same | same |
| Run prune | `pnpm store prune` | same | same |
| Measure delta | `os.statvfs` (POSIX) | same | `shutil.disk_usage` (cross-platform fallback) |

## Testing strategy

Three layers per CLAUDE.md rules #19 (loops) and #34 (real-data value).

### Layer 1 — Unit tests

For the `_prune_pnpm_store` function with mocks:
- `pnpm not on PATH and corepack not on PATH` → returns `skipped` report
- `pnpm exits 0` with stdout `Removed 100 files\nRemoved 5 packages\n` → returns `reclaimed` report with parsed counts
- `pnpm exits non-zero` → returns `failed` report with stderr captured
- `pnpm times out` → returns `failed: timeout` report
- `--dry-run` mode invokes `pnpm store prune --dry-run` (if supported) or measures store size as fallback

### Layer 2 — Integration test

A pytest fixture creates a tmp pnpm store with synthetic content-addressable files, runs `pnpm store prune` via the new function, asserts the bytes were reclaimed and the report shape matches the existing `ReclaimReport` schema.

### Layer 3 — Real-data verification (CLAUDE.md rule #34)

Run `/dev-clean --dry-run --all` on the dev machine; capture the table. Run `/dev-clean --all`; capture the table. Diff the reported `pnpm-store-prune` row against the actual `df` delta — they should match within rounding. Concrete real-data evidence: on this machine during ADR-759 the manual prune reclaimed 2,461 MB; the wired `/dev-clean` invocation should report the same magnitude on the next run.

### Out of scope

- Pruning peer-dependency metadata caches (`~/.npm/_cacache/` if it exists alongside pnpm). That's an npm artifact, not pnpm.
- Pruning the pnpm package index (`~/Library/pnpm/store/v10/index/`). That's small and pnpm regenerates it on demand.

## Migration

None — this is purely additive. Existing `/dev-clean` invocations behave identically; only `/dev-clean --all` (or `/dev-clean --include-git`) gets the new row. No flag changes, no config changes, no breaking changes to the JSON output (only adds rows).

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| User runs `/dev-clean --all` then `pnpm install` and is surprised by network re-downloads | Medium | The Tier 2 docs warn: "After `/dev-clean`, the next `pnpm install` may take longer" — extend it to mention pnpm-store-prune specifically. |
| Store grows fast in CI environments where each job creates throwaway packages | Low (CI is a separate concern from dev-clean) | CI typically runs in fresh containers where store growth doesn't accumulate. Out of scope. |
| User on slow network experiences painful 30+ second re-download after first `pnpm install` post-prune | Medium | Documented trade-off. Tier 2 is opt-in. User can choose. |
| Pnpm changes its store layout in a future version | Low | `pnpm store prune` is pnpm's own command; layout changes don't affect the user-facing CLI. |
