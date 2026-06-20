# Page Type Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 3 page types into a clear 2-type, 3-tier architecture: Custom TSX (hub tabs), Config YAML (block picker), Auto-generated (browse only).

**Architecture:** Modify the tab generation pipeline to exclude YAML-sourced pages from hub tabs and place them in a new "Skill Pages" section of the block picker panel. Auto-pages remain browse-only. Storage enforced: TSX in `skills/dashboard/pages/`, YAML in `skills/{skill}/augur/pages/`.

**Tech Stack:** TypeScript, Next.js, React (dashboard scripts + components)

**Spec:** `docs/superpowers/specs/2026-03-31-page-type-consolidation-design.md`

---

### Task 1: Add `pageSource` field to tab registry generation

**Files:**
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts:245`
- Modify: `apps/dashboard/lib/tabs/types.ts` (add `pageSource` to TabItem)

- [ ] **Step 1: Add `pageSource` to TabItem type**

In `apps/dashboard/lib/tabs/types.ts`, find the `TabItem` interface and add:

```typescript
/** Where this page comes from — determines visibility tier */
pageSource?: "tsx" | "yaml" | "auto";
```

- [ ] **Step 2: Track page source in generate-tab-registry.ts**

In `apps/dashboard/scripts/generate-tab-registry.ts`, around line 245 where `pageTypeMap` is set, also track the source. Find where pages are assembled into tab entries and add `pageSource` based on the import path:

- If import path contains `@skill/pages/` → `"tsx"`
- If import path contains `@/lib/configs/` → `"yaml"`
- Otherwise → `"auto"`

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/lib/tabs/types.ts apps/dashboard/scripts/generate-tab-registry.ts
git commit -m "feat: add pageSource field to tab registry for tier-based visibility"
```

---

### Task 2: Split tabs into `tabs` (TSX only) and `configPages` (YAML) in generated registry

**Files:**
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts:483-620` (registry output section)
- Modify: `apps/dashboard/lib/tabs/generated-registry.ts` (output — auto-generated)
- Modify: `apps/dashboard/lib/tabs/types.ts` (HubConfig type)

- [ ] **Step 1: Add `configPages` field to HubConfig type**

In `apps/dashboard/lib/tabs/types.ts`, find the `HubConfig` interface and add:

```typescript
/** YAML config pages — shown in block picker, not in hub tabs */
configPages: TabItem[];
```

- [ ] **Step 2: Filter YAML pages out of tabs in generate-tab-registry.ts**

In the registry output section (~line 483-620), where `tabs` array is assembled, split the entries:

```typescript
// Before writing tabs, separate by pageSource
const tsTabs = allTabs.filter(t => t.pageSource !== "yaml");
const configPages = allTabs.filter(t => t.pageSource === "yaml");
```

Write `tsTabs` to `tabs` and `configPages` to the new `configPages` field.

- [ ] **Step 3: Rebuild plugins and verify**

```bash
pnpm --filter dashboard run rebuild-plugins
```

Check `apps/dashboard/lib/tabs/generated-registry.ts` — YAML pages should now be in `configPages` instead of `tabs`.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/scripts/generate-tab-registry.ts apps/dashboard/lib/tabs/types.ts
git commit -m "feat: separate YAML config pages from hub tabs into configPages field"
```

---

### Task 3: Update HubTabNav to exclude configPages from tab bar

**Files:**
- Modify: `apps/dashboard/components/plugin/HubTabNav.tsx`

- [ ] **Step 1: Find where tabs are read from registry**

The `HubTabNav` component reads `tabs` from the hub config to render the tab bar. Since YAML pages are now in `configPages` instead of `tabs`, the tab bar automatically excludes them — no code change needed if the component only reads `tabs`.

Verify by reading the component and confirming it only uses `config.tabs` (not `config.configPages` or iterating all entries).

- [ ] **Step 2: Rebuild and verify in browser**

```bash
pnpm --filter dashboard run rebuild-plugins
```

Navigate to a hub that had YAML tabs (e.g., `/life`) and verify:
- Custom TSX pages still appear as tabs (file-manager, home-automation, apple/voice)
- YAML pages (wealth, health, attention, eisenhower, wearables) are NO LONGER in the tab bar

- [ ] **Step 3: Commit**

```bash
git commit -m "verify: YAML pages excluded from hub tab bar via configPages split"
```

---

### Task 4: Add "Skill Pages" section to CustomizePanel (block picker)

**Files:**
- Modify: `apps/dashboard/components/plugin/CustomizePanel.tsx:253-279`

- [ ] **Step 1: Read the current autoPages section**

The CustomizePanel already has a "Pages" section (lines 253-279) that shows `autoPages`. Replace this with `configPages` from the hub config.

- [ ] **Step 2: Update the pages section to show configPages**

Find the section that renders autoPages (around line 253-279). Replace the data source from `autoPages` to `configPages`:

```typescript
{/* Skill Pages — YAML config pages accessible via block picker */}
{configPages && configPages.length > 0 && (
  <div className="mt-4">
    <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider px-4 mb-2">
      Skill Pages
    </h3>
    <div className="space-y-1 px-2">
      {configPages.map((page) => (
        <a
          key={page.id}
          href={page.href}
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-[var(--bg-hover)] transition-colors text-sm text-[var(--text-primary)] cursor-pointer"
        >
          {page.icon && <PageIcon name={page.icon} className="w-4 h-4 text-[var(--text-muted)]" />}
          <span>{page.label}</span>
        </a>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 3: Pass configPages prop to CustomizePanel**

Find where CustomizePanel is instantiated and pass the `configPages` from the hub config. Check the parent component (likely `HubTabBar.tsx` or `HubLayout.tsx`) and add the prop.

- [ ] **Step 4: Verify in browser**

Open a hub, click the grid icon (block picker). Verify "Skill Pages" section appears with the YAML config pages listed. Click one — verify it navigates to the page.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/plugin/CustomizePanel.tsx
git commit -m "feat: show YAML config pages in block picker panel as Skill Pages"
```

---

### Task 5: Ensure YAML pages remain routable via direct URL

**Files:**
- Verify: `apps/dashboard/app/{hub}/[[...slug]]/registry.ts` (auto-generated)

- [ ] **Step 1: Verify YAML pages still in PAGES map**

After rebuild, check that YAML pages still have entries in the `PAGES` map of each hub's registry.ts. They must stay routable — removing from tabs doesn't mean removing from URL routing.

```bash
grep "lib/configs" app/life/'[[...slug]]'/registry.ts
```

Expected: YAML imports like `'wealth': () => import('@/lib/configs/life-wealth')` still present.

- [ ] **Step 2: Test direct URL access**

Navigate to `http://localhost:3000/life/wealth` directly — verify the page still renders.

- [ ] **Step 3: Commit verification**

```bash
git commit --allow-empty -m "verify: YAML config pages remain routable via direct URL"
```

---

### Task 6: Delete simple YAML configs that auto-generation covers

**Files:**
- Delete: `skills/scraper/augur/pages/overview.yaml`
- Delete: `skills/document-extractor/augur/pages/overview.yaml`
- Delete: `skills/dashboard/augur/pages/factory.yaml`
- Delete: `skills/dashboard/augur/pages/design.yaml`
- Delete: `skills/daemon/augur/pages/self-heal.yaml`
- Delete: `skills/auto-vault-hygiene/augur/pages/overview.yaml`

- [ ] **Step 1: Verify each skill has `x-augur-mcp-tools` in SKILL.md**

For each skill above, confirm the SKILL.md has MCP tools that `buildDefaultPageConfig()` can use to generate a smart auto-page. If a skill has no tools, keep its YAML.

- [ ] **Step 2: Delete the YAML files**

```bash
rm skills/scraper/augur/pages/overview.yaml
rm skills/document-extractor/augur/pages/overview.yaml
rm skills/dashboard/augur/pages/factory.yaml
rm skills/dashboard/augur/pages/design.yaml
rm skills/daemon/augur/pages/self-heal.yaml
rm skills/auto-vault-hygiene/augur/pages/overview.yaml
```

- [ ] **Step 3: Rebuild and verify**

```bash
pnpm --filter dashboard run rebuild-plugins
```

Verify the deleted pages no longer appear in registries or block picker. Verify `/browse/{skill}` still renders smart auto-pages for these skills.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete 6 simple YAML configs absorbed by smart auto-pages"
```

---

### Task 7: Promote high-traffic YAML pages to Custom TSX (Phase 1 batch)

This is the largest task — converting important YAML pages to custom TSX so they keep hub tab visibility. Start with the venture-augur pattern as reference.

**Files:**
- Reference: `skills/dashboard/pages/career/venture-augur/page.tsx`
- Create: `skills/dashboard/pages/life/wealth/page.tsx`
- Create: `skills/dashboard/pages/life/health/page.tsx`
- Create: `skills/dashboard/pages/career/pipeline/page.tsx`
- Delete (after promotion): corresponding YAML files
- Modify: each skill's SKILL.md to add `contributions.pages` if missing

**Note:** This task is large and should be decomposed into sub-tasks, one per page. Each page follows the same pattern:

1. Read the YAML config to understand blocks and MCP tools
2. Create a custom TSX page at `skills/dashboard/pages/{hub}/{skill}/page.tsx`
3. Use `useMcpQuery` for each data source with proper `unwrap` handling
4. Build purpose-specific React components (not generic blocks)
5. Add `contributions.pages` to SKILL.md if not present
6. Delete the YAML config
7. Rebuild and verify

- [ ] **Step 1: Convert wealth page**

Already done in this session — `skills/dashboard/pages/career/venture-augur/page.tsx` is the reference. Wealth needs similar treatment with portfolio cards, crypto cards, and financial goals progress.

- [ ] **Step 2: Convert health page**

Create `skills/dashboard/pages/life/health/page.tsx` with health-specific components (symptom tracking, medication list, health summary stats).

- [ ] **Step 3: Convert pipeline page**

Create `skills/dashboard/pages/career/pipeline/page.tsx` with job application tracking (searchable table, status filters, row actions for analyze/update).

- [ ] **Step 4: Rebuild and verify each**

After each conversion:
```bash
pnpm --filter dashboard run rebuild-plugins
```
Verify the page appears as a hub tab and renders correctly.

- [ ] **Step 5: Commit each separately**

```bash
git commit -m "feat: promote wealth to custom TSX page"
git commit -m "feat: promote health to custom TSX page"
git commit -m "feat: promote pipeline to custom TSX page"
```

---

### Task 8: Enforce storage rules via lint

**Files:**
- Modify: `.claude/hooks/pre-commit` or equivalent lint config

- [ ] **Step 1: Add lint rule**

Add a check that fails if:
- A `page.tsx` exists in `skills/*/augur/dashboard/` (except `skills/dashboard/`)
- A YAML page config exists in `skills/dashboard/augur/pages/`

This enforces: TSX in dashboard plugin, YAML in skill dirs.

- [ ] **Step 2: Fix any existing violations**

Move any misplaced files to their correct locations.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: enforce page storage rules — TSX in dashboard plugin, YAML in skills"
```

---

### Task 9: Embed widget canvas in hub overview pages

**Files:**
- Modify: `apps/dashboard/app/{hub}/[[...slug]]/page.tsx` (hub page router — render user blocks on overview)
- Modify: `apps/dashboard/lib/blocks/view-storage.ts` (adapt for per-hub view IDs)
- Modify: `apps/dashboard/components/plugin/CustomizePanel.tsx` (wire "Add" button to hub view)
- Create: Hub overview component that combines default content + user blocks

- [ ] **Step 1: Add per-hub view storage**

Modify `view-storage.ts` to support hub-scoped views. Add a helper:

```typescript
export function getHubViewId(hubId: string): string {
  return `hub-${hubId}-overview`;
}
```

When a hub overview loads, look up `views/hub-{hubId}-overview.yaml`. If it doesn't exist, the overview shows no user blocks.

- [ ] **Step 2: Wire "Add" button in block picker to hub view**

In `CustomizePanel.tsx`, the "Add" button for each block currently adds to a standalone view. Change it to add to the current hub's overview view:

- Get the current hub ID from context/URL
- Call `PUT /api/views/hub-{hubId}-overview` with the new block instance appended

- [ ] **Step 3: Render user blocks on hub overview**

In the hub overview page (the default page when slug is empty), add a section below the default content that renders user-added blocks from the hub's view storage:

```typescript
// After default overview content
<UserBlocksSection hubId={hubId} />
```

`UserBlocksSection` fetches `GET /api/views/hub-{hubId}-overview`, renders each block instance using `BlockRenderer`.

- [ ] **Step 4: Add remove/reorder controls**

In builder mode, show remove (X) buttons on user blocks. Reorder via drag handles.

- [ ] **Step 5: Verify in browser**

Open `/life` → click grid icon → "Add" a block → verify it appears on the overview. Reload page → verify it persists.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: embed widget canvas in hub overview pages"
```

---

### Task 10: Delete standalone widget page

**Files:**
- Delete: `apps/dashboard/app/(views)/view/[id]/page.tsx`
- Delete: `apps/dashboard/app/(views)/view/[id]/` (entire directory)
- Modify: `apps/dashboard/components/SidebarNav.tsx` (remove "Widgets" nav item)

- [ ] **Step 1: Remove the view route**

```bash
rm -rf apps/dashboard/app/\(views\)/view/
```

- [ ] **Step 2: Remove "Widgets" sidebar link**

In `SidebarNav.tsx`, find the `widgetsItem` useMemo (around line 99-106) and the section that renders it. Remove both.

- [ ] **Step 3: Migrate existing view data (optional)**

If the user has blocks in their existing view `68eb4888`, migrate them to per-hub views. Read the old view, distribute blocks by their hub context to `hub-{hubId}-overview.yaml` files.

- [ ] **Step 4: Rebuild and verify**

```bash
pnpm --filter dashboard run rebuild-plugins
```

Verify: `/view/68eb4888` returns 404. Sidebar no longer shows "Widgets". Hub overviews still show user blocks.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: delete standalone widget page — widgets now live in hub overviews"
```

---

### Task 11: Final verification and cleanup

**Files:**
- Verify: All hub registries
- Verify: Block picker panel
- Verify: Browse pages
- Verify: Hub overview user blocks

- [ ] **Step 1: Run full rebuild**

```bash
pnpm --filter dashboard run rebuild-plugins
```

- [ ] **Step 2: Verify tier 1 (hub tabs)**

Check each hub — tabs should ONLY contain Custom TSX pages.

- [ ] **Step 3: Verify tier 2 (block picker)**

Open block picker in each hub — "Skill Pages" section should list YAML config pages. "Add" button places blocks on hub overview.

- [ ] **Step 4: Verify tier 3 (browse)**

Navigate to `/browse/growth`, `/browse/finance`, `/browse/advisor` — smart auto-pages should render.

- [ ] **Step 5: Verify widgets in hub overviews**

Add a block to `/life` overview via block picker. Reload — verify it persists. Verify `/view/68eb4888` no longer exists. Verify sidebar has no "Widgets" link.

- [ ] **Step 6: Verify direct URL routing**

Confirm `/life/wealth`, `/life/health`, `/career/pipeline` still work via direct URL regardless of page type.

- [ ] **Step 7: Commit and tag**

```bash
git commit --allow-empty -m "chore: page type consolidation complete — 2 types, 3 tiers, widgets in hub overviews"
```
