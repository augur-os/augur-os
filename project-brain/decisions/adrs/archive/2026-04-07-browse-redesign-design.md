# Browse Redesign

**Date:** 2026-04-07
**Status:** Approved
**Scope:** Redesign `/browse` into a power-user-biased workspace for exploration, orientation, metadata review, and action launch.

## Problem

The current `/browse` page works, but it behaves more like a long index than a tool.

The main issues are:

- Weak hierarchy. Header, category tabs, freshness, filters, and result cards all compete at roughly the same visual weight.
- Discovery friction. Search is present, but the page still relies on a flat filter row and a broad card wall to do most of the work.
- Repetitive scanning. Cards carry similar structure and repeated actions, so users spend effort re-parsing rather than narrowing quickly.
- Split intent. The page wants to support browsing, understanding, inspecting metadata, and launching actions, but the layout does not clearly assign those jobs to stable regions.
- Underpowered detail flow. The detail panel exists, but it feels secondary rather than being the center of inspect-and-act workflows.

For returning users, the page feels serviceable but slow. For new users, it exposes capability breadth but not enough structure.

## Goals

### Primary

- Make `/browse` feel like a workspace rather than a static index.
- Bias the page toward repeat, power-user usage without becoming cryptic.
- Strengthen the search-and-select loop so users can narrow faster and lose less context.
- Promote metadata and actions into first-class parts of the experience rather than secondary labels on cards.

### Secondary

- Preserve category breadth across skills, pages, documents, actions, prompts, and related browse surfaces.
- Improve orientation for users who are still learning system structure.
- Reduce visual noise and repeated UI controls.

### Non-goals

- Redesign the global dashboard shell or sidebar navigation outside `/browse`.
- Change the underlying browse indexing model in this phase.
- Replace all category layouts with one universal presentation if a category-specific table or grouped list is materially better.

## Approaches Considered

### 1. Structured Catalog

Improve hierarchy and editorial structure while keeping the current page shape broadly intact.

**Pros:** Lower implementation risk, easier transition from current layout.

**Cons:** Still leaves `/browse` feeling like a prettier catalog rather than a high-utility tool.

### 2. Command Center

Push the page toward a search-heavy operational surface with summary strips, stronger controls, and quick actions.

**Pros:** Strong search posture, better power-user speed.

**Cons:** Risks becoming a control dashboard before the core browse flow is improved.

### 3. Split Workbench

Reframe the page as a three-zone workspace with persistent navigation, search-led results, and a dedicated detail/actions panel.

**Pros:** Best fit for power-user workflows, strongest inspect-and-act model, most coherent use of the existing detail panel concept.

**Cons:** Largest structural redesign, needs deliberate responsive fallback.

## Recommended Direction

Use **Split Workbench** as the base layout, with the **search-first discipline of Command Center**.

This keeps the page tool-like and operational while preserving browse breadth. The result should feel closer to a technical control surface than an admin gallery.

## Design

### Layout

`/browse` becomes a three-zone desktop workspace:

```
Left Rail | Center Results Workspace | Right Detail / Actions Panel
```

### Left Rail

The left rail owns persistent navigation and narrowing controls.

Contents:

- Browse scopes and categories
- Saved views / power-user presets
- Recent contexts
- Pinned high-value filters
- Optional fast counts by scope

This replaces the current pattern where categories and filters are separated into multiple shallow rows. The left rail should make the active browsing context visible at all times.

### Center Workspace

The center column is the main working surface.

Order:

1. Primary search bar
2. Quick toggles and scopes
3. Summary strip
4. Results header with view and sort controls
5. Result list or category-specific result presentation

This region should optimize for fast narrowing and scanning. It should feel denser and more purposeful than the current card wall.

### Right Panel

The right panel becomes the primary inspect-and-act surface for the selected item.

Contents:

- Item summary
- Core metadata: hub, source, quality/freshness, type
- Related items
- Primary actions: open, run, reveal, inspect
- Category-specific actions where applicable

Selection should update this panel immediately without feeling like a route transition.

## Interaction Model

### Search

Search becomes the page’s dominant control rather than one control among many.

Requirements:

- Prominent placement at the top of the center workspace
- Scope-aware operation across categories
- Semantic toggle remains available but should read as an enhancement, not a separate mode competing for attention
- Future-friendly structure for autocomplete or suggested queries

### Filters

Filters split into two tiers:

- **Pinned filters:** always visible in the left rail for high-value dimensions such as category, hub, source, and quality
- **Secondary filters:** collapsible or panel-based controls for lower-frequency dimensions

This reduces the current visual sprawl of the horizontal filter row.

### Results

The default result presentation for browse-heavy categories should be **denser and more list-oriented**.

Guidelines:

- Cards remain valid where richer visual grouping matters
- List-style rows should be preferred where users mainly scan names, types, tags, and actions
- Repeated per-card action clutter should be reduced
- The selected result should be visually obvious and stable

### Detail and Action Flow

The right panel should absorb most repeated item controls currently rendered in the result grid.

Expected flow:

1. User narrows via search or pinned filters
2. User selects a result from the center column
3. Right panel updates with context, metadata, and actions
4. User opens, runs, or reveals without losing search context

This should make `/browse` feel more like a workspace for decision and execution than a static list.

## Visual Direction

The page should move toward a **technical command surface** aesthetic.

Characteristics:

- Stronger zone separation between navigation, results, and detail
- Sharper hierarchy and better use of contrast
- Denser information presentation in the center column
- Calmer, structured presentation in side panels
- Reduced “flat admin” feel

This is a structural redesign, not a decorative reskin. Visual changes should clarify function first.

## States And Error Handling

### Loading

- Loading should respect the three-zone layout instead of collapsing into generic page skeletons
- The center workspace should preserve layout shape while data loads
- The right panel should support a stable loading state when selection changes

### Empty States

No-result states must not end in dead space.

They should provide:

- Query suggestions
- Nearby scopes or categories
- Ways to relax filters
- Context about whether the issue is search, filtering, or indexing

### Not Indexed

The current “not indexed” behavior remains necessary, but it should visually belong to the workspace model rather than acting like a detached message block.

### Errors

- Errors should be scoped to the region that failed
- Search errors, index errors, and detail-load errors should not collapse the entire page if other regions remain usable
- Freshness should never rely on color alone; text and icons must reinforce state

## Responsive Behavior

Desktop is the primary target, but mobile must remain usable.

### Desktop

- Full three-zone layout
- Persistent left rail
- Persistent right detail/actions panel

### Tablet

- Left rail may compress to icons or a narrower navigation stack
- Right panel may become toggleable rather than always visible

### Mobile

Use a stacked model:

1. Search
2. Scope and filter controls
3. Summary strip
4. Result list
5. Detail as bottom sheet or dedicated overlay

Mobile should preserve the same search-select-inspect-act workflow, but in a single-column rhythm.

## Accessibility

The redesign must remain keyboard-first and screen-reader-legible.

Requirements:

- Strong, visible focus states
- No metadata communicated by color alone
- Stable keyboard traversal between left rail, results, and detail panel
- Clear aria labels for workspace regions and toggles
- Respect `prefers-reduced-motion`

## Affected Areas

Primary source files:

- `apps/dashboard/app/(views)/browse/page.tsx`
- `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`

Likely secondary shared surfaces:

- Browse card/list/table presentation components
- Browse detail panel
- Browse empty and error states

## Scope

### In scope

- Layout restructure for `/browse`
- Search-first center workspace
- Left rail for persistent category and filter controls
- Stronger right panel for detail and actions
- Result density improvements
- Updated loading, empty, and error states
- Responsive fallback for tablet and mobile

### Out of scope

- Reworking the global app shell outside `/browse`
- Changing MCP tool contracts unless a concrete browse issue requires it
- Full browse information architecture rewrite across the entire product beyond this page

## Testing

- Component-level verification for layout states and responsive behavior
- Keyboard and focus-path validation across the three-zone layout
- Browser verification on `/browse` with real data
- Validate no-result, not-indexed, and error states
- Validate detail selection flow and action triggers without losing search context
- Validate mobile fallback behavior in browser dev tools or responsive Playwright coverage

## Implementation Notes

- The redesign should preserve the existing data model where possible and first improve layout and interaction boundaries.
- Category-specific result layouts can remain where they materially outperform a generic list.
- The detail panel should become more central, not more optional.
- The redesign should ship as a real UX upgrade for users, not just a visual reshuffle.
