---
date: 2026-05-16
status: Draft
deciders:
  - gsannikov
related:
  - CLAUDE.md rule #28 (client-side verification)
  - CLAUDE.md rule #29 (dashboard slash commands)
  - CLAUDE.md rule #30 (cross-OS command surfaces)
  - CLAUDE.md rule #34 (verification proves user value)
---

# Dashboard Worktree Toolchain Sharing — Design

## Goal

Stop duplicating the dashboard's `node_modules` (~1.5GB main, ~767MB each worktree) every time a new worktree is created. After this design ships: `apps/dashboard/node_modules` is per-worktree (preserving the existing preflight invariant), but the *bytes* are shared at the filesystem layer via pnpm hardlinks, and *new worktree creation* skips the install step entirely on filesystems that support copy-on-write.

Concrete target: total disk usage for the dashboard toolchain across all worktrees drops from ~3GB (4 worktrees today, measured) to ~200MB (4 × ~50MB metadata, estimated — Layer 3 verification will confirm the per-worktree metadata footprint). New worktree creation goes from ~30-60s of `pnpm install` (estimated from current behavior) to ~2s on APFS/btrfs/ReFS (estimated), and to ~5-10s on filesystems without CoW (estimated — still much faster than today because hardlinks replace network downloads and file copies). All timing and metadata estimates are validated by Layer 3 of the testing strategy.

## Problem

A `pnpm install` in any worktree today materializes ~41k–83k files as full copies inside `apps/dashboard/node_modules`. The pnpm content-addressable store at `~/Library/pnpm/store/` is supposed to back this with hardlinks, but it isn't: a probe across the four current worktrees shows **2 hardlinks in main, 0 in the others**. Every worktree therefore pays full disk cost. With `df` reporting ~24GB free on the system volume, this is a real and growing constraint.

Two related artifacts compound the problem:

- A stale `apps/dashboard/package-lock.json` (504KB) sits next to the pnpm-managed tree, suggesting prior mixed-tool usage that may have contributed to the broken hardlinking.
- `scripts/worktree_preflight.py` explicitly **blocks** `node_modules` from being a symlink pointing outside the worktree root. The most obvious workaround ("just symlink to a shared install") is therefore off the table without a policy change.

## Non-goals

- **No conversion to a pnpm workspace** (no root `pnpm-workspace.yaml`). Downstream scripts and the existing preflight contract assume the dashboard is standalone; flipping that is a larger architectural change with unrelated risk.
- **No shared mutable `node_modules`**. The preflight invariant (each worktree owns its own real `node_modules`) is preserved, not weakened. Shared-mutable designs were considered and rejected — see *Approaches considered*.
- **No override of pnpm's default store-dir**. The platform-standard location (`~/Library/pnpm/store/` on macOS, `%LOCALAPPDATA%\pnpm\store\` on Windows, `~/.local/share/pnpm/store/` on Linux) stays.
- **No new ADR**. This is implementation of existing rules (#28, #29, #30, #34), not a new architectural decision.

## Approaches considered

**A. Fix pnpm to actually hardlink from its content-addressable store.** Each worktree keeps its own `node_modules` tree, but every file inside is a hardlink to the single canonical copy in the store. This is what pnpm is supposed to do by default; it's not happening today because of a configuration mismatch (likely cross-volume store, or a missing `package-import-method=hardlink` directive). **Chosen as the universal core**.

**B. Single shared `node_modules`, symlinked into every worktree.** One canonical install at a runtime path; each worktree's `apps/dashboard/node_modules` is a symlink. Smallest disk footprint (~50MB total instead of ~200MB), but: (1) requires weakening the preflight guard; (2) introduces shared-mutable state where two `pnpm install`s or two `next dev` processes can race on `node_modules/.cache`; (3) needs a lockfile-divergence detector to detach worktrees on demand. **Rejected.** The marginal disk saving (~150MB total) is not worth the shared-state hazards and the policy change.

**C. Copy-on-write clone of `node_modules` at worktree creation.** When a new worktree is created, CoW-clone `node_modules` from a sibling worktree (typically main). APFS, btrfs, xfs, and ReFS all support per-file CoW; bytes are shared until modified. Each worktree is fully isolated semantically; new worktree creation becomes near-instant. **Chosen as a layer on top of A**, with graceful fallback to `pnpm install --frozen-lockfile --package-import-method hardlink` on filesystems without CoW.

**Final choice: A + C with a capability probe.** A is the universal fix. C is a cross-OS acceleration with clean per-filesystem fallback. The combination preserves every existing invariant.

## Architecture

Three layers, decoupled:

```
┌─────────────────────────────────────────────────────────────────┐
│  pnpm content-addressable store  (single source of bytes)       │
│  ~/Library/pnpm/store/  (macOS)                                 │
│  %LOCALAPPDATA%\pnpm\store\  (Windows)                          │
│  ~/.local/share/pnpm/store/  (Linux)                            │
│  ──> each package version exists exactly once on disk           │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ hardlinks (same-volume requirement)
                            │
┌─────────────────────────────────────────────────────────────────┐
│  Per-worktree node_modules  (owned by the worktree)             │
│  <worktree>/apps/dashboard/node_modules/                        │
│  ──> populated via either path:                                 │
│       (a) pnpm install → hardlinks to store                     │
│       (b) CoW clone from a sibling worktree → bytes share       │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ verifies, materializes, validates
                            │
┌─────────────────────────────────────────────────────────────────┐
│  Preflight orchestrator (scripts/worktree_preflight.py)         │
│  - validates pnpm store-dir is on same volume as worktrees      │
│  - probes filesystem CoW capability                             │
│  - chooses cheapest materialization path                        │
│  - reports incidents into the existing preflight contract       │
└─────────────────────────────────────────────────────────────────┘
```

### Invariants

Preserved from current design:

1. Every worktree has its own real `node_modules` directory tree. The preflight guard against symlinked-out `node_modules` stays in place.
2. The dashboard remains a standalone npm project (no root `pnpm-workspace.yaml`).
3. The MCP/build/test contract is unchanged — `.bin/next` must exist at `apps/dashboard/node_modules/.bin/next`.

New:

4. pnpm store remains at the platform-standard default location. Preflight verifies that the projects directory and the pnpm store directory share the same filesystem volume; if they don't, it reports a clear incident telling the user how to resolve it (either move projects, or set `store-dir` to a path on the projects volume — user's choice, not the design's).
5. pnpm's `package-import-method` is `hardlink`, set in versioned dashboard pnpm config and forced by the preflight fallback install command.
6. The preflight orchestrator has authority to materialize a missing or empty `node_modules` via the cheapest available primitive (CoW clone from sibling > `pnpm install --frozen-lockfile --package-import-method hardlink`).
7. CoW clone is gated on lockfile equality — if the new worktree's `pnpm-lock.yaml` doesn't match the source worktree's, fall through to the hardlink-forced frozen install.

## Components

### 1. Root `.npmrc` (existing file, one line added)

The repo has `/.npmrc` with:

```ini
shamefully-hoist=true
public-hoist-pattern[]=*node-pty*
```

The dashboard also needs an effective local pnpm config because `pnpm` commands run
from `apps/dashboard/` do not necessarily inherit the repo-root `.npmrc`. Add the same
hoisting directives plus the hardlink import directive to `apps/dashboard/.npmrc`:

```ini
shamefully-hoist=true
public-hoist-pattern[]=*node-pty*
package-import-method=hardlink
```

The preflight fallback install path also passes `--package-import-method hardlink`
explicitly, so future worktree materialization remains correct even if local config
lookup changes.

### 2. `scripts/worktree_toolchain.py` (new module, ~150 LOC)

Three pure functions, designed for unit-testability:

- **`verify_pnpm_alignment(project_root: Path) -> Incident | None`** — runs `pnpm config get store-dir`, calls `stat().st_dev` on both the store and the projects directory, returns an `Incident` if they're on different filesystem volumes (with a remediation hint in the message). Returns `None` on alignment.

- **`probe_clone_primitive() -> CloneFn | None`** — returns the right `(src: Path, dst: Path) -> None` callable for the current filesystem, or `None` if no CoW available. Platform table:

  | OS | Filesystem | Primitive |
  |---|---|---|
  | macOS | APFS | `cp -c -R` |
  | Linux | btrfs/xfs | `cp --reflink=auto -R` |
  | Linux | ext4/other | `None` (fall through to install) |
  | Windows | ReFS (Dev Drive) | `Copy-Item` with CoW flag |
  | Windows | NTFS | `None` (fall through to install) |

- **`materialize_node_modules(worktree_root: Path, source_worktree: Path | None) -> MaterializeResult`** — orchestrator. If a source worktree exists with a matching `pnpm-lock.yaml` (SHA-256 equality) and `probe_clone_primitive()` returns a non-`None` callable, attempt clone. On clone success, return `method="clone"`. On clone failure (or no primitive available, or lockfile mismatch, or missing source), fall through to `pnpm install --frozen-lockfile --package-import-method hardlink` and return `method="install"`. If `next_bin` already exists at the target, return `method="skip"` (idempotent). Returns a struct with `method`, `duration_ms`, `source_worktree`, `clone_primitive`, and `incidents`.

This module has zero knowledge of the preflight contract — it's a clean utility callable from anywhere.

### 3. `scripts/worktree_preflight.py` (extended, ~30 LOC added)

Two integration points only:

- A new `_check_pnpm_alignment()` step appended to the existing check sequence — calls `verify_pnpm_alignment()` and emits its incident into the preflight contract.
- The existing `_check_dashboard_deps()` learns one new branch: when `next_bin` doesn't exist *and* `repair=True`, call `materialize_node_modules(worktree_root, source_worktree=_detect_main_worktree())` before re-checking. The existing "node_modules pointing outside worktree root" guard is untouched.

### 4. One-off cleanup (manual or `/dev-clean` extension)

- Delete `apps/dashboard/package-lock.json` (504KB stale npm artifact).
- Optionally `pnpm store prune` to reclaim store space.
- For each existing worktree: `pnpm install` once to re-hardlink with the now-correct config. One-time cost, no recurring action.

### 5. Docs

- One paragraph in `apps/dashboard/README.md` about the pnpm store / same-volume requirement.
- Cross-link in `docs/agent-topics/WORKFLOWS.md` under the worktree section.

## Data flow

### Event 1: Fresh repo clone (no worktrees yet)

```
git clone → cd apps/dashboard → pnpm install
  ├─ pnpm reads apps/dashboard/.npmrc or receives --package-import-method hardlink
  ├─ resolves deps from pnpm-lock.yaml
  ├─ for each pkg: check ~/Library/pnpm/store/...
  │   ├─ if absent → download tarball → unpack into store
  │   └─ if present → reuse
  └─ for each file in node_modules: hardlink from store (NOT copy)
Result: ~50MB metadata + ~0 new bytes
```

### Event 2: New worktree creation (the hot path)

```
worktree-launch.sh → git worktree add → worktree_preflight.py --repair
  ├─ _check_pnpm_alignment() → ✅ (one-time check, passes after setup)
  ├─ _check_dashboard_deps() → ❌ next_bin missing
  └─ materialize_node_modules(new_wt, source=main_wt)
      ├─ compare new_wt/pnpm-lock.yaml vs main_wt/pnpm-lock.yaml
      │   ├─ match → try probe_clone_primitive() → cp -c -R (macOS)
      │   │   ├─ success → done in ~2s, ~0 new bytes (CoW)
      │   │   └─ no primitive or failure → fall through
      │   └─ differ → fall through
      └─ pnpm install --frozen-lockfile → ~5-10s, ~0 new bytes (hardlinks)
Result: new_wt/apps/dashboard/node_modules ready, .bin/next exists
```

### Event 3: Day-to-day dev (no package.json changes)

Nothing to do. `node_modules` is stable; pnpm doesn't touch it. CoW-cloned files become independent on write, but no writes happen to `node_modules` during normal dev (writes go to `.next` which is already symlinked to the shared cache at `~/Library/Caches/Augur/dashboard/next/`).

### Event 4: Branch bumps a dependency (rare)

```
edit package.json → pnpm add foo OR pnpm install
  ├─ pnpm updates this worktree's pnpm-lock.yaml
  ├─ writes new file in node_modules → CoW clone breaks for affected files only
  ├─ new package downloaded to store (if not present)
  └─ new package hardlinked into this worktree's node_modules
Result: this worktree's node_modules diverges from main's; other worktrees unaffected
Disk cost: only the bytes of the newly-added/changed package, not the full tree
```

### Event 5: Main bumps a dependency, existing worktrees catch up

The worktree on the branch that bumped is already updated (Event 4). Other worktrees only update when they pull/rebase main and run `pnpm install`. Standard pnpm behavior; nothing new.

### Event 6: Worktree teardown

```
git worktree remove path
  └─ rm -rf the worktree
      └─ node_modules deletion releases CoW share (or decrements hardlink count)
Result: real disk recovered only when the last hardlink/CoW share goes away
```

### Behavioral property

Events 2 (CoW clone) and 4 (modify) interact cleanly because APFS CoW is **per file**, not per directory. Editing one file in a cloned `node_modules` breaks CoW for that file only — every other file still shares bytes with main. Even after dozens of small mutations, the worktree stays near zero net new disk.

### Safety net

The lockfile-equality check in Event 2 is the safety net for stale-clone scenarios. A single SHA-256 comparison of `pnpm-lock.yaml` between the new and source worktree, before any clone happens, prevents accidentally starting a worktree with `node_modules` that matches the wrong lockfile.

## Error handling

All failures route through the existing `Incident` / `Repair` types in `worktree_preflight.py` — no new error infrastructure.

| Failure | Detection | Response |
|---|---|---|
| pnpm store on different volume from projects | `_check_pnpm_alignment()` compares `stat().st_dev` results | Emit incident with two remediation hints (move projects to store volume *or* set `store-dir` to projects volume). Do not auto-fix — either choice is the user's call. Block worktree materialization until resolved. |
| CoW primitive fails mid-clone | Non-zero exit from `cp -c -R` (or equivalent) | `rm -rf` the partial target, log the clone error as a warning, fall through to `pnpm install --frozen-lockfile --package-import-method hardlink`. No user-facing failure unless install also fails. |
| `pnpm install` fails (network, resolution, etc.) | Non-zero exit from pnpm | Propagate as fatal incident with full pnpm stderr captured. Preflight returns non-zero. |
| Source worktree has no `node_modules` | `materialize_node_modules` checks source's `.bin/next` first | Skip clone, go directly to `pnpm install --frozen-lockfile --package-import-method hardlink`. Not an error. |
| `pnpm-lock.yaml` stale vs `package.json` | `pnpm install --frozen-lockfile` rejects it | Surface pnpm's error as-is. Do NOT silently fall back to lockfile-rewriting `pnpm install` — that would mask a real issue (rule #5). |
| Two `materialize_node_modules` calls race on the same target | Possible if user spawns parallel worktree creations | Acquire a `flock`-style lockfile at `<worktree>/apps/dashboard/.materialize.lock` for the duration. Second caller waits, then sees `next_bin` exists and returns `method="skip"`. ~10 LOC. |
| Worktree created via raw `git worktree add` (bypassing the script) | Standard preflight: `next_bin` missing | Existing contract already handles this: emit `dashboard_deps` failure and tell user to run `--repair` or `/dev-build`. No change. |
| Source's `pnpm-lock.yaml` differs from new worktree's | SHA-256 compare before clone | Skip clone (`method="install"`), fall through to `pnpm install --frozen-lockfile --package-import-method hardlink`. Correct-by-construction. |
| User manually deletes `node_modules` | Standard preflight on next run | `--repair` re-materializes via the same path as Event 2. Idempotent. |
| Windows: store on a different drive letter | Same alignment check using `os.stat().st_dev` | Same incident with Windows-flavored remediation hint (`pnpm config set store-dir D:\pnpm-store`). |

### Explicitly out of scope

- **pnpm version drift between worktrees** — handled by `packageManager: pnpm@10.32.1` in `package.json` + corepack. If someone bypasses corepack, pnpm itself errors clearly. Not our concern.
- **APFS clone source modified during clone** — `cp -c` is atomic at the file level. Nothing else writes to `node_modules` during worktree creation; not a realistic failure mode.

### Error surfacing principle

Every materialization result (success or failure) emits a structured row into the preflight report with `{method, duration_ms, source_worktree, clone_primitive, incidents}`. This makes the cost of the optimization visible — if CoW is silently falling back to install on every worktree (e.g., user moved projects to a different volume), the report shows it instead of hiding it.

## Cross-OS behavior

Per CLAUDE.md rule #30 (cross-OS command surfaces stay shell-neutral), the implementation is entirely in Python. There is no `.ps1` or `.sh` adapter — the preflight engine picks the right clone primitive at runtime via `probe_clone_primitive()`.

| Approach component | macOS | Windows | Linux |
|---|---|---|---|
| A — pnpm hardlinks | ✅ Native (APFS hardlinks) | ✅ Native (NTFS hardlinks) | ✅ Native (ext4/btrfs hardlinks) |
| C — CoW clone | ✅ APFS `cp -c -R` | ⚠️ Only on ReFS Dev Drive; NTFS falls back to install | ✅ btrfs/xfs `cp --reflink=auto` |
| Alignment check | ✅ `stat -f %d` via `os.stat().st_dev` | ✅ Same `os.stat().st_dev` (drive letter changes the device) | ✅ Same |
| Lockfile SHA-256 | ✅ stdlib `hashlib` | ✅ stdlib | ✅ stdlib |

### Windows-specific friction worth noting in docs

- **Store on different drive letter** is the most common Windows misalignment. The alignment check catches it; the remediation hint suggests `pnpm config set store-dir <projects-drive>:\pnpm-store`.
- **Long path support** for deep `node_modules` paths — needs `git config core.longpaths true` and Windows 10+ long path support enabled. Preflight should check this on Windows and emit an incident with the fix command.
- **Windows Defender** scans `node_modules` aggressively. Documentation recommendation: add a Defender exclusion for the projects root. Not enforced by the design.

## Testing strategy

Three layers, mapped to existing auto-loops (rule #19: never invoke raw test commands).

### Layer 1 — Unit tests (`/auto-test-pytest`)

For each pure function in `worktree_toolchain.py`:

- **`verify_pnpm_alignment`** — fixture: mock `pnpm config get store-dir` output and `stat().st_dev`. Assert it returns `None` when devices match, `Incident` otherwise.
- **`probe_clone_primitive`** — fixture: patch `platform.system()` and the filesystem-type probe. Assert the right callable is returned for each `(OS, fs)` combination; assert `None` for unsupported combos.
- **`materialize_node_modules`** — drive the decision tree with tmp dirs:
  - lockfile match + clone succeeds → `method="clone"`
  - lockfile match + clone fails → falls through to install
  - lockfile differs → `method="install"`, clone never attempted
  - source missing `.bin/next` → `method="install"`
  - install fails → fatal `Incident` returned, partial state cleaned

These are fast (sub-second each).

### Layer 2 — Integration tests (`/auto-test-pytest` with a tmp-fixture worktree)

A pytest fixture creates a temp git repo with a minimal `package.json` (just `next` as the dep), runs `git worktree add`, then invokes `worktree_preflight.py --repair` against the new path. Asserts:

- `apps/dashboard/node_modules/.bin/next` exists after preflight.
- Preflight report contains a `materialize` row with `method` populated.
- The new worktree's `node_modules` is NOT a symlink to outside the worktree (existing guard still holds).
- A second preflight run is idempotent (`method="skip"`).
- Mutating `pnpm-lock.yaml` in the new worktree, then creating a third worktree from it, picks `method="install"` (lockfile divergence path).

### Layer 3 — Real-data verification (per CLAUDE.md rule #34)

A one-off `scripts/verify_worktree_toolchain.py` that runs against the *actual* Augur repo and worktrees:

1. Create a real throwaway worktree off main via the standard `scripts/worktree-launch.sh` flow.
2. Confirm materialization succeeded — `.bin/next` exists.
3. Measure: `find apps/dashboard/node_modules -type f -links +1 | wc -l` should be ≫ 0 (proves hardlinks landed). Today: 0–2. Target: ≥80% of files.
4. Measure: `du -sh` of the new worktree's `node_modules` should be near-zero *additional* disk over the source (use `df` before/after for the volume-level delta).
5. **Browser verification (rule #28)**: `/dev-build` in the new worktree, open the dashboard in a real browser, confirm at least one page mounts to interactive state.
6. Tear down the worktree, confirm `df` reclaims the expected bytes.

The output of this script is the evidence pasted into the merge commit — naming the real input (actual repo, actual main worktree as source), the concrete output (hardlink count, disk delta, browser screenshot or page-load excerpt), and the user-facing value (worktree creation went from ~30s / 767MB to ~2s / ~0MB).

### Cross-OS coverage

- **macOS** — covered by the dev environment running the verification.
- **Linux** — CI runs Layer 2 integration tests, exercising the `cp --reflink=auto` path on btrfs if available, else hitting the install fallback. Layer 2 doesn't gate on CoW success; it gates on materialization correctness.
- **Windows** — Layer 2 runs the install-fallback path. A separate manual smoke on a Windows machine confirms the alignment check produces the right error when store and projects are on different drive letters.

### Regression coverage

- Existing preflight tests for `_check_dashboard_deps` must keep passing unchanged.
- The "node_modules pointing outside worktree root" guard test must keep passing — the new code path does not symlink `node_modules`.

### Out of scope for tests

- pnpm store internals (covered by pnpm's own test suite).
- APFS / btrfs / ReFS CoW semantics (kernel guarantee).
- Network or registry behavior during install (pnpm's concern).

## Migration

A one-shot, no automated rollout:

1. **Set `package-import-method=hardlink` in `/.npmrc` and `apps/dashboard/.npmrc`**. Commit.
2. **Remove the stale `package-lock.json`** at `apps/dashboard/package-lock.json`. Commit.
3. **Land the `worktree_toolchain.py` module + preflight integration**. Commit.
4. **Run the verification script** (Layer 3) once on the dev machine. Paste evidence into the merge commit.
5. **For each existing worktree**: `pnpm install` once to re-hardlink against the now-correctly-configured store. (No script automation — this is a one-time hand-off per worktree.)
6. **Optionally** `pnpm store prune` to reclaim store bytes.
7. **Update docs** (`apps/dashboard/README.md`, `docs/agent-topics/WORKFLOWS.md`).

No flag-gating, no phased rollout. The change is local to one machine's filesystem layout and either works (verifiable in seconds) or doesn't (visible in the preflight report).

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| pnpm store and projects are on different volumes for some users | Medium (common on dev rigs with external SSDs) | Alignment check + clear remediation hint. User chooses which to move. Until resolved, behavior is unchanged from today (full copies). |
| CoW clone produces a `node_modules` that pnpm later refuses to manage | Low (pnpm doesn't track inode identity, only content) | Verified at Layer 2 (clone then re-run preflight → no incidents); Layer 3 runs `pnpm install --frozen-lockfile --package-import-method hardlink` after a clone-populated worktree to confirm pnpm accepts the state. |
| User's pnpm version disagrees with the `packageManager` field | Low (corepack enforces) | Surfaces as pnpm's own clear error. Out of scope for this design. |
| Windows users without ReFS Dev Drive get no acceleration | High (most Windows users) | A still applies (hardlinks work on NTFS); fallback to `pnpm install --frozen-lockfile --package-import-method hardlink` is still fast because hardlinks replace network downloads. The disk-sharing benefit is universal even when CoW isn't. |
| Future Next.js or pnpm update changes hardlink behavior | Low | Preflight's `_check_pnpm_alignment()` runs every time, so regressions surface as incidents. |
