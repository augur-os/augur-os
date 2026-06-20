---
status: Implemented
date: 2026-05-24
deciders:
  - gsannikov
related: [759]
hub: null
tags: [testing, sys-modules, isolation, ci, tech-debt]
superseded_by: null
spec_file: null
plan_file: 2026-05-24-test-suite-module-identity.md
---

# ADR-778: Test-Suite Module Identity Isolation

> **ADR-778 is an index file.** The substantive design and implementation steps live in the linked plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Retire the legacy `augur_mcp` compatibility shim, migrate production and test consumers to canonical `src.mcp.*` imports and patch targets, and remove direct `src/mcp` roots from the test process so each MCP source module has one identity during monolithic `pytest tests/` runs. Add a full-tree CI guard so the invariant cannot silently regrow.

## Spec (canonical)

- None — design is folded into the plan.

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-24-test-suite-module-identity.md`](../superpowers/plans/2026-05-24-test-suite-module-identity.md)

## Status notes

Implemented (2026-05-24). Surfaced while investigating a 187-failure baseline during the worktree-plugin-registration work: confirmed pre-existing (290 at ADR-759 on 2026-05-16, now 187), deterministic, and a pure test-isolation artifact — tests pass in isolation, fail only in the whole-tree run. Root cause was dual `sys.modules` registration; the scoped `auto-test-pytest` loop masked it because it never ran the full tree in one process.

**Prior implementation attempt 2026-05-24 (`/adr implement`) — BLOCKED.** The planned standalone meta_path canonicalizer was net-negative: canonicalizing all `augur_*` fixed 65 but added 38 regressions + 151 errors; excluding the `augur_mcp` shim was worse (191 failed). The legacy `augur_mcp` shim computed its alias targets from `__name__`, so a finder fought it either way. That evidence drove the implemented direction: **retire/rework the `augur_mcp` shim first** (ADR-14 canonical-cleanup direction), then drop `src/mcp` from the test `sys.path`. The failure-set-diff acceptance harness from this attempt was reused. See the plan's "Attempt log" for the evidence.

**Implementation 2026-05-24 (`/adr implement`) — PASSED.** Retired the `augur_mcp` shim instead of adding a second import indirection layer. Production and test code that imported or patched `augur_mcp.*`, `augur_framework.*`, `augur_shared.*`, or `augur_core.*` was migrated to canonical `src.mcp.*` module paths where it runs inside the repo test process. `tests/conftest.py` now removes direct `src/mcp` path roots before and after tests so bare MCP imports cannot create duplicate module objects; production MCP launch surfaces still keep their required runtime `src/mcp` `PYTHONPATH` contract. The legacy packaging tests that asserted `augur_mcp` alias behavior were replaced with tests for the retired namespace and canonical test patch/import targets. The monolithic acceptance gate passed: baseline `187 failed, 2599 passed, 80 skipped`; after implementation `2786 passed, 80 skipped`, with `187` fixed, `0` failure regressions, and `0` error regressions.

## Related

- ADR-759 (prior triage of the same dual-module-path failure class)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - "tests patching short module path while impl uses long path (or vice versa)"
    - "legacy augur_mcp compatibility namespace inside the repo test process"
  files_affected:
    - tests/conftest.py
    - tests/packages/augur-mcp/test_packaging.py
    - tests/test_module_identity_isolation.py
    - src/mcp/pyproject.toml
    - src/mcp/augur_mcp/
    - .github/workflows/ci-tests.yml
```
