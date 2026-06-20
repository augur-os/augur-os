---
status: Implemented
date: '2026-03-31 (Updated: 2026-04-08)'
deciders:
- gsannikov
related:
- ADR-186
- ADR-479
- ADR-489
- ADR-490
hub: adaptive
tags:
- skills
- discovery
- platform-integration
- sync
superseded_by: null
---

# ADR-524: Skill Ownership Model — Augur, External, and Adopted Skills

## Context

The current skill architecture drifted into two incompatible models:

- `ADR-479` says `skills/` is the only Augur-managed source of truth, and client locations are external inventory or export surfaces.
- the previous version of `ADR-524` reintroduced a lifecycle based on client-local and client-global locations, with `eject/reset/shadowing` semantics.

That contradiction now shows up in implementation:

- discovery, lifecycle, and sync code disagree on what client paths mean
- Codex prompt mirrors and Codex native exports are treated inconsistently
- global client directories are partly treated as inventory and partly as default export targets
- cleanup is weak enough that stale generated artifacts and retired export formats can survive

The real user cases are not about local versus global ownership. They are about three practical categories:

1. skills built or fully owned inside Augur
2. skills discovered externally and left untouched
3. external skills that the user adopts into Augur while still wanting upstream awareness

The architecture should model those cases directly.

## Decision

### 1. Canonical source of truth

`skills/` is the only Augur-managed source of truth.

Anything outside `skills/` is not Augur-owned by default, regardless of whether it is project-local or user-global.

### 2. Ownership classes

Skills are classified by `ownership`, not by install location.

| Ownership | Location | Augur writes to it | Meaning |
|----------|----------|--------------------|---------|
| `augur` | `skills/` | Yes | Built or fully owned inside Augur |
| `external` | client-local or client-global locations outside `skills/` | No | Visible for awareness only |
| `adopted` | `skills/` | Yes | Managed by Augur, but retains upstream relationship |

#### `augur`

- lives in `skills/`
- is fully owned by Augur and the user
- exports to enabled clients using Augur-managed formatting
- does not require upstream tracking

#### `external`

- is discovered outside `skills/`
- is shown in discovery and UI for awareness
- is never rewritten, exported, cleaned up, or reformatted by Augur
- may appear in project or global scope, but that scope is observational metadata only

#### `adopted`

- lives in `skills/`
- exports like any other Augur-managed skill
- keeps upstream metadata because the user still wants update awareness, rebases, or upstream fixes
- covers both imported external skills and lightly or heavily modified upstream skills

### 3. Metadata contract

Keep the core metadata minimal.

Required:

- `ownership`: `augur | external | adopted`

Important optional metadata:

- `upstream`: first-class for `adopted`

`upstream` should carry enough information for future update workflows:

- upstream repository or source identifier
- upstream ref, version, or revision when known
- optional upstream subpath when the adopted skill came from a repo subtree

The following are explicitly *not* part of the core skill lifecycle contract:

- `enabled_clients`
- `install_channel`
- `scope`

Rationale:

- enabled clients come from Augur's global installation/config state
- install channel is informative but not architecturally important
- scope is useful for discovery and UI, but should not define ownership or lifecycle

### 4. Discovery model

Discovery assigns ownership by source, not by export format.

Rules:

- anything under `skills/` is Augur-managed (`augur` or `adopted`)
- anything outside `skills/` is `external` unless explicitly adopted into `skills/`
- prompt mirrors, native exports, and other generated client files are never authoritative ownership signals
- client-local vs client-global is not a lifecycle distinction

### 5. Export model

Export exists only to adapt Augur-managed skills to enabled clients.

Rules:

- export only `augur` and `adopted` skills
- export only to clients enabled in the current Augur installation
- do not export to unsupported or disabled clients
- do not write Augur-managed exports into user-global client directories by default
- repo-scoped client surfaces are the normal export targets

### 6. Repo vs global rule

Augur-owned skills sync in the Augur repo, not globally.

That means:

- repo-local client exports are normal
- global client directories are discovery targets for external inventory
- any future global export must be explicit user intent, not default sync behavior

### 7. Codex behavior

Codex has two explicit export surfaces:

1. prompt mirror export
2. native skill export

Both are client-specific export targets derived from `skills/`.

Neither is a source of truth, and neither defines lifecycle state. Lifecycle must never be inferred from whether a skill appears in prompts or native exports.

### 8. Cleanup is mandatory

Cleanup is part of sync, not a best-effort follow-up.

Rules:

- every sync pass reconciles expected managed exports against actual managed exports
- when a client is disabled, Augur deletes all Augur-managed exports for that client automatically
- when an export format is retired or renamed, old Augur-managed artifacts are deleted automatically
- cleanup touches only files proven to be Augur-managed via markers or manifests
- cleanup must never delete user-created or externally installed files

At minimum, cleanup must cover:

- generated prompt mirrors
- native skill export directories
- Augur-managed manifests
- stale files from retired export formats

### 9. Command direction

The old `eject/reset` lifecycle commands should not survive unchanged because they encode the wrong model.

The command family should move toward ownership-aware actions:

- import or adopt an external skill into `skills/`
- export or resync managed skills to enabled clients
- cleanup stale managed exports
- show status and upstream update state for adopted skills

## Consequences

### Positive

- resolves the contradiction between `ADR-479` and the previous `ADR-524`
- matches the real user cases more directly than local/global lifecycle states
- makes upstream-aware modified skills first-class via `adopted`
- prevents Augur from polluting user-global client environments by default
- clarifies Codex by treating prompt mirrors and native exports as explicit targets, not ownership states
- makes cleanup deterministic for disabled clients and retired export formats

### Negative

- requires migration away from current `source`-driven lifecycle assumptions
- lifecycle commands and UI labels need redesign
- some sync and discovery code will need deletion, not just renaming

### Neutral

- global client directories still matter, but only for awareness and external inventory
- enabled-client export remains valuable; it is just narrowed to repo-scoped managed artifacts
- existing Augur-owned skills in `skills/` remain valid under the new model

## Implementation Order

### Phase 1: Canonical model

1. Update ADRs, docs, and skill-authoring guidance to use `ownership`
2. Remove local/global as lifecycle language from architecture docs and command docs

### Phase 2: Discovery

1. Change discovery to classify by `skills/` versus external inventory
2. Treat local/global as discovery metadata only when needed for UI
3. Stop inferring lifecycle from client-export locations

### Phase 3: Export

1. Read enabled clients from global Augur config
2. Export only `augur` and `adopted` skills
3. Restrict default export to repo-local client surfaces
4. Split Codex prompt and native exports into explicit target behaviors

### Phase 4: Cleanup

1. Reconcile managed exports every sync pass
2. Remove managed leftovers for disabled clients automatically
3. Remove managed leftovers from retired export formats automatically

### Phase 5: Command migration

1. Deprecate `eject/reset` lifecycle semantics
2. Introduce ownership-aware adopt/import, export/resync, cleanup, and upstream-status flows

## Alternatives Considered

### Alternative 1: Keep the previous location-based lifecycle

Retain `Augur`, `Platform Local`, and `Platform Global` as the primary states. Rejected because it conflicts with `ADR-479`, keeps the current conceptual drift, and overfits storage location rather than ownership intent.

### Alternative 2: Two classes only (`augur` and `external`)

Treat upstream-aware modified skills as ordinary Augur skills with optional metadata. Rejected because the user's actual workflow needs a distinct class for imported-but-managed skills that still want upstream rebases and updates.

### Alternative 3: Keep default global export for Augur-managed skills

Write managed exports into user-global client directories automatically. Rejected because it pollutes the user's broader environment and turns discovery targets into implicit lifecycle surfaces again.

## References

- Design spec: `docs/superpowers/specs/2026-04-08-skill-ownership-sync-architecture-design.md`
- ADR-186: Sync Agents Refactor
- ADR-479: Multi-Client Skill Structure
- ADR-489: Portable Skills Pack
- ADR-490: Framework migration — dual-alias architecture

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "skill discovery and lifecycle APIs shift from source/location semantics to ownership semantics"
    - "client export logic becomes enabled-client-only and repo-scoped by default"
    - "Codex prompt mirror and native skill export become explicit target behaviors"
  patterns_deprecated:
    - "platform-local/platform-global lifecycle model"
    - "treating client export paths as ownership signals"
    - "default global export for Augur-managed skills"
    - "eject/reset as primary lifecycle commands"
  files_affected:
    - src/plugins/skill_discovery.py
    - src/config/paths.py
    - src/mcp/augur_core/tools/core/skill_lifecycle.py
    - src/mcp/augur_core/tools/core/models.py
    - skills/ai/scripts/sync_agents/skill_sync.py
    - docs/creating-skills.md
    - docs/agent-topics/SKILLS.md
    - docs/generated/adr-index.md
```
