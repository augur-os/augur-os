---
status: Implemented
date: '2026-05-05'
deciders:
- Gur Sannikov
related:
- ADR-176
- ADR-200
- ADR-216
- ADR-453
hub: adaptive
tags:
- adaptive-loops
- self-heal
- dashboard
- worktrees
- observability
- monitor
superseded_by: null
---


# ADR-572: Loop Coverage and Worktree Boundary Hardening

## Context

On 2026-05-05 the dashboard at `localhost:3000` returned 500 on every route for an extended period while every supervisory layer reported green. The trigger was a single dangling symlink — `apps/dashboard/node_modules/node_modules` pointing at `.worktrees/dev-loops-2026-05-05/apps/dashboard/node_modules`, a worktree that no longer existed. Turbopack's resolver hit the dangling pointer, package lookups for `@swc/helpers/_/_interop_require_default`, `@swc/helpers/_/_interop_require_wildcard`, and `scheduler` failed even though all three packages were present on disk, the dev server compiled to 500s, and eventually died.

The trigger was small. The failure mode was that **four independent supervisory layers each used a predicate too weak to catch it**:

1. **Self-heal ran in a worktree it couldn't see the main bug from.** The auto-self-heal loop (`skills/daemon/scripts/ops/self_heal.py`) executed inside `.worktrees/dev-loops-2026-05-05/`. The bug existed only in the main checkout's `node_modules/`. Self-heal scanned its own worktree's filesystem view and reported `success` while the user's actual dashboard was 500ing.

2. **No loop probes the live dashboard.** The categories `auto-test-build`, `auto-debt-scan`, `auto-skill-quality`, `auto-flow-optimizer`, `auto-mcp-health-audit`, etc. all check static artifacts (build outputs, lint, AST, registry parity). None does the equivalent of `curl :3000/ → assert 200` *and* `grep dashboard.stderr.log for "Module not found" → assert empty`. `auto-test-build` ran for 40 seconds and reported success while the running dashboard was unreachable.

3. **`dashboard_monitor` predicate is "PID alive."** Lifecycle journal entries during the outage: `"process alive, port not bound (compiling)" → state: healthy`. PID-existence is the wrong predicate — a turbopack compile loop that never finishes leaves the PID alive forever. This is the same SSR-vs-client trap CLAUDE.md rule 28 warns about, but raised one layer to the daemon.

4. **Worktree teardown leaks back-references into the parent checkout's `node_modules/`.** The `.worktrees/dev-loops-2026-05-05/` directory was removed by routine cleanup, but the symlink it had planted in the main checkout's `apps/dashboard/node_modules/` was not. CLAUDE.md rule 26 ("No-loss dev-merge cleanup") covers branches and worktree directories themselves; it does not cover symlinks the worktree's package manager planted outside its own root.

The shared root cause is **predicate weakness at every supervisory boundary**: scope (where the loop runs), coverage (what the loop checks), liveness (what "healthy" means), and teardown (what cleanup actually cleans up). Any one of the four would have caught this; none of them did.

## Decision

Tighten the predicate at each layer. Bundled here because they share one root cause; staged because only Remediation 1 ships in this ADR's first commit and the others have larger blast radius.

### Remediation 1 — Self-heal main-checkout gate (this commit)

`skills/daemon/scripts/ops/self_heal.py` is the canonical auto-self-heal entry per ADR-200. Its `scan(ctx)` and `fix(ctx, issues)` early-return a benign no-op when `ctx.project_root` is not the git main checkout (i.e., is inside `.worktrees/` or is a linked worktree).

The gate is implemented inside the ops module, not at the engine, because:

- Scoping the rule to its module keeps the blast radius small. The user asked for self-heal specifically; executor-level gating would silently affect every loop.
- Catches every caller automatically: adaptive engine, manual CLI invocation, tests, future ad-hoc orchestration.
- Reuses the existing `skills/platform-admin/scripts/worktree_guard.py` helper, which already encapsulates the porcelain-parsing logic for "what is the main checkout."

The gate adds two predicates to `worktree_guard.py`: `is_main_checkout(path)` (strict — False on errors) and `is_inside_worktree(path)` (fail-open — False on errors and on non-git paths). Self-heal calls the fail-open variant so a non-git scratch dir or a deployment without platform-admin still runs the loop. When the gate skips, **the result is journaled** with `summary="self-heal skipped: running inside a worktree (ADR-572)"` and `severity="info"`. Silent skips are how the original outage stayed invisible; this ADR explicitly rejects them.

A loop-level YAML scope flag (e.g., `loops.self-heal.scope: main-checkout`) is a more general design but adds engine surface for one constraint. Defer until a second loop needs the same gate; promote the gate from module-level to engine-level then.

### Remediation 2 — Live-dashboard probe loop (proposed, not in this commit)

Add a new ops module `skills/daemon/scripts/ops/dashboard_live.py` with category `auto-dashboard-live`. Its `scan(ctx)`:

1. `curl http://localhost:3000/ → assert HTTP 200`
2. Tail `~/Library/Logs/Augur/dashboard.stderr.log` for the last N minutes; assert no `Module not found` and no `Failed to load chunk` entries
3. Optionally probe one route per hub against the SSR document and assert no `<augur-error-boundary>` or chunk-load error markup

Failures escalate to self-heal (which the main-checkout gate now permits, since the loop runs against the *running* dashboard, not a worktree's filesystem view).

### Remediation 3 — Dashboard monitor predicate (proposed, not in this commit)

`skills/daemon/scripts/dashboard_monitor.py` health classifier currently treats `process alive AND port not bound (compiling)` as `healthy`. Replace with: a process must answer HTTP 200 on `/` within a ceiling (suggested 60 s after first compile entry; no ceiling on a steady-state-bound port) to count as healthy. A turbopack process that compiles indefinitely transitions to `degraded` and triggers Remediation 2.

### Remediation 4 — Worktree teardown back-reference scrub (proposed, not in this commit)

The `/dev-merge` worktree cleanup script and any other code path that runs `git worktree remove` must also run, for the parent checkout, the equivalent of:

```bash
find <main-checkout>/node_modules -type l -lname '*.worktrees/*' -delete
find <main-checkout>/apps/*/node_modules -type l -lname '*.worktrees/*' -delete
```

Include the scrub in `skills/platform-admin/scripts/dev_merge_purge.py`. Update CLAUDE.md rule 26 to cover symlinks planted outside the worktree root.

## Consequences

**Positive**

- Self-heal in a worktree becomes a *recorded* no-op instead of a fake `success`. Operators can see in the loop journal that the loop ran and skipped, and why.
- The four remediations form one decision record so future incidents that hit any of them can attach to the same ADR rather than spawn duplicates.
- Establishes the principle: **every supervisory layer must use a predicate strong enough to catch the failure mode it claims to supervise.**

**Negative**

- Remediation 1 means self-heal coverage in worktrees drops to zero. This is the right trade — the cost of self-heal "fixing" a worktree that gets deleted minutes later, or running against a filesystem view that excludes the real bug, is higher than the cost of skipping. If a future workflow needs worktree-scoped self-heal, it should be a different loop with worktree-aware semantics, not the current self-heal.
- Remediations 2-4 expand the dashboard's runtime contract (the loop now hits `:3000`). If the dashboard is intentionally not running, the live-probe loop must respect a "dashboard not expected" mode (e.g., `dashboard_lifecycle` reports `stopped`).

**Neutral / migration**

- No data migration. The journal will start emitting `severity=info, action=fix-skipped, reason=not-main-checkout` entries; existing log consumers should ignore unknown reasons.
- ADR-200 (self-heal extraction) and ADR-216 (severity gating) remain authoritative for self-heal's scan/fix logic; this ADR adds one orthogonal constraint at the entry boundary.

## Implementation

This ADR's first commit ships Remediation 1 only:

- Add `is_main_checkout(path: Path) -> bool` to `skills/platform-admin/scripts/worktree_guard.py`
- Add the gate to `skills/daemon/scripts/ops/self_heal.py` `scan()` and `fix()`
- Add a test that creates a tmp git worktree, points an `OpsContext` at it, and asserts `scan()` returns the skip result

Remediations 2-4 are tracked as Proposed in this ADR's body and may ship under separate commits that reference ADR-572.
