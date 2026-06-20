---
status: Implemented
date: 2026-05-18
deciders:
  - gsannikov
related:
  - ADR-760
hub: dev
tags:
  - browse
  - dashboard
  - ui
  - navigation
  - taxonomy
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-764: Browse Category Tier Model — Labeled Journey Clusters + Grouped "More" Popover

## Decision summary

`BrowseCategory` gains a required `tier: "primary" | "more"` field; the Browse page renders the primary tier as **journey-group clusters with the group label above each pill cluster** (laid out so the label + pills wrap as a unit, never apart), and collapses the rest into a single **grouped "More N ▾"** popover that auto-hides when empty.

## Context

Before this change, `apps/dashboard/app/(views)/browse/page.tsx` rendered all 23 visible categories through `OverflowBar`, which inlined the nine `journey_group` labels (`INCOMING`, `KNOWLEDGE`, `REUSE`, `SYSTEM`, `STATE`, `INTENT`, `WIRING`, `ORCHESTRATION`, `DIAGNOSTICS`) at smaller weight than the pills they were supposed to group. Three problems followed:

1. **Broken hierarchy** — section labels were visually lighter than items, so they read as noise rather than structure.
2. **No tiering** — daily-driver content (Notes, Wiki, Skills) sat at the same visual weight as rare diagnostics (Tests, Logs, System Metadata); 23 pills wrapped to 3 visible rows.
3. **Weak active selection** — the active pill had to compete with 22 identical pills for visual attention.

The dashboard taxonomy is real (`journey_group` carries lifecycle meaning and is asserted in `tests/dashboard/browse-category-journey.test.ts`), so the fix must keep the taxonomy intact while improving the surface.

## Decision

1. **Tier field.** Add `tier: "primary" | "more"` to `BrowseCategory` in `apps/dashboard/lib/browse/types.ts` as a **required** field. Export `partitionBrowseCategoriesByTier(categories)` as the canonical splitter. The split lives in canonical data, not in render code — changing the split is a single-field edit in `types.ts`.

2. **Default tier policy.** The primary tier holds the six daily-driver content categories — Notes, Documents, Wiki, Pages, Skills, Actions — chosen so the primary pill row plus the "More ▾" button fit on a single pill row at typical desktop widths (≈1200–1500 px content area). All other categories default to `more`. The policy is editable per-category; the only invariant is that every `devOnly` category must be in `more` (dev-only items must never appear in the always-visible primary row), which is asserted by the journey test.

3. **Desktop nav component.** Replace the desktop `OverflowBar` usage in Browse with a new `BrowseCategoryNav` (`apps/dashboard/components/shared/BrowseCategoryNav.tsx`) that renders:
   - Primary categories as **labeled journey clusters**: each cluster is a flex column with the uppercase `journey_group` label on top (10 px, semibold, tracking-wider, muted) and the pills row below. Clusters are arranged horizontally with flex-wrap on the cluster *as a unit*, guaranteeing the previous broken-hierarchy issue (labels orphaned from items at wrap) can't recur.
   - If the active category is in the `more` tier, an inline highlighted pill for it on the right after a vertical separator — so selection stays visible without opening the popover.
   - A right-aligned "More N ▾" button. The popover groups items by `journey_group` (uppercase labels as **proper section headers**, visually subordinate to items), arranged in a 2-column grid. When the popover contains both content-only and all-`devOnly` journey groups (i.e. dev mode is on), a Content / Dev super-divider separates the two clusters.
   - The "More ▾" button auto-hides entirely when `more.length === 0` for the current `visibleCategories` (e.g. non-dev mode with all non-dev categories promoted to primary).
   - **Keyboard support**: arrow/Home/End traverse menu items, Escape closes and returns focus, opening the popover auto-focuses the active item (or first item).

4. **Mobile.** The mobile `<select>` is unchanged.

## Alternatives considered

- **Persistent left rail with collapsible journey groups.** Better for power-user taxonomy but requires reflowing the Browse page layout and removes the consistent top-bar pattern other dashboard pages use.
- **Command-palette-first (⌘K) with pinned recents.** Most scalable but hides the taxonomy from new users and adds a hidden affordance for what should be the most discoverable navigation on the page.
- **Polish only (bold group labels, dividers, stronger active state) on the old `OverflowBar`.** Fixes the hierarchy violation but leaves the density problem unresolved.
- **All non-dev categories promoted to primary (no More popover in non-dev mode).** Tried during iteration; at typical desktop widths the 12 pills plus group labels plus the dev-mode "More" button wrapped to a second pill row, defeating the goal. Reverted to the 6-item primary policy above.

The chosen design preserves the existing data model and journey-group taxonomy, scales to additional `more`-tier categories without re-wrapping, keeps the visual weight where users spend time, and fits on one pill row at the widths the dashboard targets.

## Consequences

- `BrowseCategory.tier` is required, so any new category added to `BROWSE_CATEGORIES` must choose a tier. The journey-test suite asserts every category has a valid tier and that no `devOnly` category is in `primary`.
- The popover render scales: a category becomes "more" by flipping one field, with no UI work required.
- Rule 32 (Browse signals ride existing file cards) is unaffected — this change is purely about the navigation surface, not about how items render inside a category.
- `OverflowBar` remains available for other consumers; only the Browse desktop nav switched off it.
- At very narrow widths (≈<900 px content area), the cluster row will wrap to multiple rows of label+pills clusters — still readable because labels stay attached to their pills. Mobile uses `<select>` so this only affects intermediate widths.

## Related

- [ADR-760](./ADR-760-browse-page-ux-cleanup.md) — Browse Page UX Cleanup (prior pass on the same surface)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "BrowseCategory: added required field `tier: \"primary\" | \"more\"`"
    - "types.ts: added export `partitionBrowseCategoriesByTier`"
  patterns_deprecated:
    - "Inline journey-group labels rendered at smaller weight than the pills they group (OverflowBar usage in Browse desktop nav)"
  files_affected:
    - apps/dashboard/lib/browse/types.ts
    - apps/dashboard/components/shared/BrowseCategoryNav.tsx
    - apps/dashboard/app/(views)/browse/page.tsx
    - tests/dashboard/browse-category-journey.test.ts
```
