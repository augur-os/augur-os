# Project-Brain Physical Migration Design

Date: 2026-05-21

## Context

`shared-vault/` currently holds durable Augur project knowledge, capabilities,
wiki material, inbox policy, and lifecycle documents. The name came from the
older shared/team-vault model, but the current product model treats this
material as the Augur project brain.

Phase 2 already introduced `project-brain/`, root `BRAIN.yaml`, cwd discovery,
and `aug init`. Phase 3 migrates the physical content and updates path helpers
so the repo no longer depends on `shared-vault/` as the canonical project-brain
root.

## Goals

- Move durable Augur project-brain content into `project-brain/`.
- Keep runtime state, caches, logs, and generated client caches outside the
  brain folder.
- Preserve git history through `git mv` where practical.
- Keep existing product behavior working during the migration.
- Remove `shared-vault/` as a long-term source path.
- Leave any compatibility surface explicit, temporary, and tested.

## Non-Goals

- Do not migrate the personal brain.
- Do not create multi-repo project-brain support.
- Do not redesign AI-client projection semantics; that is ADR-771.
- Do not build dashboard federation; that is ADR-772.
- Do not keep `shared-vault/` as an alias after this phase is complete unless a
  specific compatibility exception is documented with an expiry.

## Target Layout

```text
Augur/
  project-brain/
    BRAIN.yaml
    profile/
    instructions/
      topics/
    capabilities/
      skills/
      agents/
    knowledge/
      memory/
      notes/
      sources/
      wiki/
    decisions/
      adrs/
    specs/
    plans/
    workflows/
    policies/
    activity/
      daily/
    reports/
    inbox/
    archive/
    config/
    drafts/
  src/
  apps/
  docs/
  tests/
  scripts/
```

`config/` and `drafts/` remain in the contract because the current
`shared-vault/` root already contains them and they are durable project-brain
content, not runtime state.

`docs/` roots may remain physically under `docs/` when an existing contract
requires that location. In that case the project brain owns an explicit mapping
and pointer under `project-brain/`, not a duplicate copy. This keeps ADRs and
project lifecycle material part of the project brain without breaking ADR-608's
current `docs/adrs/` release contract.

## Migration Map

| Current path | Target path |
| --- | --- |
| `shared-vault/skills/` | `project-brain/capabilities/skills/` |
| `shared-vault/wiki/` | `project-brain/knowledge/wiki/` |
| `shared-vault/notes/` | `project-brain/knowledge/notes/` |
| `shared-vault/sources/` | `project-brain/knowledge/sources/` |
| `shared-vault/inbox/` | `project-brain/inbox/` |
| `shared-vault/archive/` | `project-brain/archive/` |
| `shared-vault/config/` | `project-brain/config/` |
| `shared-vault/drafts/` | `project-brain/drafts/` |
| `shared-vault/README.md` | `project-brain/README.md` |

## Mapped Project-Brain Sources

These roots are project-brain material, but Phase 3 should map them instead of
physically moving them unless the implementing session explicitly updates the
governing ADR contracts:

| Repo path | Project-brain role |
| --- | --- |
| `docs/adrs/` | `project-brain/decisions/adrs/` mapped source |
| `docs/superpowers/specs/` | `project-brain/specs/` mapped source |
| `docs/superpowers/plans/` | `project-brain/plans/` mapped source |
| `docs/agent-topics/` | `project-brain/instructions/topics/` mapped source |
| `plugins/agents/` | `project-brain/capabilities/agents/` mapped source or migrated capability root |

Phase 3 should create pointer/manifest files under the matching project-brain
folders so UI, search, and client projections can treat ADRs, specs, plans,
workflows, and instructions as project-brain content even when the physical
canonical file remains in `docs/`.

## Code Changes

- Extend `src.lib.brain_manifest` skeleton to include `config/` and `drafts/`.
- Replace canonical `get_shared_vault_*` call sites with project-brain-aware
  helpers.
- Add mapped-source metadata to the project-brain manifest or adjacent config
  so path resolution can include durable repo docs without copying them.
- Keep legacy helper names only as temporary wrappers where removing them in
  one step would make the migration unsafe.
- Update skill discovery, MCP bundle loading, dashboard page discovery, command
  discovery, generated surfaces, tests, and docs to read the migrated paths.
- Update `PYTHONPATH` construction that currently injects `shared-vault` so
  skill packages can still import under the new capability root.

## Verification

- Exhaustive `rg "shared-vault"` classification report: every remaining hit is
  historical, compatibility-expiring, or test fixture.
- Focused Python tests for path helpers, skill discovery, command discovery,
  dynamic plugin loading, MCP config generation, and `aug init`.
- Dashboard Jest tests for page/skill discovery and Browse transforms.
- `sync_agents check` after regeneration.
- Real-data proof: list real migrated Augur project skills from
  `project-brain/capabilities/skills`, load a real skill doc, and verify a real
  dashboard/Browse route shows that skill after migration.
