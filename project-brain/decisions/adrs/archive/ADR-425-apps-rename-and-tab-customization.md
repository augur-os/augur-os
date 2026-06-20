---
status: Implemented
date: 2026-03-16
deciders:
  - Gur Sannikov
related:
  - ADR-419
  - ADR-182
hub: core
tags:
  - dashboard
  - sidebar
  - tabs
  - customization
superseded_by: null
---

# ADR-425: Apps Rename and Tab Customization

## Context

Users don't understand the "Hubs" label in the sidebar — "Apps" better communicates that these are customizable applications. Additionally, users have no way to reorder or rename tabs within a hub; tab order is fixed by `augur.yaml` order values set at development time.

## Decision

Two user-facing improvements:

### 1. Sidebar Rename ("Hubs" → "Apps")

Single string replacement in the sidebar section header. Individual hub names unchanged.

### 2. Tab Customization Panel

Inline panel that slides down from the tab bar when the user clicks "Customize":

- **Drag-and-drop reorder** — all tabs shown in a flat sortable list with grip handles
- **Inline rename** — click a tab name to edit it
- **Overview tab pinned** — always first position, not draggable
- **Overflow divider** — visual boundary showing which tabs are visible vs. in "More ▾"
- **Done/Reset buttons** — changes batched and persisted on "Done", discarded on "Reset"

### Persistence

`POST /api/tabs/customize` API route:
1. Receives `hubId` and `changes` array (each with `pageId`, `skillId`, `order`, optional `title`)
2. Writes `order`/`title` to each affected plugin's `augur.yaml` `contributions.pages[]`
3. Regenerates tab registry
4. Returns updated `HubConfig`

Per-tab `skillId` tracking added to generated registry for cross-plugin tab writes. File locking via `flock` prevents concurrent write conflicts.

## Consequences

### Positive

- Users can personalize their tab layout per hub
- "Apps" label is more intuitive than "Hubs"
- Changes persist to source augur.yaml files (decentralized)

### Negative

- API route writes directly to plugin augur.yaml files (no MCP tool exists for this)
- Requires `@dnd-kit/sortable` dependency

### Neutral

- Tab registry remains a generated cache, not source of truth

## References

- Design doc: `docs/superpowers/specs/2026-03-16-apps-rename-and-tab-customization-design.md`
- ADR-419: Hub Tab Navigation Redesign
