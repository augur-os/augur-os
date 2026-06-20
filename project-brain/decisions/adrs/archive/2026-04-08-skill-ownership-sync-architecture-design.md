# Skill Ownership And Cross-Client Sync Architecture

**Date:** 2026-04-08
**Status:** Draft
**Scope:** Replace the current skill provenance model with a simpler ownership model for discovery, export, cleanup, and future ADR updates.

## Problem

The current architecture mixes two incompatible ideas:

- `ADR-479` says `skills/` is the only Augur-managed source of truth and client installs are external inventory.
- `ADR-524` reintroduces a lifecycle model based on client-local and client-global locations, plus eject/reset/shadowing behavior.

That drift now shows up in implementation:

- discovery, lifecycle, and sync code do not agree on what a client path means
- Codex paths are split inconsistently between prompt mirrors and native skill exports
- global client directories are treated partly as inventory and partly as export targets
- cleanup is not strong enough, so stale generated files and old export formats can survive

The result is a fragile sync pipeline whose complexity no longer matches the real user cases.

## Goals

1. Make `skills/` the only Augur-managed source of truth again.
2. Separate skill ownership from install scope.
3. Preserve support for upstream-aware modified external skills.
4. Export only to enabled clients in the current Augur installation.
5. Make cleanup mandatory so disabled or retired client targets leave no Augur-managed leftovers.
6. Clarify Codex behavior without treating prompt mirrors and native exports as competing sources.

## Non-Goals

- Auto-managing external skills that Augur does not own
- Writing Augur-managed skills into user-global client directories by default
- Preserving old lifecycle vocabulary when it conflicts with the simpler model
- Encoding enabled-client state or install channel into per-skill metadata

## User Cases

The model must support these concrete cases:

1. A user creates a skill from scratch or changes it heavily: it is `augur`.
2. A user installs an external skill through a client and leaves it untouched: it is `external`.
3. A user installs a skill through Augur and wants it exported to enabled clients in Augur format: it is `adopted`.
4. A user lightly patches an external skill such as `superpowers` but still wants upstream fixes: it is `adopted`.
5. A user has global skills Augur should not touch but should still surface: they are `external`.
6. A user heavily customizes an open-source skill but still wants rebases or update awareness: it is `adopted`.

## Recommended Approach

Use a clean ownership rewrite.

- Replace the current provenance/lifecycle model with an ownership model.
- Treat client directories only as export targets or external inventory.
- Remove local/global as lifecycle concepts.
- Keep upstream tracking only where it materially matters: adopted skills.

This is preferable to a compatibility bridge because the existing drift is conceptual, not just operational.

## Ownership Model

### Canonical Rule

`skills/` is the only Augur-managed source of truth.

### Ownership Classes

#### `augur`

- Lives in `skills/`
- Fully owned by Augur and the user
- Exported to enabled clients using Augur-managed client formatting
- Does not require upstream metadata

#### `external`

- Discovered outside `skills/` from client-local or client-global locations
- Shown for awareness and inventory
- Never rewritten, reformatted, exported, or cleaned up by Augur
- May appear in project or global scope, but scope is observational metadata only

#### `adopted`

- Lives in `skills/`
- Owned and exported by Augur like an `augur` skill
- Retains upstream metadata because the user wants future updates, rebases, or patch tracking
- Covers skills imported through Augur and lightly or heavily modified external skills

## Metadata Contract

Keep skill metadata minimal.

### Required

- `ownership`: `augur | external | adopted`

### Important Optional Metadata

- `upstream`: first-class for `adopted`

`upstream` should carry enough information for future update workflows:

- upstream repository or source identifier
- upstream ref, version, or revision when known
- optional upstream subpath when the adopted skill came from a repo subtree

### Explicitly Not Core Skill Lifecycle Metadata

- `enabled_clients`
- `install_channel`
- `scope`

Rationale:

- enabled clients come from global Augur install/config state
- install channel is not important enough to drive architecture
- scope is useful for discovery and UI but should not shape ownership semantics

## Discovery Model

Discovery should assign ownership by source, not by export format.

### Discovery Sources

- `skills/` -> managed skills (`augur` or `adopted`)
- enabled and disabled client-local directories -> possible `external` inventory
- client-global directories -> possible `external` inventory

### Discovery Rules

- Anything under `skills/` is Augur-managed.
- Anything outside `skills/` is external inventory unless explicitly imported into `skills/`.
- Prompt files, generated stubs, native exports, and mirrors are never authoritative ownership signals.
- Client-local vs client-global is not a lifecycle distinction.

## Export Model

### Core Rule

Export exists only to adapt Augur-managed skills to enabled clients.

### Export Rules

- Export only `augur` and `adopted` skills.
- Export only to clients that are enabled in the current Augur installation.
- Do not export to unsupported or disabled clients.
- Do not export Augur-managed skills into global client directories by default.
- Repo-scoped client surfaces are the default export targets.

### Repo vs Global Rule

Augur-owned skills sync in the Augur repo, not globally.

That means:

- repo-local client exports are normal
- global client directories are discovery targets for external inventory
- any future global export must be explicit user intent, not default sync behavior

## Codex Behavior

Codex should be modeled as two explicit export surfaces:

1. prompt mirror export
2. native skill export

Rules:

- neither surface is a source of truth
- both are client-specific export targets derived from `skills/`
- both participate in cleanup if managed by Augur
- lifecycle must never be inferred from whether a skill appears in prompts or native exports

This removes the current ambiguity where one code path treats `.codex/prompts/` as canonical and another treats `.codex/skills/` or native export locations as canonical.

## Cleanup Model

Cleanup is mandatory, not optional.

### Cleanup Rules

- Every sync pass must reconcile expected managed exports against actual managed exports.
- When a client is disabled, Augur deletes all Augur-managed exports for that client automatically.
- When an export format is retired or renamed, old Augur-managed artifacts are deleted automatically.
- Cleanup only touches files proven to be Augur-managed via markers or manifests.
- Cleanup must never delete user-created or client-installed external files.

### Cleanup Targets

At minimum, cleanup must cover:

- generated prompt mirrors
- native skill export directories
- Augur-managed manifests
- stale files from older export formats

## Commands Direction

The old lifecycle commands should not survive unchanged because they encode the wrong model.

The new command family should align with ownership:

- import or adopt an external skill into `skills/`
- export or resync managed skills to enabled clients
- cleanup stale managed exports
- status and update workflows for adopted skills with upstream awareness

`eject/reset` should be considered deprecated after migration because ownership, not client location, becomes the primary concept.

## Migration Plan

1. Rewrite the ADR around ownership rather than provenance by location.
2. Change discovery to classify by `skills/` vs external inventory.
3. Treat existing client-local and client-global paths as scope metadata only.
4. Split Codex prompt and native exports into explicit target behaviors.
5. Restrict default export to enabled clients only.
6. Add deterministic cleanup for disabled clients and retired export formats.
7. Migrate UI and command language away from platform-local/platform-global lifecycle wording.

## Consequences

### Positive

- Resolves the contradiction between `ADR-479` and `ADR-524`
- Makes real-world cases like lightly patched upstream skills first-class
- Prevents Augur from polluting user-global client environments by default
- Shrinks sync responsibility to enabled-client export plus cleanup
- Clarifies Codex by separating surfaces from ownership

### Negative

- Requires migration away from current `source`-driven lifecycle assumptions
- Existing lifecycle commands and labels need redesign
- Some current discovery and sync code will need deletion, not just renaming

## Recommendation

Adopt the clean ownership rewrite and update the canonical ADR accordingly.

The resulting architecture should be summarized as:

- `skills/` is canonical
- ownership is `augur | external | adopted`
- upstream matters primarily for `adopted`
- enabled clients come from global config, not skill metadata
- exports are repo-scoped and enabled-client-only
- cleanup is mandatory and automatic for Augur-managed leftovers
