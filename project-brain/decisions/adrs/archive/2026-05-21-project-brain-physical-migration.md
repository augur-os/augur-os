# Project-Brain Physical Migration Plan

## Goal

Move Augur project-brain content from `shared-vault/` to `project-brain/` and
make the new physical layout canonical.

## Tasks

### Task 1: Inventory And Classify `shared-vault` References

- Generate a full `rg "shared-vault"` report across code, tests, docs, and
  generated-source templates.
- Classify each hit as canonical path, compatibility wrapper, historical doc,
  test fixture, or generated output.
- Commit the inventory as a migration note under `docs/reports/` or the ADR
  closeout section.

### Task 2: Extend Brain Skeleton

- Add `config/` and `drafts/` to `src.lib.brain_manifest` skeleton.
- Add tests proving new `project-brain/` roots contain the full v1 contract.

### Task 3: Move Durable Content

- Use `git mv` for root migrations from `shared-vault/` to
  `project-brain/`.
- Create pointer README files where repo-level docs remain canonical, especially
  `project-brain/decisions/adrs/README.md`.
- Register mapped project-brain sources for `docs/adrs/`,
  `docs/superpowers/specs/`, `docs/superpowers/plans/`,
  `docs/agent-topics/`, and `plugins/agents/` before any physical move of
  those roots.
- Verify no runtime/cache/log/index directories are moved.

### Task 4: Update Path Helpers And Loaders

- Replace canonical readers with project-brain helpers.
- Keep `get_shared_vault_*` wrappers only where needed for one release, with
  explicit deprecation comments and tests.
- Add mapped-source resolution so ADRs, specs, plans, instructions, workflows,
  and agents can be treated as project-brain material while their governing
  physical roots remain in `docs/` or `plugins/`.
- Update Python import/PYTHONPATH handling for migrated skill packages.

### Task 5: Update Discovery And Dashboard Surfaces

- Update skill discovery, command discovery, MCP bundle discovery, dashboard
  registry generation, Browse transforms, and YAML page generation.
- Regenerate generated surfaces.

### Task 6: Exhaustive Migration Check

- Run the full reference scan again.
- Fail the phase if any uncategorized `shared-vault` hit remains.
- Run focused tests for all changed discovery/path surfaces.

### Task 7: Real-Data Proof

- Query the real migrated project-brain skill inventory.
- Open/read one real migrated skill document through the product path.
- Verify a real dashboard/Browse page renders migrated project-brain data.

## Acceptance Criteria

- `project-brain/` is the canonical root for Augur project-brain content.
- ADRs and project lifecycle material are visible through project-brain
  mappings even when their physical canonical roots remain under `docs/`.
- `shared-vault/` no longer exists as a canonical source path.
- Every remaining `shared-vault` reference is explicitly historical or
  compatibility-expiring.
- Tests and real-data checks prove skills, commands, MCP bundles, and Browse
  still work.
