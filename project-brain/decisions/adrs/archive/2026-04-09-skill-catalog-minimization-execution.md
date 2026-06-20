# Skill Catalog Minimization Execution Ladder

> Goal: reduce the Augur-owned skill set to a smaller, higher-value catalog without deleting real runtime behavior by accident.

## Execution Rules

- Do not delete or externalize a skill based only on the first-pass catalog audit.
- For every destructive move, check MCP tools, pages, generated blocks, tests, docs, and cross-repo references first.
- Prefer absorbing weak boundaries into stronger destination skills before removing files.
- Keep tool names stable during migrations unless the destination replacement is already live.
- Treat `reading` and `learning` as target-state concepts for now, not existing destination skills.

## Phase 1: Thin Wrapper Merges

These have the lowest risk and remove obvious fake boundaries first.

### 1. Merge `post` into `content`

- Move the user-facing workflow into `content`
- Update references to `/post`
- Remove the standalone `post` skill only after `content` owns the workflow docs

### 2. Merge `design-content-pipeline` into `content`

- Move any remaining workflow instructions into `content`
- Replace standalone references with `content` entrypoints
- Remove the standalone skill after references are updated

### 3. Merge `scrape-and-save-idea` into `lifestyle`

- Move the scrape-save flow into `lifestyle`
- Preserve the user-visible capability, remove the separate thin skill boundary

## Phase 2: Infrastructure Ownership Cleanup

These reduce hidden architectural drift before broader consolidation.

### 4. Move review tooling fully into `channels`

- Register `get-reviews-summary` and `manage-reviews` from `channels`
- Retire `src/mcp/augur_mcp/domain/reviews.py`
- Keep tool names stable during the move

### 5. Clean up stale `executor` wiring

- Remove references to missing executor scripts/pages
- Decide whether anything real remains worth preserving
- Delete the `executor` skill only after stale references are removed

## Phase 3: Thin Internal Boundary Reduction

These are good reduction targets but should happen after the obvious wrapper cleanup.

### 6. Consolidate or remove thin internal skills

Priority set:

- `hub-template`
- `skill-setup`
- `performance-profiling`
- `nightly`

Expected direction:

- `hub-template`: delete or fold into a single templates surface
- `skill-setup`: remove or replace with current `skills/`-native scaffolding
- `performance-profiling`: fold into `observe`/metrics/system diagnostics
- `nightly`: fold into validator/daemon-owned execution

## Phase 4: Direct Absorption Migrations Into Existing Skills

These are worthwhile catalog reductions, but they are real product migrations.

### 7. Migrate `linkedin-writer` into `content`

- Move post storage/tooling/page ownership into `content`
- Preserve existing post workflows during migration
- Remove `linkedin-writer` only after `content` fully owns the surface

### 8. Migrate `wearables` into `health`

- Move live wearables tools, blocks, and page routing into `health`
- Replace `health`'s optional dependency relationship with direct ownership

### 9. Migrate `wealth` into `finance`

- Fold wealth-specific dashboard and MCP surfaces into `finance`
- Retire dedicated `wealth` registration in `src/mcp/augur_mcp/infrastructure/wealth.py`

### 10. Migrate `enterprise` into `venture`

- Move page/tool/block ownership into `venture`
- Rename `venture-augur` to `venture` as part of the same business-surface cleanup

## Phase 5: Concept-Target Migrations

Do not start these until a concrete destination exists.

### 11. Create a real `reading` destination, then merge:

- `books`
- `reading-list`

This is not ready yet because both skills still own active MCP/page/test surfaces and no replacement skill exists.

### 12. Create a real `learning` destination, then merge:

- `growth`

This is not ready yet because there is currently no `learning` skill in the repo.

## Phase 6: Externalization Decisions

These should be handled after the internal/public boundary is cleaner.

### 13. Externalize with migration plans

- `generative-ui`
- `career-ops`

Notes:

- `generative-ui` has low Augur ownership signal and looks like a good early externalization candidate
- `career-ops` is imported but highly integrated, so it needs a deliberate migration plan rather than a simple ownership flip

## Recommended First Implementation Batch

If the goal is maximum reduction with minimum risk, start here:

1. `post -> content`
2. `design-content-pipeline -> content`
3. `scrape-and-save-idea -> lifestyle`
4. move review tooling into `channels`
5. clean stale `executor` references
6. resolve `hub-template`, `skill-setup`, `performance-profiling`, `nightly`

That sequence removes weak boundaries quickly without starting the heavier product migrations too early.
