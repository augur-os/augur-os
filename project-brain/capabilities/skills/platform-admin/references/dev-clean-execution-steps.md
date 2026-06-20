# Dev Clean Execution Steps

`/dev-clean` runs a fixed set of operations in order. Each operation is idempotent and safe to repeat. The executor lives at `project-brain/capabilities/skills/platform-admin/scripts/dev_clean.py`.

## Tier 1 — Filesystem caches (default)

### Step 1: `pnpm-ignored-cache`

```text
target: apps/dashboard/node_modules/.ignored
```

pnpm relocates hoisted packages here when an upgrade obsoletes the prior layout. The tree is never read by Node or pnpm at runtime; it exists only to enable rollback. After install completes, it is pure waste — observed to grow to 400+ MB and 18K+ files in active monorepos.

### Step 2: `duplicate-mcp-venv`

```text
target: src/mcp/.venv
```

A duplicate Python virtualenv left over from local experimentation. The project uses the root `.venv` driven by `uv sync` at repo root. `src/mcp/.venv` is shadowed by the root venv at PYTHONPATH resolution time and serves no purpose. If a user genuinely needs an isolated MCP venv they will recreate it explicitly.

### Step 3: `pycache-purge`

```text
targets: every __pycache__/ directory under project-brain/, src/, scripts/
```

Python bytecode caches. `.gitignore` already excludes them, but the CPython interpreter writes them next to source files on every import. They accumulate on disk and never self-clean. The interpreter will regenerate only what the next run actually needs.

### Step 4: `tool-caches`

```text
targets: .pytest_cache/, .ruff_cache/
```

Test and lint runner caches. Both are regenerated on the next `pytest` / `ruff` run. Removing them costs a single first-run rebuild penalty and otherwise frees ~1–2 MB.

### Step 5: `stale-dashboard-worktree-caches`

```text
targets: inactive get_cache_dir()/dashboard-worktree-* directories
```

External Next/Turbopack caches for dashboard worktree dev servers. These caches
are fully regenerable on the next `/dev-build` or dashboard visit. The active
main checkout cache lives in `get_cache_dir()/dashboard/` and is never touched.
Before removing a worktree cache, `/dev-clean` reads `next/dev/lock` and
skips the cache when that lock points to a live Next PID.

## Tier 2 — `.git` compaction + pnpm store pruning (opt-in via `--include-git` or `--all`)

### Step 6: `git-lfs-prune`

```bash
git lfs prune --verify-remote
```

Removes local LFS objects that are no longer referenced by any commit reachable from a branch, tag, or stash. `--verify-remote` adds the constraint that each pruned object must already exist on the LFS remote — this is the safety floor that prevents data loss. Observed reclaim on the Augur repo: ~165 MB of orphaned LFS objects from old branch history.

Skips cleanly if `git-lfs` is not installed.

### Step 7: `git-gc`

```bash
git gc --prune=now --quiet
```

Repacks loose objects, consolidates pack files, and removes objects unreachable from any ref or reflog older than 0 seconds. By definition this cannot affect anything reachable from a branch, tag, HEAD, or stash. Typical reclaim: 30–50% of `.git/objects` size on a repo that has accumulated many small packs.

### Step 8: `pnpm-store-prune`

```bash
pnpm store prune
```

Removes unreferenced package versions from the global pnpm content-addressable store. The installed `node_modules` trees in current worktrees are not removed; if a future install needs a package version that was pruned, pnpm re-downloads it from the registry. The operation runs through `pnpm` when present and falls back to `corepack pnpm` when pnpm is not directly on `PATH`.

Dry-run first asks pnpm for `store prune --dry-run`. Current pnpm 10 releases do not expose that flag, so `/dev-clean --dry-run --all` reports the current store size as an upper-bound estimate and leaves the store untouched.

## Safety Properties

* **No target outside the explicit allow-list.** The executor enumerates targets by literal path or the narrow `dashboard-worktree-*` cache namespace; there is no broad recursive sweep that could escape the intended scope.
* **Repo-scoped execution with declared external cache/store targets.** `REPO_ROOT` is derived from the script's own path; most Tier 1 paths stay under the repo, worktree dashboard caches stay under `get_cache_dir()`, git operations stay under `.git`, and the only global Tier 2 target is pnpm's own store path resolved by `pnpm store path`.
* **Dry-run is a true preview.** `--dry-run` walks the same target paths and reports the same bytes/files figures the executing run would reclaim, without invoking any delete operation.
* **Git operations use remote verification.** Both `git lfs prune --verify-remote` and `git gc --prune=now` are constrained to objects that are either already pushed (LFS) or unreachable from any ref/reflog (gc). Neither can remove reachable or unpushed work.
* **pnpm owns pnpm-store deletion.** `/dev-clean` does not glob through the store; it delegates deletion to `pnpm store prune`, which removes only unreferenced store entries.
* **Idempotent.** Re-running on a clean tree reports zero across every operation.

## Reading the Report

```text
OPERATION           TIER  TARGETS   RECLAIMED  FILES
pnpm-ignored-cache  T1          1   391.6 MB   18559
duplicate-mcp-venv  T1          1    33.8 MB    1015
pycache-purge       T1         87    22.7 MB    1828
tool-caches         T1          2     1.1 MB      54
stale-dashboard-worktree-caches T1   5     2.4 GB    4730
git-lfs-prune       T2          1   165.0 MB       —
git-gc              T2          1    42.0 MB       —
pnpm-store-prune    T2          1     2.4 GB  120000
TOTAL               --         94     3.0 GB  141456
```

* **TARGETS** — number of distinct paths removed (e.g. how many `__pycache__` directories).
* **RECLAIMED** — bytes freed; for git operations this is the `.git` directory size delta.
* **FILES** — file count delta (git operations leave this blank since they collapse loose objects into packs rather than removing individual files).
* Operations skipped for environmental reasons (no git, no LFS installed, target missing) show a `SKIPPED` row with the reason.

## Pairing with Other Commands

* Run as a preface to `/dev-merge full` to keep `.git` and the pnpm store lean over time — Tier 2 is appropriate here because everything is being pushed anyway and dependency downloads are acceptable.
* Run after a major dependency upgrade (`pnpm` workspace bump, `uv` lock refresh) — `.ignored` and `__pycache__` accumulate fastest here.
* Do not run during an active `/dev-build` — file locks on Windows will cause Tier 2 to fail noisily (Tier 1 is fine).
