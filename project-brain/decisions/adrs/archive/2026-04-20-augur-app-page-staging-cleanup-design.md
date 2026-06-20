# Augur App Page Staging Cleanup

**Date:** 2026-04-20
**Status:** Approved for implementation planning
**Scope:** Clean up current dashboard app surfaces by staging or deleting leftover
pages while preserving required backend skills.

## Problem

The current dashboard app surface exposes several routes that do not represent a
clear current-stage user product:

- `/dev` is mostly an operator shell with generated or automatic pages.
- `/life` is effectively File Manager only, so it reads as an unfinished app.
- `/brain/knowledge/memory` contains a useful Memory experience, but its
  Workspace, Profile, and Daily Logs sections are nested under a second tab row.

The desired UX is a clean current-stage app surface. Pages that belong to later
product stages should move into the existing `staging/{release}/pages/` payloads
or be deleted when they are superseded. Backend skills should not be moved just
because one of their pages is staged if current MVP runtime still depends on
their MCP tools, commands, generated client surfaces, or data contracts.

## Existing Context

The repo already has a release staging model:

- root `skills/` contains current live skills
- `staging/r1/skills`, `staging/r2/skills`, `staging/r3/skills`,
  `staging/r4/skills`, and `staging/later/skills` contain deferred skill copies
- `staging/{release}/pages/` contains deferred custom dashboard page source
- `docs/generated/skill-release-matrix.json` records skill release placement
- `/stage-release` and `/port-release` define staged release payload rules

The cleanup should reuse that model instead of inventing another page archive.

## Design Rule

Use dependency-aware page staging.

Page surfaces and skill backends are separate decisions:

- **Keep active** when the route is part of the current user-facing product.
- **Move page only** when the UI is not current-stage, but the owning backend
  skill is still needed by active runtime paths.
- **Move skill and page together** only when neither the UI nor backend is
  required in the current stage.
- **Delete or supersede** generated/generic pages when a clearer custom page or
  flattened route replaces them.

Implementation must determine backend dependency before moving any skill folder.
Dependency signals include MCP tool use, command exposure, generated client
wrappers, dashboard hooks, action definitions, tests, and release matrix
dependency closure.

## Brain Design

Brain should become the current user-facing second-brain app.

Memory subsections should become independent Brain-level pages instead of tabs
inside the Memory page:

| Current route | Target disposition |
|---|---|
| `/brain/knowledge/memory` | Keep active as `/brain/memory` |
| `/brain/knowledge/memory/daily-logs` | Keep active as `/brain/daily-logs` |
| `/brain/knowledge/memory/profile` | Keep active as `/brain/profile` |
| `/brain/knowledge/memory/workspace` | Keep active as `/brain/workspace` |
| memory search widget / knowledge search | Keep active as `/brain/search` |
| `/brain/ingest` | Keep active as the source-capture path for the current Brain app |
| `/brain/harness` | Move/stage as operator/admin surface, default `r3` |
| `/brain/ai/agents` | Move/stage as operator/admin surface, default `r3` |
| `/brain/rag` | Stage if it remains a technical status page rather than user search UX |
| `/brain/knowledge` YAML | Delete/supersede with explicit Memory/Search pages |
| `/brain/ai` YAML | Delete/supersede with staged Agents/operator page |

The active Brain tab row should contain direct pages such as Memory, Search,
Daily Logs, Profile, Workspace, and Ingest. The implementation should remove
`MemorySectionNav` from the active Memory pages after flattening.

## Dev Design

Dev should not appear as a mostly internal app shell in the primary app
navigation.

| Current route/page | Target disposition |
|---|---|
| `/dev` shell overview | Delete/supersede |
| `/dev/platform-admin` generated overview | Delete/supersede |
| `/dev/auto-vault-hygiene` YAML | Delete/supersede; keep the loop backend under `loop-repo` |
| `/dev/auto-skill-quality` YAML | Delete/supersede |
| `/dev/skill-scores` custom page | Stage to `r3` by default |

Backend skills such as `platform-admin`, `auto-skill-quality`, and `loop-repo`
stay in root `skills/` by default because their tools and commands are part of
current development/runtime workflows. Move one only if implementation verifies
that no active route, command, MCP tool, generated client surface, or test
depends on it.

## Life Design

Life should not appear as a current app while it is effectively File Manager
only.

| Current route/page | Target disposition |
|---|---|
| `/life` shell overview | Move/stage with Life page surface |
| `/life/file-manager` | Move/stage to `staging/r1/pages/life/file-manager` |
| `/life/file-manager/organize` | Move/stage with File Manager page surface |

The `file-manager` backend skill stays in root `skills/` by default because
current context, collateral, `/save`, or file-routing workflows may depend on
its MCP tools. Move the skill itself only if implementation verifies that those
dependencies are absent.

## Generator And Registry Behavior

The implementation should update source-of-truth inputs, not generated outputs.

Allowed source changes include:

- `SKILL.md` frontmatter page declarations and `x-augur-config.contributions`
- `skills/{skill}/augur/pages/*.yaml`
- `apps/dashboard/features/pages/{hub}/...` custom page sources
- `staging/{release}/pages/...`
- `staging/{release}/manifest.md`

Generated files such as tab registries and config wrappers should be regenerated
after source changes. They should not be hand-edited as the durable fix.

## Validation

Implementation planning should include checks for:

- generated tab registry no longer exposes deleted or staged pages
- Brain active pages are direct top-level tabs, not nested `MemorySectionNav`
- staged page files appear under the correct `staging/{release}/pages/` path
- root skills are moved only after dependency checks prove they are not needed
- release matrix and staged manifests remain valid
- dashboard build/mount validation passes
- browser verification confirms `/brain` shows real flattened Memory pages and
  `/dev` and `/life` no longer appear as leftover primary app surfaces

## Non-Goals

- Redesigning the whole dashboard navigation system.
- Reclassifying every staged skill.
- Removing backend MCP tools solely to clean the UI.
- Adding compatibility route shims for every old URL.
- Solving final release enablement for all `r1`/`r2`/`r3` skills.
