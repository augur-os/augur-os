# Page Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 58 dashboard pages by eliminating logical duplicates, dissolving the observe hub, splitting tabbed mega-pages, converting 20 pages to AutoPage, and rebuilding remaining pages with existing shared components.

**Architecture:** Bottom-up component-level approach. Most shared components already exist (StatCard, DataTableBlock, StatusBadge, ActionBar, GlassCard, EmptyState, Skeleton). Only 3-4 new components needed. Main work is adoption, structural changes, and AutoPage conversions.

**Tech Stack:** Next.js App Router, React, TypeScript, shadcn/ui, SkillAutoPage, block YAML (augur.yaml), MCP tools

**Spec:** `docs/superpowers/specs/2026-03-21-page-consolidation-design.md`

---

## Plan Structure

This plan is split into 3 sub-plans executed sequentially:

- **Plan A (this file):** Phase 1 (build missing components) + Phase 2 (kill duplicates, dissolve observe)
- **Plan B:** Phases 3-4 (split mega-pages, focus fuzzy pages) — write after Plan A is complete
- **Plan C:** Phases 5-6 (AutoPage conversions, rebuild remaining) — write after Plan B is complete

---

## Pre-Work: Component Inventory

Most planned shared components **already exist**. Before building anything, verify what's available:

| Planned component | Already exists? | Location |
|-------------------|----------------|----------|
| `<StatGrid>` | YES | `@/components/ui/StatCard` + `@/components/blocks/types/StatGridBlock` |
| `<ActionBar>` | YES | `@/components/blocks/ActionBar.tsx` |
| `<StatusBadge>` | YES | `@/components/ui/StatusBadge` (5 tones) |
| `<PageHero>` | YES (as GlassCard) | `@/components/ui/GlassCard` with icon, title, subtitle, headerActions |
| `<DataTable>` | YES | `@/components/blocks/types/DataTableBlock` with search/filter/sort/row actions |
| `<DataList>` | YES | `@/components/blocks/types/DataListBlock` |
| `<EmptyState>` | YES | `@/components/ui/EmptyState` |
| `<Skeleton>` | YES (7 variants) | `@/components/ui/Skeleton` |
| `<SearchFilter>` | PARTIAL | `@/components/ui/FilterBar` (tabs + sort + refresh) — needs search input integration |
| `<CollapsibleSection>` | NO | Must build |
| `<NavLinkGrid>` | NO | Must build (GlassLinkCard exists for individual cards) |
| `<PageStates>` | PARTIAL | EmptyState + Skeleton exist but no unified wrapper |
| `<LightControlCard>` | NO | Domain component — extract from home-automation |
| `<SceneQuickButtons>` | NO | Domain component — extract from home-automation |

**Actual work for Phase 1:** Build 3 components, extract 2 domain components, create 1 unified wrapper.

---

## Phase 1: Build Missing Components

### Task 1: Build `<CollapsibleSection>` component

**Files:**
- Create: `apps/dashboard/components/ui/CollapsibleSection.tsx`

- [ ] **Step 1: Create CollapsibleSection component**

```tsx
"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface CollapsibleSectionProps {
  title: string;
  icon?: LucideIcon;
  count?: number;
  defaultOpen?: boolean;
  color?: string;
  children: ReactNode;
  className?: string;
}

export function CollapsibleSection({
  title,
  icon: Icon,
  count,
  defaultOpen = false,
  color,
  children,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn("border border-[var(--border-color)] rounded-lg", className)}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-4 py-3 text-left hover:bg-[var(--bg-tertiary)] transition-colors rounded-lg"
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-4 h-4" style={color ? { color } : undefined} />}
          <span className="text-sm font-medium text-[var(--text-primary)]">{title}</span>
          {count !== undefined && (
            <span className="text-xs text-[var(--text-muted)] bg-[var(--bg-tertiary)] px-2 py-0.5 rounded-full">
              {count}
            </span>
          )}
        </div>
        <ChevronDown
          className={cn(
            "w-4 h-4 text-[var(--text-muted)] transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Verify it renders**

Run: `pnpm --filter dashboard build`
Expected: Build passes with no errors

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/ui/CollapsibleSection.tsx
git commit -m "feat: add CollapsibleSection shared component"
```

### Task 2: Build `<NavLinkGrid>` component

**Files:**
- Create: `apps/dashboard/components/ui/NavLinkGrid.tsx`

- [ ] **Step 1: Create NavLinkGrid component**

```tsx
import { GlassLinkCard } from "@/components/ui/GlassCard";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavLink {
  label: string;
  href: string;
  icon: LucideIcon;
  description?: string;
  color?: string;
}

interface NavLinkGridProps {
  links: NavLink[];
  columns?: 2 | 3 | 4;
  className?: string;
}

export function NavLinkGrid({ links, columns = 3, className }: NavLinkGridProps) {
  const colClass =
    columns === 2 ? "grid-cols-1 sm:grid-cols-2" :
    columns === 4 ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" :
    "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3";

  return (
    <div className={cn("grid gap-3", colClass, className)}>
      {links.map((link) => (
        <GlassLinkCard
          key={link.href}
          href={link.href}
          title={link.label}
          description={link.description}
          icon={link.icon}
          color={link.color}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `pnpm --filter dashboard build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/ui/NavLinkGrid.tsx
git commit -m "feat: add NavLinkGrid shared component"
```

### Task 3: Build `<PageStates>` wrapper component

**Files:**
- Create: `apps/dashboard/components/ui/PageStates.tsx`

- [ ] **Step 1: Create PageStates component**

```tsx
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { AlertCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface PageStatesProps {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: LucideIcon;
  emptyAction?: { label: string; onClick: () => void };
  children: ReactNode;
}

export function PageStates({
  loading,
  error,
  empty,
  emptyTitle = "No data",
  emptyDescription = "Nothing to display yet.",
  emptyIcon,
  emptyAction,
  children,
}: PageStatesProps) {
  if (loading) {
    return <Skeleton variant="shimmer" className="h-64 w-full rounded-lg" />;
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-4 text-red-400 bg-red-500/10 rounded-lg border border-red-500/20">
        <AlertCircle className="w-5 h-5 flex-shrink-0" />
        <span className="text-sm">{error}</span>
      </div>
    );
  }

  if (empty) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
        icon={emptyIcon}
        action={emptyAction}
      />
    );
  }

  return <>{children}</>;
}
```

- [ ] **Step 2: Verify build**

Run: `pnpm --filter dashboard build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/ui/PageStates.tsx
git commit -m "feat: add PageStates unified loading/error/empty wrapper"
```

### Task 4: Extract `<LightControlCard>` from home-automation

**Files:**
- Create: `plugins/ui/pages/life/home-automation/components/LightControlCard.tsx`
- Modify: `plugins/ui/pages/life/home-automation/page.tsx`
- Modify: `plugins/ui/pages/life/home-automation/lighting/page.tsx`

- [ ] **Step 1: Read both pages to identify the duplicated light card code**

Read: `plugins/ui/pages/life/home-automation/page.tsx` (lines 219-262)
Read: `plugins/ui/pages/life/home-automation/lighting/page.tsx` (lines 288-389)
Identify the shared interface (`Light`), shared toggle/brightness logic, shared JSX structure.

- [ ] **Step 2: Create LightControlCard component**

Extract the shared light card rendering (toggle switch + brightness slider + name + status) into a standalone component. Include the `useDebouncedCallback` for brightness. Accept `light`, `onToggle`, `onBrightness` as props.

- [ ] **Step 3: Update home-automation/page.tsx to use LightControlCard**

Replace inline light card rendering (lines 219-262) with `<LightControlCard>` component.

- [ ] **Step 4: Update lighting/page.tsx to use LightControlCard**

Replace inline light card rendering (lines 288-389) with `<LightControlCard>` component.

- [ ] **Step 5: Verify build**

Run: `pnpm --filter dashboard build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add plugins/ui/pages/life/home-automation/components/LightControlCard.tsx
git add plugins/ui/pages/life/home-automation/page.tsx
git add plugins/ui/pages/life/home-automation/lighting/page.tsx
git commit -m "refactor: extract LightControlCard from duplicate implementations"
```

### Task 5: Extract `<SceneQuickButtons>` from home-automation

**Files:**
- Create: `plugins/ui/pages/life/home-automation/components/SceneQuickButtons.tsx`
- Modify: `plugins/ui/pages/life/home-automation/page.tsx`
- Modify: `plugins/ui/pages/life/home-automation/lighting/page.tsx`

- [ ] **Step 1: Read both pages to identify duplicated scene button code**

Read: `plugins/ui/pages/life/home-automation/page.tsx` (lines 198-212)
Read: `plugins/ui/pages/life/home-automation/lighting/page.tsx` (lines 267-283)

- [ ] **Step 2: Create SceneQuickButtons component**

Extract the scene activation button grid. Accept `scenes`, `onActivate`, `activatingId` as props.

- [ ] **Step 3: Update both pages to use SceneQuickButtons**

- [ ] **Step 4: Verify build and commit**

Run: `pnpm --filter dashboard build`

```bash
git add plugins/ui/pages/life/home-automation/components/SceneQuickButtons.tsx
git add plugins/ui/pages/life/home-automation/page.tsx
git add plugins/ui/pages/life/home-automation/lighting/page.tsx
git commit -m "refactor: extract SceneQuickButtons from duplicate implementations"
```

---

## Phase 2: Kill Logical Duplicates + Dissolve Observe

### Task 6: Delete stub pages (contracts, outreach)

**Files:**
- Delete: `plugins/ui/pages/career/venture-augur/sales/contracts/page.tsx`
- Delete: `plugins/ui/pages/career/venture-augur/sales/outreach/page.tsx`

- [ ] **Step 1: Delete both stub files**

```bash
rm plugins/ui/pages/career/venture-augur/sales/contracts/page.tsx
rm plugins/ui/pages/career/venture-augur/sales/outreach/page.tsx
```

- [ ] **Step 2: Check for and remove any empty parent directories**

```bash
find plugins/ui/pages/career/venture-augur/sales -type d -empty -delete
```

- [ ] **Step 3: Verify build**

Run: `pnpm --filter dashboard build`
Expected: PASS (no other files import these pages)

- [ ] **Step 4: Commit**

```bash
git add -A plugins/ui/pages/career/venture-augur/sales/
git commit -m "chore: remove stub pages with no real backend (contracts, outreach)"
```

### Task 7: Delete duplicate reading-list/reading-list page

**Files:**
- Delete: `plugins/ui/pages/brain/reading-list/reading-list/page.tsx`

- [ ] **Step 1: Verify parent page is a superset**

Read: `plugins/ui/pages/brain/reading-list/page.tsx` — confirm it includes all functionality from the child.

- [ ] **Step 2: Delete the child page**

```bash
rm plugins/ui/pages/brain/reading-list/reading-list/page.tsx
rmdir plugins/ui/pages/brain/reading-list/reading-list 2>/dev/null || true
```

- [ ] **Step 3: Verify build and commit**

Run: `pnpm --filter dashboard build`

```bash
git add -A plugins/ui/pages/brain/reading-list/reading-list/
git commit -m "chore: remove reading-list/reading-list (subsumed by parent)"
```

### Task 8: Convert redirect pages to Next.js rewrites

**Files:**
- Delete: `plugins/ui/pages/brain/knowledge/page.tsx`
- Delete: `plugins/ui/pages/command/daemon/metrics/page.tsx`
- Delete: `plugins/ui/pages/life/apple/page.tsx`
- Modify: `apps/dashboard/next.config.js` (or `next.config.ts`)

- [ ] **Step 1: Read current next.config to understand rewrite format**

Read: `apps/dashboard/next.config.js` (or `.ts` or `.mjs`) — find existing rewrites section.

- [ ] **Step 2: Add rewrites for the 3 redirect pages**

Add to the rewrites config:
```js
{ source: '/brain/knowledge', destination: '/brain/knowledge/memory' },
{ source: '/command/daemon/metrics', destination: '/command/daemon/loops' },
{ source: '/life/apple', destination: '/life/apple/overview' },
```

- [ ] **Step 3: Delete the 3 redirect page files**

```bash
rm plugins/ui/pages/brain/knowledge/page.tsx
rm plugins/ui/pages/command/daemon/metrics/page.tsx
rm plugins/ui/pages/life/apple/page.tsx
```

- [ ] **Step 4: Verify build and test rewrites**

Run: `pnpm --filter dashboard build`

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/next.config.* plugins/ui/pages/brain/knowledge/page.tsx plugins/ui/pages/command/daemon/metrics/page.tsx plugins/ui/pages/life/apple/page.tsx
git commit -m "refactor: convert 3 redirect pages to Next.js rewrites"
```

### Task 9: Delete ops-daemon page

**Files:**
- Delete: `plugins/ui/pages/command/ops-daemon/page.tsx`

- [ ] **Step 1: Verify daemon landing will cover this content**

Read: `plugins/ui/pages/command/ops-daemon/page.tsx` — confirm it's a 31-line wrapper around DaemonOverviewClient.

- [ ] **Step 2: Delete and commit**

```bash
rm plugins/ui/pages/command/ops-daemon/page.tsx
rmdir plugins/ui/pages/command/ops-daemon 2>/dev/null || true
git add -A plugins/ui/pages/command/ops-daemon/
git commit -m "chore: remove ops-daemon (absorbed into daemon landing)"
```

### Task 10: Remove duplicate workflow section from updater page

**Files:**
- Modify: `plugins/ui/pages/command/updater/page.tsx` (remove workflow section)
- Preserve: `plugins/ui/pages/command/workflows/page.tsx` (this stays as canonical)

- [ ] **Step 1: Read updater/page.tsx and find the WorkflowsSection**

Read: `plugins/ui/pages/command/updater/page.tsx` — locate the embedded WorkflowsSection (expected around lines 391-510).

- [ ] **Step 2: Remove WorkflowsSection from updater page**

Remove the WorkflowsSection component definition and its rendering from updater/page.tsx. Keep the UpdaterSection only.

- [ ] **Step 3: Verify build and commit**

Run: `pnpm --filter dashboard build`

```bash
git add plugins/ui/pages/command/updater/page.tsx
git commit -m "refactor: remove duplicate workflow section from updater (canonical at /command/workflows)"
```

### Task 11: Dissolve observe hub — promote logs, sessions, self-heal

This is the largest structural change in Phase 2. The observe hub's 4 page wrappers are deleted. Three original content pages are promoted to standalone command pages. Supporting tab/component files are migrated.

**Files:**
- Delete: `plugins/ui/pages/command/observe/page.tsx`
- Delete: `plugins/ui/pages/command/observe/health/page.tsx`
- Promote: `plugins/ui/pages/command/observe/logs/page.tsx` → standalone at `plugins/ui/pages/command/logs/page.tsx`
- Promote: `plugins/ui/pages/command/observe/sessions/page.tsx` → standalone at `plugins/ui/pages/command/sessions/page.tsx`
- Create: `plugins/ui/pages/command/self-heal/page.tsx` (extract from daemon's SelfHealSection)
- Migrate: `plugins/ui/pages/command/observe/tabs/LogsTabView.tsx` → `plugins/ui/pages/command/logs/`
- Migrate: `plugins/ui/pages/command/observe/tabs/SessionsTab.tsx` → `plugins/ui/pages/command/sessions/`
- Add rewrites: `/command/observe/*` → new locations

- [ ] **Step 1: Read all observe page wrappers and tab files**

Read every file in `plugins/ui/pages/command/observe/` to understand the ObserveTabScreen pattern and what each tab renders.

- [ ] **Step 2: Create standalone logs page**

Create `plugins/ui/pages/command/logs/page.tsx` that renders LogsTabView directly (without ObserveTabScreen wrapper). Import the actual LogsTab component. Preserve the `?category=` query param support.

- [ ] **Step 3: Create standalone sessions page**

Create `plugins/ui/pages/command/sessions/page.tsx` that renders SessionsTab directly.

- [ ] **Step 4a: Read daemon/page.tsx and identify SelfHealSection boundaries**

Read: `plugins/ui/pages/command/daemon/page.tsx` — find SelfHealSection (expected lines 490-1005). Identify all sub-components (EventCard, SelfHealStatsHero, filter state), MCP calls (`/api/command/daemon/self-heal`, `/api/command/daemon/health`), and state variables.

- [ ] **Step 4b: Create self-heal page with imports and data fetching**

Create `plugins/ui/pages/command/self-heal/page.tsx`. Copy the MCP query hooks and state management from SelfHealSection. Set up the page shell with PageStates wrapper.

- [ ] **Step 4c: Copy the rendering logic (event list, filters, stats hero)**

Copy the JSX from SelfHealSection into the new page. This is a COPY, not a move — daemon/page.tsx keeps its SelfHealSection for now. Removing it from daemon is Phase 3 work (daemon → landing page).

- [ ] **Step 4d: Verify the new self-heal page builds**

Run: `pnpm --filter dashboard build`

- [ ] **Step 5: Add Next.js rewrites for old observe URLs**

```js
{ source: '/command/observe', destination: '/command/daemon' },
{ source: '/command/observe/health', destination: '/command/daemon/health' },
{ source: '/command/observe/logs', destination: '/command/logs' },
{ source: '/command/observe/logs/:path*', destination: '/command/logs/:path*' },
{ source: '/command/observe/sessions', destination: '/command/sessions' },
```

- [ ] **Step 6: Delete observe directory**

```bash
rm -rf plugins/ui/pages/command/observe/
```

- [ ] **Step 7: Verify build**

Run: `pnpm --filter dashboard build`
Expected: PASS

- [ ] **Step 8: Test rewrites work**

Navigate to old URLs in browser — confirm they redirect to new locations.

- [ ] **Step 9: Commit**

```bash
git add -A plugins/ui/pages/command/observe/ plugins/ui/pages/command/logs/ plugins/ui/pages/command/sessions/ plugins/ui/pages/command/self-heal/ apps/dashboard/next.config.*
git commit -m "refactor: dissolve observe hub — promote logs, sessions, self-heal to standalone command pages"
```

### Task 12: Remove duplicate content from venture-augur/demo

**Files:**
- Modify: `plugins/ui/pages/career/venture-augur/demo/page.tsx`

- [ ] **Step 1: Read demo page**

Read: `plugins/ui/pages/career/venture-augur/demo/page.tsx` — identify TierDistribution, WeightConfig, SkillScoreTable imports and rendering.

- [ ] **Step 2: Remove skill scores embed, keep DemoCatalog only**

Remove the TierDistribution, WeightConfig, SkillScoreTable sections. Add a link to `/adaptive/auto-skill-quality/skill-scores` instead.

- [ ] **Step 3: Verify build and commit**

Run: `pnpm --filter dashboard build`

```bash
git add plugins/ui/pages/career/venture-augur/demo/page.tsx
git commit -m "refactor: remove skill scores embed from demo (canonical at /adaptive/skill-scores)"
```

### Task 13: Remove daemon IntegrationsTab (duplicate of ai_bridge/integrations)

**Deferred to Plan B (Phase 3).** The daemon IntegrationsTab at `plugins/ui/pages/command/daemon/tabs/IntegrationsTab.tsx` (~200 LOC) is a near-duplicate of ai_bridge's integrations. However, removing it requires modifying daemon/page.tsx's tab structure, which is Phase 3 work (splitting daemon into landing + sub-pages). Noted here for traceability — the spec lists it as Phase 2 but the actual removal is coupled to the daemon restructure.

### Task 14: Remove ai_bridge MemoryTab (duplicate of knowledge/memory)

**Deferred to Plan B (Phase 3).** The ai_bridge MemoryTab at `plugins/ui/pages/brain/ai_bridge/tabs/MemoryTab.tsx` (~273 LOC) is a read-only duplicate of knowledge/memory. Removing it requires modifying ai_bridge/page.tsx's tab structure, which is Phase 3 work (splitting ai_bridge into standalone pages). The tab will be replaced by a link to `/brain/knowledge/memory`.

---

**Note on observe dissolution (Task 11):** When `rm -rf plugins/ui/pages/command/observe/` is executed in Step 6, the following files are **intentionally killed** (not migrated):
- `ObserveTabScreen.tsx` — wrapper component, no longer needed when pages are standalone
- `OverviewTab.tsx` — duplicate of daemon overview widgets
- `HealthTab.tsx` — duplicate of daemon/health (just renders MetricsTab)
- `MarkersTab.tsx` — code markers view (can be re-added as standalone page later if needed)
- `WorkflowSuiteCard.tsx` — duplicate of `/command/workflows`
- `loading.tsx` — observe loading state, no longer needed

Only `LogsTabView.tsx`/`LogsTab` and `SessionsTab.tsx` are migrated to new locations.

---

## Checkpoint: Phase 1-2 Complete

After completing all 12 tasks:
- 3 new shared components built (CollapsibleSection, NavLinkGrid, PageStates)
- 2 domain components extracted (LightControlCard, SceneQuickButtons)
- 8 pages/sections deleted (stubs, duplicates, redirects)
- Observe hub dissolved — 3 pages promoted to standalone
- 1 duplicate section removed from updater
- 1 duplicate embed removed from demo

**Verify:** Run full build (`pnpm --filter dashboard build`) and confirm no regressions.

**Next:** Plan B covers Phases 3-4 (split mega-pages + focus fuzzy pages). Write in a follow-up session.
