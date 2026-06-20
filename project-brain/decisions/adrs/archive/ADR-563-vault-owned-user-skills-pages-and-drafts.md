---
status: Implemented
date: 2026-04-23
deciders:
- Gur Sannikov
- Codex
related:
- ADR-270
- ADR-557
hub: brain
tags:
- vault
- skills
- pages
- staging
- lifecycle
superseded_by: null
---

# ADR-563: Vault-Owned User Skills, Pages, and Draft Staging

## Context

Augur currently uses the repo-local `staging/` tree as a holding area for non-MVP skills and deferred page payloads. That made sense while the staged release model was about curating future product payloads inside the repo. It does not match the current ownership reality.

The current user is also the first real user of Augur. In practice, everything under `staging/` is private non-MVP work until it is deliberately promoted into the live product tree. Keeping that material in the core repo mixes three different concerns:

1. shipped Augur product surfaces
2. active private user surfaces
3. unfinished draft experiments

That mixed ownership makes the architecture muddy and weakens the GTM boundary that the user wants:

- the second brain stays user-owned
- Augur attaches to it as infrastructure
- user-private skills and pages live with the user's vault, not inside product code

There is also a page-source problem. Dashboard routes are generated/mounted during build. Copying user page sources into repo app paths creates a double-source system unless the ownership contract is explicit.

## Decision

Use the external vault as the canonical home for user-owned skills, user-owned pages, and private draft staging.

The vault surface is split into three ownership states:

```text
get_vault_dir()/
  _drafts/
    staging/
  skills/
  pages/
```

### 1. Draft staging

Move the current repo-local `staging/` tree into:

```text
get_vault_dir() / "_drafts" / "staging"
```

This path preserves the existing staged release buckets (`r1`, `r2`, `r3`, `r4`, `later`) without pretending they are active user or product surfaces.

`get_vault_dir() / "_drafts" / ...` is explicitly non-canonical and must be ignored by:

- skill discovery
- page discovery
- dashboard mount/build
- client sync/export
- RAG/wiki indexing
- generic autoloops and hygiene passes, unless explicitly targeted

### 2. Active user skills

Active private user skills live in:

```text
get_vault_dir() / "skills" / <skill>
```

These are canonical user-owned skills. They are discoverable and exportable, but are not part of shipped Augur by default.

### 3. Active user pages

Active private user pages live in:

```text
get_vault_dir() / "pages" / <page-or-app>
```

This path is for production-ready private user pages only.

Vault pages are allowed to be discovered and mounted. If dashboard build needs generated copies or wrappers, those are derived outputs only. The canonical source remains the vault page path.

### 4. Product surfaces remain in core

Shipped Augur surfaces stay in the core repo:

```text
skills/
apps/dashboard/
```

### 5. Skill/page lifecycle

The lifecycle states are:

- `external`
- `installed-external`
- `draft`
- `active-private`
- `product`
- `deprecated`
- `discarded`

Mapped to storage:

- `draft` -> `get_vault_dir() / "_drafts" / ...`
- `active-private skill` -> `get_vault_dir() / "skills" / ...`
- `active-private page` -> `get_vault_dir() / "pages" / ...`
- `product` -> repo-owned product paths

### 6. Promotion model

Promotion is explicit:

- `_drafts/staging/...` -> `vault/skills/...`
- `_drafts/staging/...` -> `vault/pages/...`
- `vault/skills/...` -> repo `skills/...`
- `vault/pages/...` -> repo product page sources

Do not promote unfinished draft material directly into shipped core.

## Consequences

### Positive

- Ownership becomes explicit: shipped product, active user surfaces, and unfinished drafts no longer share one repo bucket.
- The second-brain promise becomes clearer: user-private skills and pages live with the user vault.
- Draft work can stay messy without polluting discovery, RAG, or dashboard wiring.
- Promotion becomes a deliberate state change instead of a fuzzy repo convention.

### Negative

- Discovery, mount, and sync logic must learn about vault-owned active surfaces.
- Existing assumptions that canonical skills only live under repo `skills/` will need to be updated.
- Page mounting from the vault needs a stricter source-of-truth contract so generated outputs are never treated as editable source.

### Neutral

- Shipped Augur skills and pages remain repo-owned.
- External marketplace/client skill install flows still matter for `external -> installed-external`.
- The staged release concept still exists, but as private draft inventory in the vault rather than as a long-term core repo surface.

## Release Boundary

This ADR is not part of the current production-release acceptance criteria until it is implemented and verified. For the production cut, Augur must not claim vault-owned private skills or vault-owned private dashboard pages as shipped behavior.

Current release behavior remains:

- shipped product skills and pages are repo-owned
- repo `staging/` is not advertised as a live user/private surface
- vault wiki, vault notes, documents, RAG, `/ask`, and concept-first wiki compounding remain in scope

This keeps the wiki/LLM release gate focused on the implemented ADR-546/ADR-561 concept-first wiki system while preserving ADR-563 as the next ownership-boundary implementation.

## Alternatives Considered

### Keep `staging/` in the Core Repo

Rejected. It keeps user-private draft work mixed into the product repo and preserves the ownership ambiguity that this ADR is trying to remove.

### Move All Staged Skills Directly into `vault/skills`

Rejected. Most staged skills are not ready. Putting unfinished work into the active user skill surface would pollute discovery, exports, and daily use.

### Keep User Pages Only in Core Until the Mount System Is Perfect

Rejected. It keeps private page ownership on the wrong side of the boundary. The right answer is to make vault pages canonical and treat generated mount outputs as derived artifacts.

## References

- ADR-270: Path separation
- ADR-557: MVP main and staged release payloads
- `staging/README.md`
- `apps/dashboard/lib/plugin-discovery/page-discovery.ts`
- `apps/dashboard/scripts/mount-plugins.ts`
- `src/plugins/skill_discovery.py`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: staging/
      to: get_vault_dir() / "_drafts" / "staging"
  apis_changed:
    - src.plugins.skill_discovery.discover_all_skills
    - apps/dashboard/lib/plugin-discovery/page-discovery.ts
    - apps/dashboard/scripts/mount-plugins.ts
  patterns_deprecated:
    - repo-local staging as the long-term home for user-private non-MVP work
    - canonical user-private skill ownership inside the core repo
  files_affected:
    - staging/**
    - src/plugins/skill_discovery.py
    - apps/dashboard/lib/plugin-discovery/page-discovery.ts
    - apps/dashboard/scripts/mount-plugins.ts
    - skills/rag/scripts/_indexer_helpers.py
    - skills/ingest/scripts/wiki_scanner.py
```

## Implementation Prompt

> Paste this into Codex to execute this ADR.

**Team name**: `adr-563-vault-user-surfaces`

### Phase 1: Ownership Split
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Add vault path helpers/constants for `_drafts`, `skills`, and `pages` user surfaces | `src/config/paths.py`, related config helpers |
| 1.2 | developer | low | Move repo `staging/` into `get_vault_dir()/_drafts/staging/` with the existing tree preserved | vault paths, `staging/**`, migration helpers |
| 1.3 | developer | low | Update discovery and indexing code to ignore `get_vault_dir()/_drafts/**` | discovery and RAG/indexing code |

### Phase 2: Active User Surfaces
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Extend skill discovery to treat `get_vault_dir()/skills/*` as canonical active user skills | `src/plugins/skill_discovery.py`, dashboard consumers |
| 2.2 | developer | medium | Define `get_vault_dir()/pages/*` as canonical active user pages and mount them through generated outputs only | `page-discovery.ts`, `mount-plugins.ts`, registry generation |
| 2.3 | developer | low | Add tests covering ignore rules, vault skill discovery, and vault page canonical ownership | tests for discovery, mount, and indexing |

### Completion Criteria

- [ ] Repo `staging/` is no longer the canonical home of private non-MVP work
- [ ] `get_vault_dir()/_drafts/**` is ignored by discovery, dashboard mount, sync, and RAG
- [ ] `get_vault_dir()/skills/**` is treated as active canonical user skill source
- [ ] `get_vault_dir()/pages/**` is treated as active canonical user page source
- [ ] Generated dashboard page outputs are treated as derived artifacts, not source
- [ ] ADR status updated after implementation and verification
