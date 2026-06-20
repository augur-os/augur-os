# Vault User Surfaces Phase 1 Design

Date: 2026-04-23
Status: Proposed
Scope: Ownership split for private non-MVP skills, draft staging relocation, and active vault-backed user skills

## Summary

> Superseded path note: the 2026-05-02 Obsidian-first vault root design replaces `_drafts/staging/` with tracked `drafts/staging/`. The ownership model remains: inactive drafts are not discovered or exported; active private skill implementations live under `skills/`.

Phase 1 moves Augur away from treating repo `staging/` as the holding area for private non-MVP work. The new ownership model is:

- repo `skills/` = shipped Augur product skills only
- `get_vault_dir()/drafts/staging/` = ignored private draft inventory
- `get_vault_dir()/skills/` = active private user skills

This phase also removes repo `staging/` entirely after migration, and makes vault skills discoverable and auto-exported by default. It does not implement vault page mounting yet.

## Problem

The current repo-local `staging/` tree mixes three concerns:

1. future product candidates
2. private user work
3. unfinished drafts

That breaks the desired second-brain boundary. The user wants private skills to live with the user-owned vault, not in the core product repo. At the same time, not all staged skills are ready to become active user skills, so the design needs both an active user-skill surface and an ignored draft surface.

Current page architecture also uses generated dashboard routes and mounted outputs. Solving vault page ownership requires a stricter source-of-truth contract, so that concern is deferred from this phase.

## Goals

- Remove repo `staging/` as the canonical home for private non-MVP work
- Preserve the current staged tree as-is under the vault
- Introduce an ignored draft area for unfinished private work
- Introduce an active vault-backed skill area for real private user skills
- Make active vault skills auto-export to enabled clients by default
- Keep shipped Augur skills in repo `skills/`
- Avoid dual source-of-truth behavior during the migration

## Non-Goals

- Vault page mounting or copying
- Promotion tooling UI
- Automatic content cleanup or quality filtering during migration
- Reworking the full external marketplace/install lifecycle
- Productizing any staged draft content during the move

## Target State

```text
augur-core/
  skills/                      # shipped Augur skills only
  apps/dashboard/              # shipped product dashboard surfaces
  src/                         # runtime, MCP, generators, sync, build logic

vault/
  drafts/
    staging/
      r1/
      r2/
      r3/
      r4/
      later/
  skills/
    <user-skill>/
      SKILL.md
      augur/
      scripts/
      assets/
      references/
  pages/                       # reserved for later phase, out of scope here
```

## Ownership Model

### Repo `skills/`

- Ownership: Augur
- Meaning: shipped product skill
- Discovery: yes
- Export: yes
- Canonical: yes

### `get_vault_dir()/drafts/staging/`

- Ownership: user
- Meaning: unfinished, private, non-canonical draft inventory
- Discovery: no
- Export: no
- Dashboard mount/build: no
- RAG/wiki/indexing: no
- Canonical: no

### `get_vault_dir()/skills/`

- Ownership: user
- Meaning: active private user skills
- Discovery: yes
- Export: yes, automatically
- Dashboard participation: allowed if skill metadata contributes active surfaces
- Canonical: yes

## Lifecycle Model

Phase 1 uses these states:

- `external`
- `installed-external`
- `draft`
- `active-private`
- `product`
- `deprecated`
- `discarded`

### Storage mapping

- `draft` -> `get_vault_dir()/drafts/staging/...`
- `active-private` -> `get_vault_dir()/skills/<skill>`
- `product` -> repo `skills/<skill>`

### Allowed transitions

- `external -> installed-external`
- `installed-external -> draft`
- `installed-external -> active-private`
- `draft -> active-private`
- `active-private -> product`
- `active-private -> deprecated`
- `draft -> discarded`
- `external -> discarded`

## Discovery Design

After phase 1, canonical skill discovery reads from three sources:

1. repo `skills/*`
2. `get_vault_dir()/skills/*`
3. external client skill dirs for review-only awareness

It must explicitly ignore:

- `get_vault_dir()/drafts/**`
- repo `staging/**` because the repo path should no longer exist

### Required metadata

Discovery records should distinguish:

- `ownership: augur | user | external`
- `source_root: repo | vault | external-client`
- `canonical: true | false`

This prevents Browse, sync, and promotion logic from collapsing all skills into one ownership class.

## Export Design

For this phase, vault skills are active by default.

Rule:

- any skill under `get_vault_dir()/skills/*` is auto-exported to enabled clients using the same managed propagation flow as repo-backed canonical skills

Vault skills remain user-owned in metadata and UX even though they are managed for export.

## Migration Design

### Step 1: Add path helpers

Add explicit helpers for:

- `get_vault_dir() / "drafts"`
- `get_vault_dir() / "drafts" / "staging"`
- `get_vault_dir() / "skills"`

`get_vault_dir() / "pages"` may be reserved but should not be activated in this phase.

### Step 2: Move staged content

Move:

```text
repo staging/** -> get_vault_dir()/drafts/staging/**
```

The tree should be preserved exactly. This is not a cleanup or reclassification step.

After verification, remove repo `staging/` entirely.

### Step 3: Ignore drafts centrally

Update all relevant systems so `drafts` is ignored:

- discovery
- dashboard mount/build
- sync/export
- RAG/wiki/indexing
- hygiene/autoloops unless explicitly targeted

### Step 4: Activate vault skills

Extend canonical skill discovery and export to include:

```text
get_vault_dir()/skills/*
```

## Dashboard Scope

This phase does not redesign vault page discovery or mounting.

`get_vault_dir()/pages` is reserved for a later phase. Page-related systems should not adopt new behavior in this implementation beyond avoiding accidental assumptions that all future user surfaces must stay inside the repo.

This scope cut is intentional. The ownership split for skills can be implemented cleanly without dragging page duplication and mount semantics into the same rollout.

## Risks

### 1. Hidden repo-only assumptions

Some consumers assume canonical skills only live under repo `skills/`. These will need targeted fixes once vault skills become active.

### 2. Draft leakage

If `drafts` exclusion is incomplete, draft content could leak into discovery, sync, or RAG.

### 3. Test and docs drift

Many tests and docs currently mention repo `staging/`. Those references must be updated in the same rollout.

## Verification

Minimum verification must prove four boundaries:

1. draft skill under `drafts/staging` is invisible to discovery
2. draft skill under `drafts/staging` is not exported
3. draft skill under `drafts/staging` is not indexed by RAG/wiki
4. active skill under `vault/skills` is discovered with `ownership=user`
5. active skill under `vault/skills` is exported to enabled clients
6. repo product skills still discover/export as before
7. no active code path depends on repo `staging/`

## Implementation Strategy

Recommended execution order:

### Chunk 1: Ownership cut

- add vault helpers
- migrate repo `staging/` into vault `drafts/staging`
- remove repo `staging/`
- add ignore rules for `drafts`

### Chunk 2: Active user skills

- extend discovery to `vault/skills`
- auto-export vault skills
- update downstream consumers and tests

This keeps the rollout bounded and reduces the risk of mixing migration bugs with page-mount redesign.

## Alternatives Considered

### Keep repo `staging/` and add vault skills later

Rejected. It leaves the ownership boundary muddy and preserves the current confusion.

### Move all staged skills directly into `vault/skills`

Rejected. Most staged skills are not ready, and phase 1 needs a real draft area.

### Include vault page mounting in the same phase

Rejected. It expands scope into page-source duplication and dashboard mount semantics before the ownership split is stable.

## Open Follow-Up

Phase 2 should design the contract for `get_vault_dir()/pages`:

- canonical source rules
- how generated dashboard outputs remain derived artifacts only
- how discovery and mount treat vault pages without creating ambiguous editable copies
