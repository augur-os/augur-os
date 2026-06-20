# Page Cleanup & Grouped Navigation Design

**Date**: 2026-03-22
**Status**: Draft
**Scope**: Tab registry navigation redesign + hidden template cleanup

## ADR References

- **ADR-128**: Contribution-Based Hub Assembly — defines how plugins contribute pages to hubs
- **ADR-218**: Filesystem-Based Tab Discovery — auto-discovers page.tsx files for registry
- **ADR-177**: Infrastructure Reliability Refactor — build-time tab-to-page validation gate
- **ADR-136**: Nested Skills — implements `nav_mode: nested` with `children` arrays; reusable pattern for tab grouping

## Problem

The dashboard has ~140 page.tsx files and 188 tab registry entries. The tab bar across 6 hubs shows 42 primary tabs + 6 overflow. The core issue: **skill sub-pages are flattened into the hub tab bar as top-level tabs**, making the nav feel cluttered and hard to scan.

### Current state per hub

| Hub | Primary tabs | Overflow | AutoPages | Blocks | Issue |
|-----|-------------|----------|-----------|--------|-------|
| Adaptive | 3 | 0 | 1 | 0 | Clean |
| Brain | 6 | 0 | 4 | 13 | Clean |
| Career | 9 | 0 | 2 | 34 | Quiz/Demo are sub-pages shown as top-level |
| Command | 9 | 5 | 2 | 18 | Daemon sub-pages (Health, Jobs, Loops, Notifications, Services) flattened as top-level tabs |
| Life | 9 | 1 | 4 | 51 | Voice Memos, Scenes, Lighting are sub-pages of Apple/Home-Automation shown top-level |
| Studio | 6 | 0 | 1 | 10 | Clean |

The 12 SkillAutoPage scaffold pages are already correctly classified as `autoPages` (not in the tab bar). **No page deletions needed** — the problem is purely navigational.

### What the user sees vs what they expect

**Command hub currently:**
```
[Overview] [Custom Plugins] [Daemon] [Health] [Jobs] [Loops] [Notifications] [Services] [Logs]  [More: Self Heal, Sessions, System Cleanup, Updater, Workflows]
```

Health, Jobs, Loops, Notifications, Services are all **daemon sub-pages** — they should be grouped under Daemon, not siblings of it.

**Life hub currently:**
```
[Overview] [Voice Memos] [Scenes] [Lighting] [Attention] [Eisenhower] [File Manager] [Finance] [Health]  [More: Home Automation]
```

Voice Memos belongs under Apple. Scenes and Lighting belong under Home Automation. Home Automation itself is demoted to overflow while its children are primary tabs.

## Design

### Phase 1: Grouped Navigation

**Goal**: Skill sub-pages cluster under their parent skill in the tab bar as dropdown groups.

#### Grouping logic

The tab generator already tracks `skillId` on every tab entry. The grouping rule:

1. Collect all tabs by `skillId`
2. Skills with **1 tab**: render as a flat tab (current behavior)
3. Skills with **2+ tabs**: render as a **dropdown group** — the skill name is the parent label, sub-pages are dropdown items
4. The **Overview** tab (no skillId) always remains flat

#### Expected result per hub

**Command hub after grouping:**
```
[Overview] [Custom Plugins] [Daemon v] [Logs] [More: Self Heal, Sessions, System Cleanup, Updater, Workflows]
                                 |
                            [Daemon]
                            [Health]
                            [Jobs]
                            [Loops]
                            [Notifications]
                            [Services]
```
9 tabs -> 4 primary + overflow. Daemon's 6 entries collapse into 1 group.

**Life hub after grouping:**
```
[Overview] [Apple v] [Home Automation v] [Attention] [Eisenhower] [File Manager] [Finance] [Health]
               |              |
          [Voice Memos]  [Scenes]
                         [Lighting]
                         [Home Automation]
```
10 tabs -> 8 primary (no overflow). Apple and Home Automation sub-pages collapse into 2 groups.

**Career hub after grouping:**
```
[Overview] [GTM] [Interview] [Learning v] [Pipeline] [Resume] [Venture Augur v]
                                  |                              |
                             [Learning]                    [Venture Augur]
                             [Quiz]                        [Demo]
```
9 tabs -> 7 primary. Learning+Quiz and Venture Augur+Demo collapse.

| Hub | Current | After grouping | Reduction |
|-----|---------|----------------|-----------|
| Adaptive | 3 | 3 | 0 |
| Brain | 6 | 6 | 0 |
| Career | 9 | 7 | 2 |
| Command | 9 + 5 overflow | 4 + 5 overflow | 5 |
| Life | 9 + 1 overflow | 8 | 2 + eliminates overflow |
| Studio | 6 | 6 | 0 |
| **Total** | 42 + 6 | 34 + 5 | 9 fewer visible tabs |

#### Implementation

**1. Tab generator changes** (`scripts/generate-tab-registry.ts`):

After building `customTabs` array (line 282), add a grouping pass:

```typescript
// Group tabs by skillId — skills with 2+ tabs become dropdown groups
const grouped = groupBySkillId(customTabs);
// grouped: Array<TabItem | GroupedTab>
```

The grouping function:
- Tabs with no `skillId` or unique `skillId`: pass through as flat tabs
- Tabs sharing a `skillId`: merge into a `GroupedTab` where:
  - `id`: the skillId
  - `label`: derived from skill display name (SKILL.md title or `smartLabel(skillId)`)
  - `href`: the first child's href (for parent navigation on click)
  - `children`: the original tab entries
  - `icon`: inherit from the first child or use a default

**2. New type** (`lib/tabs/types.ts`):

```typescript
export interface GroupedTab extends TabItem {
  /** Sub-pages within this skill group */
  children: TabItem[];
}

export type TabEntry = TabItem | GroupedTab;

export function isGroupedTab(tab: TabEntry): tab is GroupedTab {
  return 'children' in tab && Array.isArray(tab.children);
}
```

**3. HubTabBar changes** (`components/HubTabBar.tsx`):

This is a **breaking change** to the component's rendering logic (not just styling).

- Accept `tabs: TabEntry[]` instead of `tabs: TabItem[]`
- For flat `TabItem`: render as current (link tab)
- For `GroupedTab`: render as a dropdown button (reuse the existing `MoreDropdown` pattern)
  - Click on label text: navigate to `href` (first child route)
  - Click on chevron: open dropdown showing children
  - Active state: highlight when `pathname` starts with any child's `href`
  - Keyboard: arrow keys navigate dropdown, Escape closes

**4. Responsive overflow**: Operates on the grouped array — fewer top-level items means fewer items overflow. The `MoreDropdown` stays for remaining overflow; grouped dropdowns are separate.

### Phase 2: Hidden Templates — Dev Mode Only

The `hidden` hub contains business templates (consulting, SMB client, terminal automation) — 6 pages accessible only by direct URL today. Instead of deleting, expose them in dev mode:

- Add the hidden hub to the sidebar navigation with `devOnly: true`
- When dashboard mode is "development", the hub appears in the sidebar
- In production mode, it remains hidden (current behavior)

Implementation: add a `devOnly` flag to the hidden hub's assembly config or nav item entry, and filter on `useModeStore` in the sidebar renderer (same pattern already used for dev-only tabs).

### Phase 3: Block Registry Cleanup (deferred)

The 126 block entries are skill UI components shown in the "Blocks" dropdown. Separate concern — needs its own design discussion.

## Non-Goals

- Deleting any pages — scaffolds are already in `autoPages`, hidden templates become dev-mode visible
- Changing page content or data wiring
- Redesigning the block system or auto-page discovery
- Collapsing thin wrapper pages into parents (separate refactor)

## Verification

After implementation:

1. `npm run generate-tabs` — confirm ADR-177 validation passes
2. `npm run build` — no broken imports
3. Manual: each hub tab bar shows grouped dropdowns for multi-page skills
4. Manual: clicking group label navigates to first child; clicking chevron opens dropdown
5. Manual: active state highlights group when any child route is active
6. Manual: overflow "More" button still works for remaining tabs

## Migration

1. Phase 1 is a breaking change to `HubTabBar` component API and generated registry format
2. Phase 2 (hidden templates) is additive — no deletions, just adding dev-mode visibility

## Success Criteria

- Tab bar shows grouped skill navigation — Command hub drops from 9 to 4 primary tabs
- No overflow on Life hub (currently 1 overflow item)
- All pages remain accessible (grouped sub-pages in dropdowns, scaffolds in autoPages)
- Hidden templates accessible in dev mode via sidebar
