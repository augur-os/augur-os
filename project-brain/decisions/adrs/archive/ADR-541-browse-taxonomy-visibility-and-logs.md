---
status: Implemented
date: '2026-04-09'
deciders:
- Gur Sannikov
related:
- ADR-539
- ADR-540
hub: adaptive
tags:
- browse
- dashboard
- taxonomy
- commands
- integrations
- logs
superseded_by: null
---

# ADR-541: Browse Taxonomy, Visibility Split, and Logs

## Context

The current `/browse` page exposes too many categories in regular mode and mixes together concepts that users experience differently.

Three specific problems are causing friction:

1. **Default mode is too noisy** — builder/operator categories such as agents, workflows, MCP tools, tests, and scripts compete with user-facing surfaces like skills, pages, documents, and notes.
2. **`CLI Commands` is both too narrow and misleading** — the current name suggests the tab represents the CLI ecosystem, but the real browse goal is command discovery. At the same time, the broader CLI/client ecosystem belongs under integrations, not under a command tab.
3. **Log browsing disappeared** — there is no current browse category for operational logs, even though logs remain a useful dev/operator surface.

The user-approved direction is to simplify, not to invent a new metadata model. Browse should keep dynamic discovery, stay close to the current page structure, and make only the taxonomy changes needed to reduce clutter and clarify meaning.

This ADR builds on two recent decisions:
- **ADR-539** established the browse/index category model and the RAG category split.
- **ADR-540** established `/browse` as a primary workbench surface rather than a flat catalog.

## Decision

### 1. Adopt a two-level browse visibility model

Browse categories are split into **regular** and **dev-only** visibility.

**Regular mode categories**:
- `skills`
- `pages`
- `actions`
- `commands`
- `prompts`
- `integrations`
- `documents`
- `vault`

**Dev-only categories**:
- `wiki`
- `agents`
- `workflows`
- `mcp-tools`
- `api-routes`
- `scripts`
- `tests`
- `logs`

Rule: regular mode is for user-facing content, invocation, and connected systems. Dev mode adds AI/operator/implementation surfaces.

### 2. Rename `cli-commands` to `commands`

The existing `cli-commands` browse category is renamed to `commands`.

Semantics:
- `commands` is a browse surface for explicit command entrypoints.
- `commands` is **not** a duplicate of `skills`.
- A skill appears in `commands` only when it exposes one or more real command files.
- The command card unit is **one card per `commands/*.md` file**.

Discovery rule:
- command indexing should use actual command files, not generic `SKILL.md` visibility alone.
- both core Augur commands and skill-contributed commands belong in the same `commands` category.

### 3. Keep `skills`, `actions`, and `prompts` as separate surfaces

The browse taxonomy keeps these distinctions:

- `skills` = one card per `SKILL.md` capability package
- `actions` = runnable dashboard/action-dispatch targets
- `prompts` = prompt templates
- `commands` = explicit command files

These surfaces must not be collapsed into one another. In particular:
- `actions` stays separate from `commands`
- `commands` does not become a general "all runnable things" bucket
- `skills` should not be duplicated into `commands` unless command files exist

### 4. Treat `integrations` as the home for all connected systems

`integrations` remains a broad category covering all systems Augur works with.

Examples include:
- AI clients
- Augur CLI
- notes tools (for example Obsidian)
- platform integrations (for example Apple)
- external services and supporting tools

`integrations` should not be narrowed to AI clients only.

Filtering model:
- integrations are filtered by tags/type metadata such as `ai-client`, `notes`, `calendar`, `email`, `storage`, `system`, or similar.
- Augur CLI is represented as an integration entry, not as a command-category proxy.

### 5. Add a dev-only `logs` category

A new `logs` browse category is added and is visible only in dev mode.

Semantics:
- `logs` is for runtime-resolved Augur logs only
- repo-local logs are treated as bugs and should be fixed at the source, not normalized in browse
- the category is for operational inspection, not for user knowledge browsing

Source rule:
- log discovery must use the canonical runtime/log paths resolved via `src.config.paths`
- do not browse project-root or hidden-folder log accumulation as a product feature

Initial quick actions:
- `Open Folder`
- `Reveal File`
- `Tail Recent`
- `Copy Path`

## Consequences

### Positive

- Regular browse mode becomes materially less noisy.
- The difference between capabilities, commands, actions, prompts, integrations, and operators-only surfaces becomes clearer.
- `integrations` becomes a better home for the actual system ecosystem, including Augur CLI.
- `logs` returns as a focused dev surface without polluting the default browse experience.
- The redesign stays close to the current dynamic browse/index model instead of introducing a new registry system.

### Negative

- Renaming `cli-commands` to `commands` requires coordinated updates across browse UI, transforms, and indexing.
- Existing tests and docs that still encode the old category name will need migration.
- Current command discovery based on `SKILL.md` visibility is no longer sufficient if `commands/*.md` becomes the canonical browse source.

### Neutral

- The underlying browse page and workbench direction from ADR-540 remain intact.
- `integrations` still uses one broad category rather than being split into multiple tabs.
- Dynamic indexing remains the model; this ADR changes category semantics and visibility, not the overall discovery architecture.

## Alternatives Considered

### Alternative 1: Keep all current categories visible in regular mode

Rejected because the user explicitly wants a cleaner default browse experience and the current default is too crowded with builder/operator surfaces.

### Alternative 2: Collapse actions, commands, prompts, and skills into one invocation taxonomy

Rejected because it creates duplication, weakens the meaning of each tab, and makes the page harder to scan. The approved direction is to preserve distinct surfaces with clearer rules.

### Alternative 3: Split integrations into separate top-level tabs for AI clients, notes, and services

Rejected because the existing tag/filter model already supports this without multiplying top-level categories.

## References

- ADR-539: RAG Three-Tier Simplification
- ADR-540: Browse Workbench Redesign
- `apps/dashboard/lib/browse/types.ts`
- `apps/dashboard/app/(views)/browse/page.tsx`
- `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- `apps/dashboard/lib/browse/transforms.ts`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - browse category id `cli-commands` renamed to `commands`
    - browse category id `logs` added as a dev-only category
  patterns_deprecated:
    - treating the command tab as a proxy for the CLI/client ecosystem
    - relying on repo-local logs as a browseable surface
    - deriving browse commands solely from generic SKILL visibility metadata
  files_affected:
    - apps/dashboard/lib/browse/types.ts
    - apps/dashboard/app/(views)/browse/page.tsx
    - apps/dashboard/app/(views)/browse/useBrowseState.ts
    - apps/dashboard/lib/browse/transforms.ts
    - src/mcp/augur_mcp/infrastructure/browse/skills.py
    - tests/packages/augur-mcp/infrastructure/test_browse.py
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-541-browse-taxonomy`

### Phase 1: Taxonomy and visibility
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Rename `cli-commands` to `commands` across browse category definitions, labels, descriptions, and state handling | `apps/dashboard/lib/browse/types.ts`, `apps/dashboard/app/(views)/browse/page.tsx`, `apps/dashboard/app/(views)/browse/useBrowseState.ts`, related browse UI files |
| 1.2 | developer | medium | Apply the agreed regular vs dev-only category split, including moving `wiki` to dev mode and adding `logs` as dev-only | same browse category/state files |

### Phase 2: Source semantics
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Update command discovery so browse `commands` is sourced from real `commands/*.md` files with one card per command file | browse indexing/discovery code, tests |
| 2.2 | developer | medium | Keep `actions`, `prompts`, `skills`, and `integrations` semantics distinct and update transforms/descriptions accordingly | `apps/dashboard/lib/browse/transforms.ts`, browse MCP infrastructure |
| 2.3 | developer | medium | Move Augur CLI representation into `integrations` and ensure integrations remain tag-filterable across AI clients, notes tools, and services | integrations discovery/transform code |

### Phase 3: Logs surface
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Add a dev-only `logs` category sourced only from runtime-resolved log roots via `src.config.paths` | browse infra for logs, dashboard transforms, types |
| 3.2 | developer | low | Add initial quick actions for logs: open folder, reveal file, tail recent, copy path | log browse UI and supporting MCP endpoints/tools |

### Phase 4: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | validator | medium | Update browse tests and category expectations for renamed and moved categories | browse tests, MCP browse tests |
| 4.2 | validator | high | Verify the regular mode is materially less noisy and that dev mode exposes the added operator surfaces without regressions | browse UI + browser verification outputs |

### Completion Criteria
- [ ] `Commands` replaces `CLI Commands` everywhere in browse
- [ ] Regular mode exposes only the agreed user-facing categories
- [ ] Dev mode exposes wiki, operator, and log surfaces
- [ ] `Commands` lists one card per `commands/*.md`
- [ ] `Integrations` includes Augur CLI and remains filterable by tags
- [ ] `Logs` browses only runtime-resolved logs and offers the agreed quick actions
- [ ] Browse tests and browser verification pass
- [ ] ADR status updated to Implemented after completion
