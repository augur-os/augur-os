# Plan: Test-Suite Module Identity Isolation

**Date:** 2026-05-24
**Owner ADR:** ADR-778
**Status:** Implemented

## Problem

Running the Python test suite monolithically — `pytest tests/` in one process —
produces **187 failures** (down from 290 triaged on 2026-05-16 under ADR-759, so
partially chipped away). Every one is a **test-isolation artifact**, not a real
defect:

- `tests/packages/augur-mcp/` run alone → 601 passed, 0 failed.
- The other large clusters run alone → 0 failed.
- The same tests inside `pytest tests/` → ~187 fail.
- No `pytest-randomly`/`xdist` installed, so collection order is deterministic
  and the failing set is stable run-to-run.
- Stash/compare proved the worktree-plugin change in this thread contributes
  **zero** of these failures.

## Root cause

A single source file gets imported under **two names** and becomes **two
distinct module objects**, both live in `sys.modules`:

```
src.cli_plugins                       ⇆  cli_plugins
src.mcp.augur_shared.bundle_server    ⇆  augur_shared.bundle_server
src.mcp.augur_framework.tools.…       ⇆  augur_framework.tools.…
```

`is`-identity is `False`. A test does
`patch("src.cli_plugins._get_skill_dirs", return_value=[])`, but the code under
test was bound — by whichever path an **earlier** suite test imported first — to
the *other* object, so the patch is a no-op and the **real environment leaks in**
(`discover_subcommands` returns `7` real skills instead of the patched `0`;
`bundle_server.run("apple")` logs `[augur_shared.bundle_server] bundle 'apple'
not found` despite `_collect_skill_dirs` being patched). Hence the failures are
order-dependent and surface only in the whole-tree run.

### Trigger

Overlapping `sys.path` roots installed by competing conftests:

- `tests/conftest.py` adds the project root, `src/mcp` (lines ~35-36), the
  plugin-factory scripts dir (~52-53), and **all package roots** (~113-122).
- `tests/cli/conftest.py:9` *removes* `src/` from `sys.path` as a local
  mitigation, then re-inserts the project root.

`src/mcp` on `sys.path` is **required** by the production MCP runtime
(CLAUDE.md: PYTHONPATH must include project root and `src/mcp`), so the runtime
contract cannot simply be removed. The implemented fix removes that path from
the **test process only** after migrating repo tests and patch targets to
canonical imports.

### Why the test loop stays green (green ≠ clean)

`auto-test-pytest`
(`project-brain/capabilities/skills/routine-codebase/scripts/test_pytest_ops.py::_run_pytest`)
runs **hub-scoped** `test_dirs` with `-x --tb=short -q` — it never executes the
whole tree in one process, so it sidesteps the cross-dir pollution and **masks
the broken monolithic-run invariant**. This is pre-existing and reproduces on any
checkout (pure source + test code, no worktree-specific paths).

## Goal

A single source file resolves to a single module object regardless of import
alias, so `mock.patch` targets always land. Acceptance: monolithic `pytest
tests/` failure count goes **187 → 0** (or only genuinely-broken tests remain,
each individually triaged), with the ~2599 currently-passing tests preserved.
Add a mechanical regression guard so the invariant cannot silently regrow.

## Attempt log — 2026-05-24 (`/adr implement ADR-778`, BLOCKED)

The repo-root meta_path canonicalizer below was implemented and measured against
the 187-failure baseline. **It is net-negative and was reverted** — the legacy
`augur_mcp` shim is the blocker:

| Variant | Result vs 187 baseline |
|---|---|
| Canonicalize all `augur_*` (incl. `augur_mcp` shim) | 159 failed, **65 fixed**, but **+38 regressions + 151 errors** |
| Canonicalize `augur_core/framework/shared`, exclude `augur_mcp` | **191 failed** (worse), 1 fixed, +5 regressions + 2 errors |

Root finding: `src/mcp/augur_mcp/__init__.py` is a self-referential compatibility
shim that computes its alias targets from its own `__name__`. A meta_path finder
that rebinds the bare `augur_*` names to the canonical `src.mcp.augur_*` objects
**fights that logic**: including the shim breaks its packaging/importability
tests (`test_legacy_augur_mcp_namespace_aliases_*`, the `test_*_importable`
suite) with `AttributeError`/import errors; excluding it makes the shim's aliases
and the canonicalizer mutually incoherent (even worse). A naive
import-finder cannot satisfy the zero-regression gate while this shim exists.

**Revised plan:** the shim must be addressed first. Either (a) **retire the
`augur_mcp` shim** — migrate every bare `augur_mcp.*` / `augur_framework.*`
consumer (prod + tests) to canonical `src.mcp.*`, delete the shim and its
`_ALIASES`, then drop `src/mcp` from the test `sys.path` so the dual alias can no
longer form; or (b) make the canonicalizer **shim-aware** — co-design it with the
shim's `__getattr__` so name computation stays consistent. Option (a) is the
clean ADR-14 ("canonical cleanup over compatibility shims") direction and removes
the root cause rather than masking it; it is the larger refactor and should run
as its own subagent-driven effort with the same failure-set-diff gate. This
attempt's harness (failure-set diff vs a frozen baseline) is the right
acceptance instrument and should be reused.

## Chosen approach — retire the shim and remove the test alias root

Retire the `augur_mcp` compatibility shim instead of adding a repo-wide
`sys.meta_path` canonicalizer. The prior attempt showed that the shim's
self-referential `_ALIASES`/`__getattr__` behavior and an import finder cannot
both satisfy the zero-regression gate.

Implemented shape:

- Delete `src/mcp/augur_mcp/` and remove the package from the MCP package
  manifest.
- Migrate repo production code, tests, and `unittest.mock.patch` targets from
  bare `augur_mcp.*`, `augur_framework.*`, `augur_shared.*`, and
  `augur_core.*` paths to canonical `src.mcp.*` paths where they run in the repo
  test process.
- Replace packaging tests that asserted the legacy `augur_mcp` namespace with
  tests that assert the namespace is absent and that repo tests use canonical
  MCP import/patch targets.
- Remove direct `src/mcp` roots from `tests/conftest.py` before and after tests,
  including paths injected by package metadata or individual tests, while
  preserving the production MCP runtime's `src/mcp` `PYTHONPATH` contract.
- Add a CI guard that runs the full `tests/` tree in one process with the same
  module-identity topology.

## Alternatives considered

- **B. Generalize the cli-conftest path-pruning** (remove `src/` globally, force
  `src.X` everywhere). Rejected: `src/mcp` must stay on path for the MCP runtime,
  and bare `augur_*` imports in the MCP shim still need resolution.
- **C. Per-test patch-target rewrite** (`patch("X…")` → `patch("src.X…")`, per
  the `[[project-augur-mcp-shim-two-module-objects]]` memory). Rejected as the
  systemic fix: ~187 sites, fragile, no regrowth protection. Keep only as a
  fallback for stragglers the finder cannot canonicalize.

## Implementation steps

1. Inventory bare MCP namespace consumers in production code and tests:
   `augur_mcp.*`, `augur_framework.*`, `augur_shared.*`, and `augur_core.*`,
   including `unittest.mock.patch` string targets.
2. Migrate repo test-process imports and patch targets to canonical
   `src.mcp.*` paths.
3. Delete the `augur_mcp` shim and replace shim-contract tests with retirement
   tests that make the new canonical-import contract explicit.
4. Remove direct `src/mcp` roots from the test `sys.path`, including paths
   injected before collection or by individual tests, without changing the
   production MCP runtime `PYTHONPATH` contract.
5. Add a **mechanical CI/hook guard** that runs the FULL `tests/` tree in one
   process (not hub-scoped) and fails on any cross-contamination, so the
   invariant is enforced for every agent (per
   `[[prefer cross-agent enforcement over Claude-only rules]]`). Wire via
   `.githooks/` or CI workflow, not a behavioral rule.
6. Run monolithic `pytest tests/`; confirm failures drop 187 → 0 and produce a
   before/after **failure-set diff** showing no previously-passing test
   regresses.

## Verification (rule 34 — prove user value on real data)

The real metric is the monolithic run, not a scoped subset: show
`pytest tests/` going from 187 failed / 2599 passed to 0 failed (or a small,
individually-triaged residue) / 2599+ passed, with the failure-set diff attached.
A green scoped loop is **not** acceptance evidence here — that is exactly the
surface that currently hides the bug.

Implementation result (2026-05-24):

```text
baseline: 187 failed, 2599 passed, 80 skipped
after:    2786 passed, 80 skipped
fixed:    187
failure regressions: 0
error regressions:   0
```

## Risks

Import-machinery changes are global. Mitigations: stdlib + site-packages guards,
repo-`src`-scoped allowlist, and the before/after failure-set diff as the binding
acceptance gate. Watch for interaction with the configured
`--import-mode=importlib` and with `pythonpath = [".", "project-brain/capabilities"]`.
