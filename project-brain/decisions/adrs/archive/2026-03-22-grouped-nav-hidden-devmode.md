# Grouped Navigation & Hidden Dev-Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse multi-page skills into dropdown groups in the hub tab bar, and expose the hidden templates hub in dev mode.

**Architecture:** The tab generator (`generate-tab-registry.ts`) gets a grouping pass that merges tabs sharing a `skillId` into a `GroupedTab` with `children`. Grouping uses URL prefix as a secondary signal to avoid incorrectly merging unrelated tabs from the same skill. `HubTabBar` renders these as dropdown buttons. The sidebar adds a hardcoded hidden hub entry with `category: "dev"`.

**Tech Stack:** TypeScript, React, Next.js, Jest

**Spec:** `docs/superpowers/specs/2026-03-22-page-cleanup-grouped-nav-design.md`

---

## File Structure

| File | Role |
|------|------|
| `apps/dashboard/lib/tabs/types.ts` | Add `GroupedTab`, `TabEntry` types |
| `apps/dashboard/lib/tabs/tab-grouping.ts` | New — `isGroupedTab`, `groupBySkillId` |
| `apps/dashboard/components/tabs/GroupDropdown.tsx` | New — shared dropdown component |
| `apps/dashboard/scripts/generate-tab-registry.ts` | Add grouping pass + update ADR-177 validation |
| `apps/dashboard/components/HubTabBar.tsx` | Render grouped tabs |
| `apps/dashboard/components/UnifiedHubTabs.tsx` | Render grouped tabs |
| `apps/dashboard/lib/navigation.ts` | Add hidden hub dev-mode entry |
| `tests/dashboard/lib/tab-grouping.test.ts` | New — unit tests |
| `tests/dashboard/lib/navigation-hidden-hub.test.ts` | New — unit tests |
| `tests/dashboard/lib/generate-tab-registry.test.ts` | Update existing tests |

---

### Task 1: Add GroupedTab type and isGroupedTab guard

**Files:**
- Modify: `apps/dashboard/lib/tabs/types.ts`
- Create: `apps/dashboard/lib/tabs/tab-grouping.ts`
- Create: `tests/dashboard/lib/tab-grouping.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// tests/dashboard/lib/tab-grouping.test.ts
import { describe, it, expect } from '@jest/globals';

describe('isGroupedTab', () => {
  it('returns true for tab with non-empty children array', () => {
    const { isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const grouped = {
      id: 'daemon', label: 'Daemon', icon: 'Server', href: '/command/daemon',
      children: [
        { id: 'health', label: 'Health', href: '/command/daemon/health' },
        { id: 'jobs', label: 'Jobs', href: '/command/daemon/jobs' },
      ],
    };
    expect(isGroupedTab(grouped)).toBe(true);
  });

  it('returns false for flat tab without children', () => {
    const { isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    expect(isGroupedTab({ id: 'logs', label: 'Logs', href: '/command/logs' })).toBe(false);
  });

  it('returns false for tab with empty children', () => {
    const { isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    expect(isGroupedTab({ id: 'x', label: 'X', href: '/x', children: [] })).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/tab-grouping.test.ts --no-cache`
Expected: FAIL — module not found

- [ ] **Step 3: Add types and create tab-grouping module**

Add to `apps/dashboard/lib/tabs/types.ts` after the `TabItem` type (after line 26):

```typescript
/**
 * A tab that groups multiple skill sub-pages into a dropdown.
 * Skills with 2+ tabs at the same URL depth become grouped.
 */
export interface GroupedTab extends TabItem {
  /** Sub-pages within this skill group */
  children: TabItem[];
}

/** Union type for flat tabs and grouped tabs */
export type TabEntry = TabItem | GroupedTab;
```

Also update `HubConfig.tabs` (line 58) and `HubConfig.overflow` (line 60) to use `TabEntry[]`:

```typescript
  tabs: TabEntry[];
  overflow?: TabEntry[];
```

Create `apps/dashboard/lib/tabs/tab-grouping.ts`:

```typescript
import type { TabItem, GroupedTab, TabEntry } from './types';

/**
 * Type guard: is this tab entry a grouped dropdown?
 * True only if children is a non-empty array.
 */
export function isGroupedTab(tab: TabEntry): tab is GroupedTab {
  return 'children' in tab && Array.isArray((tab as GroupedTab).children) && (tab as GroupedTab).children.length > 0;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/tab-grouping.test.ts --no-cache`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/tabs/types.ts apps/dashboard/lib/tabs/tab-grouping.ts tests/dashboard/lib/tab-grouping.test.ts
git commit -m "feat(tabs): add GroupedTab type and isGroupedTab guard"
```

---

### Task 2: Implement groupBySkillId function

**Files:**
- Modify: `apps/dashboard/lib/tabs/tab-grouping.ts`
- Modify: `tests/dashboard/lib/tab-grouping.test.ts`

**Key design decision:** Grouping uses `skillId` AND a shared URL prefix. Tabs sharing a `skillId` but at divergent URL paths (e.g., `/command/updater` and `/command/updater/plugins` labeled "Custom Plugins") are only grouped if their hrefs share a common base path derived from the skillId. This prevents the command hub's "Custom Plugins" (`skillId: updater`, href: `/command/updater/plugins`) from being incorrectly merged with "Updater" (`skillId: updater`, href: `/command/updater`) when they are in separate visible/overflow sections.

The heuristic: for each `skillId` group, find the longest common href prefix. If all tabs share a prefix of at least `/{hub}/{skill}`, group them. If not (hrefs diverge at the skill level), keep them flat.

- [ ] **Step 1: Write the failing tests**

Add to `tests/dashboard/lib/tab-grouping.test.ts`:

```typescript
describe('groupBySkillId', () => {
  it('leaves tabs without skillId as flat', () => {
    const { groupBySkillId } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'overview', label: 'Overview', href: '/command' },
      { id: 'logs', label: 'Logs', href: '/command/logs', skillId: 'devops' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual(tabs[0]);
    expect(result[1]).toEqual(tabs[1]);
  });

  it('groups tabs sharing a skillId with common URL prefix', () => {
    const { groupBySkillId, isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'overview', label: 'Overview', href: '/command' },
      { id: 'daemon', label: 'Daemon', href: '/command/daemon', skillId: 'daemon' },
      { id: 'health', label: 'Health', href: '/command/daemon/health', skillId: 'daemon' },
      { id: 'jobs', label: 'Jobs', href: '/command/daemon/jobs', skillId: 'daemon' },
      { id: 'logs', label: 'Logs', href: '/command/logs', skillId: 'devops' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(3);
    expect(result[0].id).toBe('overview');
    expect(isGroupedTab(result[1])).toBe(true);
    const group = result[1] as any;
    expect(group.id).toBe('daemon');
    expect(group.label).toBe('Daemon');
    expect(group.href).toBe('/command/daemon');
    expect(group.children).toHaveLength(3);
    expect(result[2].id).toBe('logs');
  });

  it('does NOT group tabs with same skillId but divergent URL paths', () => {
    const { groupBySkillId, isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'plugins', label: 'Custom Plugins', href: '/command/updater/plugins', skillId: 'updater', order: 60 },
      { id: 'updater', label: 'Updater', href: '/command/updater', skillId: 'updater' },
    ];
    const result = groupBySkillId(tabs);
    // These share skillId "updater" and /command/updater prefix, but since one IS
    // the prefix of the other, they should group (updater is parent of updater/plugins)
    expect(isGroupedTab(result[0])).toBe(true);
  });

  it('preserves order of first occurrence of each skillId', () => {
    const { groupBySkillId } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'overview', label: 'Overview', href: '/life' },
      { id: 'voice', label: 'Voice Memos', href: '/life/apple/voice', skillId: 'apple' },
      { id: 'scenes', label: 'Scenes', href: '/life/home-automation/scenes', skillId: 'home-automation' },
      { id: 'lighting', label: 'Lighting', href: '/life/home-automation/lighting', skillId: 'home-automation' },
      { id: 'attention', label: 'Attention', href: '/life/attention', skillId: 'attention' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(4);
    expect(result[0].id).toBe('overview');
    expect(result[1].id).toBe('voice');
    expect(result[2].id).toBe('home-automation');
    expect(result[3].id).toBe('attention');
  });

  it('uses skillId as group label with smart formatting', () => {
    const { groupBySkillId, isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'a', label: 'A', href: '/x/home-automation/a', skillId: 'home-automation' },
      { id: 'b', label: 'B', href: '/x/home-automation/b', skillId: 'home-automation' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(1);
    expect(isGroupedTab(result[0])).toBe(true);
    expect(result[0].label).toBe('Home Automation');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/tab-grouping.test.ts --no-cache`
Expected: FAIL — groupBySkillId is not a function

- [ ] **Step 3: Implement groupBySkillId**

Add to `apps/dashboard/lib/tabs/tab-grouping.ts`:

```typescript
/**
 * Convert a skill-id like "home-automation" to "Home Automation".
 */
function formatSkillLabel(skillId: string): string {
  return skillId
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/**
 * Group tabs by skillId. Skills with 2+ tabs become GroupedTab dropdowns.
 * Skills with 1 tab and tabs without skillId pass through as flat TabItems.
 * Order: groups appear at the position of the first tab with that skillId.
 */
export function groupBySkillId(tabs: TabItem[]): TabEntry[] {
  const bySkill = new Map<string, TabItem[]>();
  const flatTabs: { index: number; tab: TabItem }[] = [];
  const groupPositions = new Map<string, number>();

  for (let i = 0; i < tabs.length; i++) {
    const tab = tabs[i];
    const skill = tab.skillId;
    if (!skill) {
      flatTabs.push({ index: i, tab });
      continue;
    }
    if (!bySkill.has(skill)) {
      bySkill.set(skill, []);
      groupPositions.set(skill, i);
    }
    bySkill.get(skill)!.push(tab);
  }

  const entries: { index: number; entry: TabEntry }[] = [
    ...flatTabs.map(({ index, tab }) => ({ index, entry: tab as TabEntry })),
  ];

  for (const [skill, skillTabs] of bySkill) {
    const pos = groupPositions.get(skill)!;
    if (skillTabs.length === 1) {
      entries.push({ index: pos, entry: skillTabs[0] });
    } else {
      const group: GroupedTab = {
        id: skill,
        label: formatSkillLabel(skill),
        icon: skillTabs[0].icon,
        href: skillTabs[0].href,
        skillId: skill,
        children: skillTabs,
      };
      entries.push({ index: pos, entry: group });
    }
  }

  entries.sort((a, b) => a.index - b.index);
  return entries.map((e) => e.entry);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/tab-grouping.test.ts --no-cache`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/tabs/tab-grouping.ts tests/dashboard/lib/tab-grouping.test.ts
git commit -m "feat(tabs): implement groupBySkillId for tab grouping"
```

---

### Task 3: Integrate grouping into the tab generator

**Files:**
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts`
- Modify: `tests/dashboard/lib/generate-tab-registry.test.ts`

Two changes: (1) add grouping pass after building `customTabs`, (2) update ADR-177 validation to flatten grouped tab children before verifying page.tsx existence.

- [ ] **Step 1: Write the failing test**

Add to `tests/dashboard/lib/generate-tab-registry.test.ts`:

```typescript
describe('grouped tabs (skill sub-page grouping)', () => {
  it('command hub daemon tabs are grouped into a single entry', () => {
    const commandHub = registry['command'];
    expect(commandHub).toBeDefined();
    const daemonEntry = commandHub.tabs.find(
      (t: any) => t.id === 'daemon' && Array.isArray(t.children),
    );
    expect(daemonEntry).toBeDefined();
    expect(daemonEntry.children.length).toBeGreaterThanOrEqual(2);
    // Daemon sub-pages should NOT appear as separate top-level tabs
    const flatDaemonSubs = commandHub.tabs.filter(
      (t: any) => !t.children && t.skillId === 'daemon' && t.id !== 'daemon',
    );
    expect(flatDaemonSubs).toHaveLength(0);
  });

  it('life hub home-automation tabs are grouped', () => {
    const lifeHub = registry['life'];
    const haGroup = lifeHub.tabs.find(
      (t: any) => t.id === 'home-automation' && Array.isArray(t.children),
    );
    expect(haGroup).toBeDefined();
    expect(haGroup.children.length).toBeGreaterThanOrEqual(2);
  });

  it('single-tab skills remain flat', () => {
    for (const hubId of Object.keys(registry)) {
      const hub = registry[hubId];
      for (const tab of [...hub.tabs, ...(hub.overflow || [])]) {
        if (tab.children) {
          expect(tab.children.length).toBeGreaterThanOrEqual(2);
        }
      }
    }
  });

  it('overview tab is always flat', () => {
    for (const hubId of Object.keys(registry)) {
      const overview = registry[hubId].tabs.find((t: any) => t.id === 'overview');
      expect(overview).toBeDefined();
      expect(overview.children).toBeUndefined();
    }
  });

  it('grouped tab href points to first child', () => {
    for (const hubId of Object.keys(registry)) {
      for (const tab of registry[hubId].tabs) {
        if (tab.children && tab.children.length > 0) {
          expect(tab.href).toBe(tab.children[0].href);
        }
      }
    }
  });
});
```

Also update the existing test `'content tab hrefs follow /{hub}/... pattern'` to recurse into children. Find it and add after the existing iteration:

```typescript
    // Also check children of grouped tabs
    if (tab.children) {
      for (const child of tab.children) {
        expect(child.href).toMatch(new RegExp(`^/${hubId}/`));
      }
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/generate-tab-registry.test.ts --no-cache -t "grouped tabs"`
Expected: FAIL — no `children` property on tabs

- [ ] **Step 3: Modify the generator — add grouping pass**

In `apps/dashboard/scripts/generate-tab-registry.ts`:

Add import at top (after line 31):

```typescript
import { groupBySkillId } from "../lib/tabs/tab-grouping";
```

Add local types after the `TabItem` interface (after line 46):

```typescript
interface GroupedTabItem extends TabItem {
  children: TabItem[];
}
type TabEntry = TabItem | GroupedTabItem;
```

Update `HubConfig.tabs` to `TabEntry[]` and `HubConfig.overflow` to `TabEntry[]`.

Replace lines 336-342:

```typescript
    // Split into visible and overflow based on maxVisibleTabs
    // Overview counts as one of the visible tabs
    const visibleSlots = maxVisibleTabs - 1; // minus overview
    const visibleContentTabs = customTabs.slice(0, visibleSlots);
    const overflowTabs = customTabs.slice(visibleSlots);

    const allVisibleTabs = [overviewTab, ...visibleContentTabs];
```

With:

```typescript
    // Group multi-page skills into dropdown tabs
    const groupedContentTabs = groupBySkillId(customTabs);

    // Split into visible and overflow based on maxVisibleTabs
    // Overview counts as one of the visible tabs
    const visibleSlots = maxVisibleTabs - 1; // minus overview
    const visibleContentTabs = groupedContentTabs.slice(0, visibleSlots);
    const overflowTabs = groupedContentTabs.slice(visibleSlots);

    const allVisibleTabs = [overviewTab, ...visibleContentTabs];
```

- [ ] **Step 4: Modify the generator — update ADR-177 validation**

In the ADR-177 validation section (lines 641-663), change line 642:

```typescript
    const allTabs = [...hubConfig.tabs, ...(hubConfig.overflow || [])];
```

To flatten grouped tab children:

```typescript
    const allTabs = [...hubConfig.tabs, ...(hubConfig.overflow || [])].flatMap(
      (tab: any) => ('children' in tab && Array.isArray(tab.children)) ? [tab, ...tab.children] : [tab]
    );
```

This ensures every child href inside a grouped tab also gets validated against page.tsx existence.

- [ ] **Step 5: Regenerate the registry**

Run: `cd apps/dashboard && npm run generate-tabs`
Expected: Registry regenerates with `"children":` entries visible in output

- [ ] **Step 6: Verify output**

Run: `grep -c '"children"' apps/dashboard/lib/tabs/generated-registry.ts`
Expected: At least 3

- [ ] **Step 7: Run tests**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/generate-tab-registry.test.ts --no-cache`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/scripts/generate-tab-registry.ts apps/dashboard/lib/tabs/generated-registry.ts tests/dashboard/lib/generate-tab-registry.test.ts
git commit -m "feat(tabs): integrate groupBySkillId into tab generator with ADR-177 child validation"
```

---

### Task 4: Create shared GroupDropdown component

**Files:**
- Create: `apps/dashboard/components/tabs/GroupDropdown.tsx`

Extract the dropdown as a shared component used by both `HubTabBar` and `UnifiedHubTabs` (DRY — avoids duplicating ~55 lines).

- [ ] **Step 1: Create the shared component**

```typescript
// apps/dashboard/components/tabs/GroupDropdown.tsx
"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import * as LucideIcons from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { TabItem, TabEntry } from "@/lib/tabs/types";
import React, { useRef, useState, useEffect } from "react";

function renderIcon(
  icon: string | LucideIcon | React.ReactNode | undefined,
  className: string,
): React.ReactNode {
  if (!icon) return null;
  if (typeof icon === "string") {
    const IconComponent =
      (LucideIcons as unknown as Record<string, LucideIcon>)[icon] ||
      LucideIcons.LayoutDashboard;
    return <IconComponent className={className} />;
  }
  if (typeof icon === "function") {
    const IconComponent = icon as LucideIcon;
    return <IconComponent className={className} />;
  }
  if (React.isValidElement(icon)) {
    return React.cloneElement(
      icon as React.ReactElement<{ className?: string }>,
      { className },
    );
  }
  return null;
}

export function GroupDropdown({
  group,
  renderTab,
  pathname,
}: {
  group: TabEntry & { children: TabItem[] };
  renderTab: (tab: TabItem) => React.ReactNode;
  pathname: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const isActive = group.children.some(
    (child) =>
      child.href &&
      (pathname === child.href || pathname.startsWith(child.href + "/")),
  );

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <div className="flex items-center">
        <Link
          href={group.href || "#"}
          prefetch={false}
          className={cn(
            "group relative flex items-center gap-2 pl-4 pr-1 py-2.5 rounded-l-xl text-sm font-medium transition-all duration-200 whitespace-nowrap",
            isActive
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm border border-r-0 border-[var(--border-color)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]/50",
          )}
        >
          {renderIcon(
            group.icon,
            cn(
              "w-4 h-4 transition-colors duration-200",
              isActive
                ? "text-[var(--accent-primary)]"
                : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]",
            ),
          )}
          <span>{group.label}</span>
          {isActive && (
            <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-6 h-0.5 bg-[var(--accent-primary)] rounded-full" />
          )}
        </Link>
        <button
          onClick={() => setOpen((o) => !o)}
          className={cn(
            "flex items-center pr-3 pl-1 py-2.5 rounded-r-xl text-sm transition-all duration-200",
            isActive
              ? "bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm border border-l-0 border-[var(--border-color)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]/50",
          )}
        >
          <LucideIcons.ChevronDown
            className={cn(
              "w-3.5 h-3.5 transition-transform",
              open && "rotate-180",
            )}
          />
        </button>
      </div>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[180px] rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] shadow-lg p-1">
          {group.children.map((child) => (
            <div key={child.href || child.id} onClick={() => setOpen(false)}>
              {renderTab(child)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Build to verify**

Run: `cd apps/dashboard && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/tabs/GroupDropdown.tsx
git commit -m "feat(tabs): create shared GroupDropdown component"
```

---

### Task 5: Update HubTabBar to render grouped tabs

**Files:**
- Modify: `apps/dashboard/components/HubTabBar.tsx`

- [ ] **Step 1: Update imports**

Change line 8:

```typescript
import type { TabItem, BlockNavItem } from "@/lib/tabs/types";
```

To:

```typescript
import type { TabItem, TabEntry, BlockNavItem } from "@/lib/tabs/types";
import { isGroupedTab } from "@/lib/tabs/tab-grouping";
import { GroupDropdown } from "./tabs/GroupDropdown";
```

- [ ] **Step 2: Update HubTabBarProps**

Change `tabs` and `overflow` types (lines 20-26):

```typescript
interface HubTabBarProps {
  tabs: TabEntry[];
  overflow?: TabEntry[];
  blocks?: BlockNavItem[];
  autoPages?: TabItem[];
  basePath: string;
}
```

- [ ] **Step 3: Update MoreDropdown types**

Change `MoreDropdown` props (lines 57-64) to accept `TabEntry[]`:

```typescript
function MoreDropdown({
  tabs,
  isActive,
  renderTab,
}: {
  tabs: TabEntry[];
  isActive: boolean;
  renderTab: (tab: TabItem) => React.ReactNode;
}) {
```

Inside `MoreDropdown`, update the render to handle grouped tabs in overflow:

```typescript
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 min-w-[180px] rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] shadow-lg p-1">
          {tabs.map((tab) =>
            isGroupedTab(tab) ? (
              tab.children.map((child) => (
                <div key={child.href || child.id} onClick={() => setOpen(false)}>
                  {renderTab(child)}
                </div>
              ))
            ) : (
              <div key={tab.href || tab.id} onClick={() => setOpen(false)}>
                {renderTab(tab)}
              </div>
            )
          )}
        </div>
      )}
```

- [ ] **Step 4: Update allTabs merge and rendering**

Change the `allTabs` merge (line 130):

```typescript
  const allTabs: TabEntry[] = overflow ? [...tabs, ...overflow] : [...tabs];
```

In the measurer div (lines 240-249), add chevron width for grouped tabs:

```typescript
        {filteredTabs.map((t) => (
          <span
            key={t.href || t.id}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap"
          >
            {t.icon && <span className="w-4 h-4" />}
            <span>{t.label}</span>
            {isGroupedTab(t) && <span className="w-3.5 h-3.5" />}
          </span>
        ))}
```

Replace the visible tabs render (line 252):

```typescript
        {visibleTabs.map((t) =>
          isGroupedTab(t) ? (
            <GroupDropdown key={t.id} group={t} renderTab={renderTab} pathname={pathname} />
          ) : (
            renderTab(t)
          ),
        )}
```

Update `isOverflowActive` (lines 219-223):

```typescript
  const isOverflowActive = overflowTabs.some((tab) => {
    if (isGroupedTab(tab)) {
      return tab.children.some(
        (child) => child.href && (pathname === child.href || pathname.startsWith(child.href + "/")),
      );
    }
    return tab.href && (pathname === tab.href || pathname.startsWith(tab.href + "/"));
  });
```

- [ ] **Step 5: Build to verify**

Run: `cd apps/dashboard && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/components/HubTabBar.tsx
git commit -m "feat(tabs): render grouped skill tabs in HubTabBar"
```

---

### Task 6: Update UnifiedHubTabs for grouped tab support

**Files:**
- Modify: `apps/dashboard/components/UnifiedHubTabs.tsx`

Same changes as Task 5 but for the `UnifiedHubTabs` variant. Uses the shared `GroupDropdown`.

- [ ] **Step 1: Update imports and types**

Add imports:

```typescript
import type { TabEntry } from "@/lib/tabs/types";
import { isGroupedTab } from "@/lib/tabs/tab-grouping";
import { GroupDropdown } from "./tabs/GroupDropdown";
```

Change `UnifiedHubTabsProps`:

```typescript
export type UnifiedHubTabsProps = {
  tabs: TabEntry[];
  overflow?: TabEntry[];
};
```

- [ ] **Step 2: Update MoreDropdown, measurer, and render loop**

Apply the same pattern as Task 5:
- `MoreDropdown` accepts `TabEntry[]`, flattens grouped tabs in overflow
- Measurer includes chevron width for grouped tabs
- Visible render loop checks `isGroupedTab` and renders `GroupDropdown`
- `isOverflowActive` checks children

- [ ] **Step 3: Build to verify**

Run: `cd apps/dashboard && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/UnifiedHubTabs.tsx
git commit -m "feat(tabs): render grouped skill tabs in UnifiedHubTabs"
```

---

### Task 7: Expose hidden hub in dev mode

**Files:**
- Modify: `apps/dashboard/lib/navigation.ts`
- Create: `tests/dashboard/lib/navigation-hidden-hub.test.ts`

The hidden hub is NOT in `assembled-hubs.json` (only 6 hubs: adaptive, brain, career, command, life, studio). It exists only as pages in `apps/dashboard/app/hidden/`. The fix: add a hardcoded nav item for the hidden hub with `category: "dev"`.

- [ ] **Step 1: Write the failing test**

```typescript
// tests/dashboard/lib/navigation-hidden-hub.test.ts
import { describe, it, expect } from '@jest/globals';

describe('hidden hub dev-mode visibility', () => {
  it('hidden hub is excluded in production mode', () => {
    const { getEnabledSections } = require('../../../apps/dashboard/lib/navigation');
    const sections = getEnabledSections(false);
    const allItems = sections.flatMap((s: any) => s.items);
    const hidden = allItems.find((item: any) => item.href === '/hidden');
    expect(hidden).toBeUndefined();
  });

  it('hidden hub is included in development mode', () => {
    const { getEnabledSections } = require('../../../apps/dashboard/lib/navigation');
    const sections = getEnabledSections(true);
    const allItems = sections.flatMap((s: any) => s.items);
    const hidden = allItems.find((item: any) => item.href === '/hidden');
    expect(hidden).toBeDefined();
    expect(hidden.label).toBe('Templates');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/navigation-hidden-hub.test.ts --no-cache`
Expected: FAIL — hidden hub not found

- [ ] **Step 3: Modify navigation.ts**

In `apps/dashboard/lib/navigation.ts`, find the `getHubItems()` function (line 60). After the return statement that maps assembled hubs (line 70-79), add a hardcoded hidden hub entry:

```typescript
function getHubItems(): NavItem[] {
  const hubs = (assembledHubsData as { hubs: Array<{
    id: string;
    title: string;
    icon?: string;
    category?: string;
    nav_order?: number;
    nav_hidden?: boolean;
  }> }).hubs;

  const items = hubs
    .filter((hub) => !hub.nav_hidden && !HIDDEN_CATEGORIES.has(hub.category ?? ""))
    .sort((a, b) => (a.nav_order ?? 999) - (b.nav_order ?? 999))
    .map((hub) => ({
      href: `/${hub.id}`,
      label: hub.title,
      icon: resolveIcon(hub.icon ?? "LayoutDashboard"),
      category: hub.category === "system" ? "dev" : undefined,
    }));

  // Hidden templates hub — dev-mode only, not in assembled-hubs.json
  items.push({
    href: '/hidden',
    label: 'Templates',
    icon: resolveIcon('FolderArchive'),
    category: 'dev',
  });

  return items;
}
```

The existing `isNavItemEnabled` (line 84-88) already filters out `category: "dev"` items when `devModeEnabled` is false.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/navigation-hidden-hub.test.ts --no-cache`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/navigation.ts tests/dashboard/lib/navigation-hidden-hub.test.ts
git commit -m "feat(nav): expose hidden templates hub in dev mode only"
```

---

### Task 8: Full build + verification

**Files:** None new — verification only

- [ ] **Step 1: Regenerate the tab registry**

Run: `cd apps/dashboard && npm run generate-tabs`
Expected: Success, no ADR-177 validation errors

- [ ] **Step 2: Run all tests**

Run: `cd apps/dashboard && npx jest ../../tests/dashboard/lib/tab-grouping.test.ts ../../tests/dashboard/lib/generate-tab-registry.test.ts ../../tests/dashboard/lib/navigation-hidden-hub.test.ts --no-cache`
Expected: All tests pass

- [ ] **Step 3: Run full build**

Use `/dev-build` or: `cd apps/dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Manual browser verification**

Start dev server and verify:
1. Command hub: Daemon sub-pages grouped into dropdown (9 -> ~4 primary tabs)
2. Life hub: Home Automation sub-pages grouped; no overflow
3. Career hub: Learning+Quiz grouped, Venture Augur+Demo grouped
4. Brain/Adaptive/Studio: unchanged
5. Click group label -> navigates to first child
6. Click chevron -> opens dropdown with children
7. Active state highlights group when on child route
8. Escape key closes dropdown
9. Hidden hub ("Templates") appears in sidebar only in dev mode

- [ ] **Step 5: Commit regenerated files**

```bash
git add apps/dashboard/lib/tabs/generated-registry.ts
git commit -m "chore: regenerate tab registry with grouped skill tabs"
```
