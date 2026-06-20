---
title: Shared Vault Enterprise Overlay Design
date: 2026-05-03
status: proposed
scope: design
related:
  - 2026-05-02-obsidian-first-vault-root-migration-design.md
  - 2026-04-30-vault-browse-surface-refactor-design.md
  - 2026-04-13-existing-vault-wiki-compounding-design.md
  - 2026-04-28-cross-client-bundle-architecture-design.md
---

# Shared Vault Enterprise Overlay Design

## Purpose

Augur needs one simple model that works for personal use and for an initial enterprise deployment to a team of roughly 40 engineers across roles such as developer, architect, validation, DevOps, product, and management.

The target model is a local-first project repo that contains both the deployable Augur product and a shared team brain, plus one private vault per user. The same vault structure is used in both places. The difference is ownership and write policy, not folder semantics.

## Decisions

- Add `shared-vault/` at the project repo root as the shared team brain.
- Use the same root contract in `shared-vault/` and each configured private vault.
- Retire repo-root `skills/` in the final architecture.
- Store canonical shared/team skills in `shared-vault/skills/`.
- Store canonical personal/private skills in the user's private vault `skills/`.
- Keep framework and runtime libraries in `src/`, dashboard app code in `apps/`, deploy/runtime config in `config/`, and product docs in `docs/`.
- Merge shared and private content for read/search/Browse context.
- Write new user synthesis to the private vault by default.
- Promote private material into `shared-vault/` only through PR-reviewed append-only promotion packets.
- Integrate accepted promotion packets into canonical shared wiki, notes, and skills through a compiler or maintainer process, not through direct default agent writes.
- Initial enterprise deployment is local-first per engineer: each engineer clones the repo, gets `shared-vault/`, mounts a private vault, and syncs shared changes through Git.
- Roles are views and metadata, with role playbook entrypoints under `shared-vault/notes/roles/`.

## Repository Shape

Final target:

```text
project-repo/
  src/
  apps/
  config/
  docs/
  tests/
  shared-vault/
    inbox/
    notes/
    sources/
    wiki/
    skills/
    drafts/
    archive/
    config/

private-vault/
  inbox/
  notes/
  sources/
  wiki/
  skills/
  drafts/
  archive/
  config/
```

`shared-vault/` is repo-owned and team-visible. A private vault is user-owned and may be a separate local or remote Git repo.

## Vault Root Contract

The shared and private vault roots use the same meanings:

| Root | Meaning | Shared Behavior | Private Behavior |
| --- | --- | --- | --- |
| `inbox/` | Intake, review queues, and promotion packets | Team intake and promotion review | Personal intake |
| `notes/` | Human-authored notes and role/domain playbooks | Team-readable knowledge | Personal knowledge |
| `sources/` | Source cards and captured source material | Team-approved sources | Personal sources |
| `wiki/` | Compiled concept and query knowledge | Canonical shared brain | Personal compiled brain |
| `skills/` | Canonical skills and capability bundles | Team skills | Private skills |
| `drafts/` | Inactive drafts and staged work | Excluded from normal operation | Excluded from normal operation |
| `archive/` | Historical inactive material | Excluded from normal operation | Excluded from normal operation |
| `config/` | Durable non-secret human-editable config | Team config | Personal config |

Runtime state, generated indexes, caches, logs, and sessions remain outside vaults through path helpers such as `get_runtime_dir()`, `get_cache_dir()`, and `get_logs_dir()`.

## Read And Write Model

Daily use should feel like one brain:

```text
read context = shared-vault + private-vault
default write = private-vault
shared contribution = append-only promotion packet PR
canonical shared update = compiler or maintainer integration
```

Agents, `/ask`, Browse actions, wiki compounding, and intake workflows may read from shared and private sources when the user has mounted both. New synthesis writes to the private vault by default, even in enterprise mode.

Shared writes require explicit promotion. No agent should silently write private material into `shared-vault/wiki/`, `shared-vault/notes/`, or `shared-vault/skills/`.

## Promotion Packets

PR-gated promotion is only workable if it avoids many users editing the same canonical shared files. Promotion therefore uses append-only packet folders.

Example:

```text
shared-vault/inbox/promotions/
  2026-05-03-<user>-topic-slug/
    manifest.yaml
    synthesis.md
    sources/
    proposed-actions.md
    proposed-links.md
```

Rules:

- Promotion PRs add new packet folders under `shared-vault/inbox/promotions/`.
- Promotion PRs should not directly edit canonical shared wiki pages or generated indexes by default.
- Packet folder names include date, contributor identity, and topic slug to reduce collision risk.
- `manifest.yaml` records origin, source hashes, intended destination, sensitivity, role/domain tags, and integration status.
- Packet contents preserve provenance from private notes, `/ask` outcomes, sources, and generated synthesis.
- Accepted packets are later integrated into `shared-vault/wiki/`, `shared-vault/notes/`, `shared-vault/sources/`, or `shared-vault/skills/` by a shared compiler or maintainer.
- Generated indexes and registries are regenerated from canonical content and packets; they are not hand-edited.

This keeps PR review while sharply reducing merge-conflict pressure. Most contributors add new folders. Maintainers or automation handle the smaller number of canonical integration edits.

## Wiki Compounding

Wiki compounding follows the same ownership model:

- Personal interactions compound into the private vault wiki by default.
- Shared wiki updates are created as promotion packets first.
- The shared wiki compiler consumes accepted promotion packets and rewrites canonical shared concept/query pages in batches.
- If a packet cannot be integrated cleanly, it remains accepted-but-unintegrated and appears as shared wiki debt.
- Direct same-turn writes to canonical shared wiki pages are out of scope for default agents.

The shared wiki is a durable team artifact. It should be stable enough for 40-person use and protected from accidental leakage or conflict-heavy edits.

## Browse And Search

Browse merges shared and private material by default:

```text
Browse = shared-vault + private-vault
```

Every result must expose origin and scope:

- origin: `shared` or `private`
- owner or source user when known
- scope: `team`, `role`, `project`, `personal`, `draft`, `archive`
- promotion state: `private`, `packet`, `accepted`, `integrated`
- freshness and source count where useful

Filters can isolate shared-only or private-only content. The default view remains merged because the user experience should feel like one useful brain.

If shared and private items conflict, private can win for the local user's answer context, but shared remains the canonical team source. The UI must not hide the origin difference.

## Role Views

Roles are not top-level vault folders. Physical files stay organized by durable content type and domain. Roles are metadata, ranking signals, and human-readable entrypoints.

Role playbooks live in:

```text
shared-vault/notes/roles/
  developer.md
  architect.md
  validation.md
  devops.md
  product.md
  manager.md
```

Role-specific Browse views filter and rank skills, actions, prompts, wiki pages, sources, and notes by role metadata. This avoids duplicating the same content into role folders while still giving each role a clear starting point.

## Skills And Runtime Migration

Final canonical skill roots:

```text
project-repo/shared-vault/skills/
private-vault/skills/
```

No scanner should assume repo-root `skills/` in the final state.

Current repo-root skills contain mixed responsibilities and must be classified before migration:

| Current Responsibility | Target |
| --- | --- |
| User-facing capability bundle | `shared-vault/skills/<skill>/` |
| Private capability bundle | private vault `skills/<skill>/` |
| Framework/runtime library | `src/lib/...` |
| Dashboard application route | `apps/` |
| Deploy/runtime configuration | `config/` |
| Generated client export | Generated client-specific output, not canonical source |

The migration should not blindly move all current root `skills/` content into `shared-vault/skills/`. Runtime libraries must be extracted first so that vault skills remain capability bundles, not framework implementation dumps.

During migration, a temporary compatibility path may exist only as a transition guard. It must not become a permanent alias.

## Deployment Model

Initial enterprise deployment is local-first:

1. Engineer clones the project repo.
2. The clone includes product/runtime code and `shared-vault/`.
3. Engineer mounts or creates a private vault with the same root contract.
4. Local dashboard, agents, MCP servers, Browse, and wiki tooling use merged shared/private context.
5. Shared changes happen through Git branches and PRs.
6. Promotion PRs usually add append-only packet folders.

A hosted shared service is a future phase. The initial deployment should prove the local-first model before adding server-side auth, multitenancy, or central hosted indexing.

## Rollout Phases

### Phase 1: Shared Vault Contract

- Add `shared-vault/` with the standard vault root structure.
- Add path helpers such as `get_shared_vault_dir()` and private-vault-aware merged helpers.
- Add origin metadata to discovery results.
- Ensure runtime, cache, log, and generated state do not move into either vault.

### Phase 2: Promotion Packets

- Add `shared-vault/inbox/promotions/`.
- Define packet schema and validation.
- Add a promotion helper that creates append-only packet folders.
- Ensure default promotion does not edit canonical shared wiki/index files.

### Phase 3: Merged Browse And Role Views

- Merge shared/private Browse results with origin badges and filters.
- Add role playbooks under `shared-vault/notes/roles/`.
- Add role metadata support for notes, wiki pages, skills, prompts, actions, and sources.

### Phase 4: Skill-Root Migration

- Inventory every current repo-root skill.
- Classify each item as capability bundle, framework library, dashboard app code, config, generated output, or archive candidate.
- Move capability bundles to `shared-vault/skills/`.
- Move reusable runtime/library code to `src/lib/`.
- Update MCP, client export, dashboard, Browse, and wiki discovery to use only shared/private skill roots.
- Add architecture tests that fail on new repo-root `skills/` discovery assumptions.

### Phase 5: Retire Root `skills/`

- Remove remaining repo-root skill assumptions.
- Delete or block repo-root `skills/`.
- Keep generated client exports separate from canonical skill roots.
- Verify personal and enterprise modes end to end.

## Acceptance Criteria

- Personal mode works with only a private vault.
- Enterprise mode works with `shared-vault/` plus a private vault.
- `shared-vault/` and private vaults use the same root contract.
- Browse shows merged shared/private results with visible origin and filters.
- Wiki compounding writes private by default.
- Shared promotion creates append-only packet PRs.
- Promotion packet PRs do not directly edit canonical shared wiki pages or generated indexes by default.
- The shared compiler can integrate accepted packets into canonical shared wiki pages.
- Skills are discovered from `shared-vault/skills/` and private vault `skills/`.
- No final runtime path depends on repo-root `skills/`.
- Framework libraries live under `src/lib/`, not in vault roots.
- Dashboard app code lives under `apps/`, not in vault skill folders.
- Role views work through metadata and playbooks, not role-based top-level folders.

## Risks And Mitigations

### Merge Conflicts In Shared Canonical Files

Risk: A PR-based model can create constant conflicts if many people edit the same shared wiki or index files.

Mitigation: Promotions are append-only packet folders by default. Canonical integration happens in batches through a compiler or maintainer.

### Private Data Leakage

Risk: Agents may accidentally write private synthesis into the shared repo.

Mitigation: Default write target is private. Shared writes require explicit promotion and packet review.

### Runtime Breakage From Retiring Root `skills/`

Risk: Current runtime code assumes repo-root `skills/`.

Mitigation: Classify and migrate in phases. Extract framework libraries to `src/lib/` before deleting root `skills/`. Add architecture tests before final retirement.

### Browse Trust Confusion

Risk: A merged Browse view can blur shared and private provenance.

Mitigation: Every result must show origin and scope. Filters must allow shared-only and private-only inspection.

### Role Duplication

Risk: Role folders can duplicate knowledge and make cross-role material hard to maintain.

Mitigation: Roles are metadata and views. Only role playbook entrypoints are physical role files.

## Non-Goals

- No hosted enterprise service in the first deployment.
- No complex RBAC system in the first deployment.
- No automatic private-to-shared writes.
- No direct vault skill TSX dashboard code.
- No bulk root-skill migration without classification.
- No permanent compatibility alias for repo-root `skills/`.
- No manual editing of generated indexes or registries.
