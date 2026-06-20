---
status: Implemented
date: 2026-06-05
deciders:
  - gsannikov
related:
  - ADR-770
  - ADR-771
  - ADR-781
  - ADR-794
  - ADR-797
hub: brain
tags:
  - browse
  - folder-context
  - multi-project
  - project-brain
  - onboarding
superseded_by: null
spec_file: 2026-06-04-browse-folder-context-switcher-design.md
plan_file: 2026-06-04-browse-folder-context-switcher.md
---

# ADR-798: Browse Folder Context Is The Primary Multi-Project Switcher

## Decision summary

Browse owns the user's active folder context for first-hour and multi-project use: a compact dropdown near the existing index/manage controls switches `All folders`, `Personal`, and named project folders, while the existing Browse category buttons remain unchanged.

## Spec and plan

- [`docs/superpowers/specs/2026-06-04-browse-folder-context-switcher-design.md`](../superpowers/specs/2026-06-04-browse-folder-context-switcher-design.md)
- [`docs/superpowers/plans/2026-06-04-browse-folder-context-switcher.md`](../superpowers/plans/2026-06-04-browse-folder-context-switcher.md)

## Context

Fast launch initializes one folder and Browse shows the resulting inventory. Real use quickly becomes multi-folder: a user can have a personal brain and one or more project folders, including the Augur project itself.

The user-facing problem is not only filtering. If Browse displays one folder while chat drafts or future actions target another, the product becomes unsafe and confusing. Folder context must therefore scope both the visible Browse cards and the action context.

The existing Browse navigation is already dense enough. The launch UI should not add another nav row or replace category buttons such as Notes, Documents, Pages, Skills, Actions, and Workflows.

## Decision

1. Browse gets one compact folder context dropdown in the top-right header control group, near `Indexed ... ago` and `Manage`.
2. The dropdown supports `All folders`, `Personal`, registered project folders, detected unregistered project folders, stale registered folders, and `+ Add folder`.
3. The existing Browse category buttons remain the content-type navigation. Folder context is orthogonal:
   - `All folders + Notes` shows notes across registered contexts.
   - `Personal + Notes` shows personal items.
   - `<Project> + Skills` shows project-scoped skill and inventory records.
4. Active context is stored in Augur runtime state. Dashboard local storage may cache the last selection but is not the source of truth.
5. Browse filtering and chat/action handoff read the same active context object.
6. `+ Add folder` is scan-first. It can preview discovered artifacts and problems without creating `project-brain/` or writing client projection files.
7. Stale, missing, repairable, and unregistered folder states are rendered as folder-context states, not as a separate project manager page.

## Non-Goals

- No second Browse nav row.
- No full Browse redesign.
- No separate project manager page for V1 launch.
- No automatic folder init from a scan-only preview.
- No adoption, projection, rewrite, cleanup, merge, or delete of existing AI-client files.
- No dashboard-side local execution or hidden LLM/API call.

## Implementation status

Implemented on `main` through the Browse folder-context feature series:

- `src/lib/brain_active_context.py` stores and validates the runtime active context.
- `brain-active-context`, `brain-set-active-context`, and `brain-folder-scan` MCP tools expose context and scan-first preview.
- `apps/dashboard/lib/browse/folderContext.ts` maps registry/discovery data to dropdown options and item filtering.
- `apps/dashboard/app/(views)/browse/BrowseFolderContextMenu.tsx` renders the compact header control.
- `apps/dashboard/app/(views)/browse/useBrowseState.ts` wires context, filtering, and add-folder scan.
- Browse item actions and problem prompts include active folder context.

The feature merged through `d37e9d6fe Merge browse folder context feature`; later UI polish landed in `d0ca6194c`.

## Consequences

Positive:

- Users can understand personal versus project scope without leaving Browse.
- The launch story stays simple: install, choose folder, inspect in Browse, switch folder context.
- Action/chat handoff no longer has to infer project context from the selected card alone.

Tradeoffs:

- Browse owns more state and must keep runtime context, dashboard cache, and item filtering aligned.
- The dropdown must remain compact enough not to crowd the current header.
- Server-side filtering may be needed later for very large inventories.

## Verification

Required proof:

- Real Browse data can be filtered between `All folders`, `Personal`, and the Augur project folder.
- The selected folder context appears in generated chat/action drafts.
- `brain-folder-scan` previews a folder without writing `project-brain/`.
- The folder dropdown appears beside existing index/manage controls and does not add a second navigation row.
- Registered stale project paths collapse into a repairable state rather than duplicating indistinguishable entries.

Current code evidence:

- `tests/unit/test_brain_active_context.py`
- `tests/unit/test_brain_discovery_mcp_wrappers.py`
- `tests/dashboard/lib/browse-folder-context.test.ts`
- `tests/dashboard/browse/BrowseFolderContextMenu.test.tsx`
- `tests/dashboard/browse/useBrowseState.test.tsx`

## Status notes

Implemented on 2026-06-05 as the primary multi-project Browse switcher for fast launch.

## Related

- ADR-797: Fast launch is inventory-only folder init.
- ADR-794: Standard brain workspace files.
- ADR-781: Harness layering and capability merge across global/user/project brains.
- ADR-770: Project-brain physical migration.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "brain-active-context MCP tool added"
    - "brain-set-active-context MCP tool added"
    - "brain-folder-scan MCP tool added"
  patterns_deprecated:
    - "treating Browse category navigation as the only scope selector"
    - "dashboard-local active folder state as source of truth"
  files_affected:
    - "src/lib/brain_active_context.py"
    - "src/mcp/augur_core/tools/core/brain_discovery.py"
    - "src/mcp/augur_core/tools/core/__init__.py"
    - "apps/dashboard/lib/browse/folderContext.ts"
    - "apps/dashboard/app/(views)/browse/BrowseFolderContextMenu.tsx"
    - "apps/dashboard/app/(views)/browse/BrowsePageClient.tsx"
    - "apps/dashboard/app/(views)/browse/useBrowseState.ts"
```
