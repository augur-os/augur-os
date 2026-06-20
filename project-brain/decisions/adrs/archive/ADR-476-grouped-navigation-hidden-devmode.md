---
status: Implemented
date: 2026-03-22
deciders:
  - Gur Sannikov
related: []
hub: null
tags:
  - navigation
  - tabs
  - grouped-dropdown
  - hidden-hub
  - dev-mode
superseded_by: null
---

# ADR-476: Grouped Navigation and Hidden Dev-Mode

## Context

The dashboard has ~140 page.tsx files and 188 tab registry entries, with 42 primary tabs + 6 overflow across 6 hubs. The core problem: skill sub-pages are flattened into the hub tab bar as top-level tabs, making navigation cluttered. For example, the Command hub shows Health, Jobs, Loops, Notifications, and Services as top-level tabs when they are all daemon sub-pages. The Life hub has Home Automation demoted to overflow while its children (Scenes, Lighting) appear as primary tabs.

Separately, the hidden hub containing business templates (consulting, SMB client, terminal automation) is only accessible by direct URL with no discoverability path.

## Decision

### Phase 1: Grouped Navigation

Collapse multi-page skills into dropdown groups in the tab bar:

1. Add `GroupedTab` type extending `TabItem` with a `children: TabItem[]` array, and `TabEntry = TabItem | GroupedTab` union type
2. Add `groupBySkillId()` function in `tab-grouping.ts` that merges tabs sharing a `skillId` into dropdown groups (skills with 1 tab remain flat)
3. Update `generate-tab-registry.ts` with a grouping pass after building customTabs
4. Create `GroupDropdown.tsx` component reusing the existing `MoreDropdown` pattern
5. Update `HubTabBar` and `UnifiedHubTabs` to render grouped tabs as dropdown buttons

Result: Command hub drops from 9 to 4 primary tabs; Life hub eliminates its overflow; Career hub drops from 9 to 7 tabs. Total reduction: 42 -> 34 visible tabs.

### Phase 2: Hidden Templates in Dev Mode

Add the hidden hub to sidebar navigation with `devOnly: true` flag, visible only when dashboard mode is "development". Uses the existing `useModeStore` pattern for dev-only UI elements.

## Consequences

### Positive
- Command hub drops from 14 tab entries (9 primary + 5 overflow) to 9 (4 primary + 5 overflow)
- Life hub eliminates overflow entirely
- Hidden templates become discoverable in dev mode without cluttering production UI
- No pages deleted -- all content remains accessible

### Negative
- Breaking change to `HubTabBar` component API and generated registry format
- Dropdown groups add interaction complexity (click label to navigate vs click chevron to expand)

### Neutral
- Block registry cleanup (126 entries) deferred to a separate design discussion
- Scaffold/auto-pages are already correctly classified and unaffected

## Alternatives Considered

### Alternative 1: Delete sub-pages and merge content into parent pages
Rejected because the sub-pages contain distinct functionality and deleting them loses content. Grouping preserves all pages while reducing visual clutter.

### Alternative 2: Sidebar tree navigation instead of tab bar groups
Rejected because it would require a fundamental navigation redesign. Tab bar dropdown groups are a minimal, focused change.

## References
- Spec: `docs/superpowers/specs/2026-03-22-page-cleanup-grouped-nav-design.md`
- Plan: `docs/superpowers/plans/2026-03-22-grouped-nav-hidden-devmode.md`
