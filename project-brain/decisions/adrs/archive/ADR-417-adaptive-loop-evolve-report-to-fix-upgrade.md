---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-200
  - ADR-412
hub: null
tags:
  - adaptive-loops
  - auto-commands
  - code-quality
  - testing
superseded_by: null
---

# ADR-417: Upgrade Report-Only Auto-Commands to Produce Code Fixes

## Context

The adaptive loop engine (ADR-200) runs 70 auto-command categories across 9 loops. An evolve analysis on 2026-03-17 revealed that **10 categories find issues but never produce code fixes** — they write reports but don't act on them. This means the engine's fix rate is 0%: all findings require manual follow-up.

### Current State (2026-03-17 evolve run)

| Category | Issues Found | Current Behavior |
|----------|-------------|-----------------|
| auto-debt-scan | 677 | Writes debt report (oversized/high-churn files) |
| auto-coverage-check | 395 | Writes coverage gaps report |
| auto-stale-paths | 39 | Writes ADR-270 drift report |
| auto-mcp-hygiene | 32 | Reports non-compliant MCP tool names |
| auto-code-review | 1 | Reports tsc/lint errors |
| auto-markers | 1 | Scans runtime markers |
| auto-repo-sync | 1 | Reports uncommitted changes |
| auto-test-links | 1 | Reports broken links |
| reindex-rag | 2 | Indexes skills (maintenance) |
| auto-skill-refs | 1 | Reports reference issues |

Additionally, **28 categories are trust-stuck** (trust < 10% after 12+ cycles) because their scans always return empty — they never find issues at their current difficulty level.

## Decision

Upgrade the top 5 report-only categories to produce actual code fixes, prioritized by issue count and feasibility:

### Phase 1: Quick wins (report → auto-fix)

1. **auto-mcp-hygiene** (32 issues) — Add auto-rename for non-compliant MCP tool verbs. The scanner already identifies the violations; the fix is a targeted `sed`-style replacement in `augur.yaml` files.

2. **auto-code-review** (lint errors) — When lint errors have auto-fixable rules (e.g., missing semicolons, unused imports), apply `eslint --fix` automatically instead of just reporting.

3. **auto-markers** — When TODO_CLEANUP markers have clear instructions, apply the cleanup. Currently only scans and reports.

### Phase 2: Structural fixes

4. **auto-coverage-check** (395 issues) — Generate test stub files for untested modules. Start with modules under 200 lines where the public API is extractable from type hints. Use a template that creates one test per public function with `pytest.mark.skip(reason="stub")`.

5. **auto-debt-scan** (677 issues) — For oversized files above 2x threshold (800+ lines), generate a refactoring plan as a TODO_CLEANUP marker in the file header. For files above 4x threshold (1600+ lines), attempt automated extraction of independent helper functions into sub-modules.

### Phase 3: Trust-stuck categories

Address the 28 trust-stuck categories by:
- Lowering their minimum difficulty to d0 (some are stuck at d1+ with empty scans)
- Adding "canary" checks that always find at least one advisory issue, so trust can build
- Reviewing scan() logic for overly aggressive filtering

## Consequences

- Fix rate should improve from 0% to >10% within 2 weeks
- Manual follow-up burden decreases — the engine handles routine fixes autonomously
- Trust scores for upgraded categories will climb as successful fixes accumulate
- Risk: auto-fixes may introduce bugs — mitigated by the engine's verify_commit() step which runs `tsc --noEmit` after every fix

## Implementation Notes

Each upgrade follows the same pattern:
1. Read the existing `scan()` output format
2. Add a `fix()` implementation that transforms scan issues into file edits
3. Use `OpsContext.dry_run` for safe testing
4. Verify with the engine's built-in TypeScript/Python verification

Priority order: Phase 1 first (1-2 weeks), Phase 2 next (2-4 weeks), Phase 3 ongoing.
