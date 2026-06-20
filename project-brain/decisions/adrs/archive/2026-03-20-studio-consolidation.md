# Studio Hub Consolidation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Studio hub from 18 routes to 5 focused pages by deleting duplicates, removing fluff, and fixing component sizing.

**Architecture:** The existing pages (`advisor/page.tsx`, `frontend/page.tsx`, `mcp-app-factory/page.tsx`) are already consolidated mega-pages with section components. This plan moves them to cleaner routes, deletes duplicates/stubs, strips decorative fluff, and makes components full-width by default.

**Tech Stack:** Next.js 16, React, Tailwind CSS, shadcn/ui, Augur plugin-discovery scanner

---

## File Structure

### New files (5 pages at clean routes)
- `plugins/ui/pages/studio/workbench/page.tsx` — re-export of existing advisor page with fluff removed
- `plugins/ui/pages/studio/design/page.tsx` — re-export of existing frontend page with fluff removed
- `plugins/ui/pages/studio/factory/page.tsx` — re-export of existing mcp-app-factory page with inline tabs
- `plugins/ui/pages/studio/terminal/page.tsx` — re-export of existing terminal page
- `plugins/ui/pages/studio/workbench/analytics/page.tsx` — preserved sub-page

### Deleted files (13 routes)
- `plugins/ui/pages/studio/advisor/` (moved to workbench)
- `plugins/ui/pages/studio/advisor/analytics/` (moved to workbench/analytics)
- `plugins/ui/pages/studio/developer/` (merged into workbench)
- `plugins/ui/pages/studio/devops/overview/` (empty SkillAutoPage)
- `plugins/ui/pages/studio/devops/refactor/` (merged into workbench)
- `plugins/ui/pages/studio/frontend/` (moved to design)
- `plugins/ui/pages/studio/frontend/audit/` (duplicate of design)
- `plugins/ui/pages/studio/mcp-app-factory/audit/` (thin stub)
- `plugins/ui/pages/studio/mcp-app-factory/create/` (thin stub)
- `plugins/ui/pages/studio/mcp-app-factory/import/` (thin stub)
- `plugins/ui/pages/studio/mcp-app-factory/migrate/` (thin stub)
- `plugins/ui/pages/studio/mcp-app-factory/templates/` (thin stub)
- `plugins/ui/pages/studio/renderer/` (merged into design)
- `plugins/ui/pages/studio/validator/compliance/` (merged into factory)
- `plugins/ui/pages/studio/terminal-automation-template/` (moved to terminal)

### Kept as-is
- `plugins/ui/pages/studio/page-builder/builder/page.tsx` — full-screen canvas editor, needs its own route
- `plugins/ui/pages/studio/page-builder/page.tsx` — page list landing

---

## Task 1: Create `/studio/workbench` from existing advisor page

**Files:**
- Move: `plugins/ui/pages/studio/advisor/page.tsx` → `plugins/ui/pages/studio/workbench/page.tsx`
- Move: `plugins/ui/pages/studio/advisor/analytics/page.tsx` → `plugins/ui/pages/studio/workbench/analytics/page.tsx`
- Delete: `plugins/ui/pages/studio/developer/tools/page.tsx` (already inlined in advisor)
- Delete: `plugins/ui/pages/studio/devops/overview/page.tsx` (empty SkillAutoPage)
- Delete: `plugins/ui/pages/studio/devops/refactor/page.tsx` (already inlined in advisor)

- [ ] **Step 1: Move advisor page to workbench**

```bash
mkdir -p plugins/ui/pages/studio/workbench/analytics
mv plugins/ui/pages/studio/advisor/page.tsx plugins/ui/pages/studio/workbench/page.tsx
mv plugins/ui/pages/studio/advisor/analytics/page.tsx plugins/ui/pages/studio/workbench/analytics/page.tsx
```

- [ ] **Step 2: Remove fluff from workbench page**

In `plugins/ui/pages/studio/workbench/page.tsx`:
- Remove any "Cross-Hub Navigation" `GlassCard` sections with generic link cards
- Remove decorative `GlassCard` sections that only contain static text descriptions with no interactivity
- Keep all actionable sections (buttons, forms, data tables, health checks)

- [ ] **Step 3: Delete old duplicate directories**

```bash
rm -rf plugins/ui/pages/studio/advisor
rm -rf plugins/ui/pages/studio/developer
rm -rf plugins/ui/pages/studio/devops
```

- [ ] **Step 4: Sync to mounted location**

```bash
# Remove old mounted dirs
rm -rf apps/dashboard/app/studio/advisor
rm -rf apps/dashboard/app/studio/developer
rm -rf apps/dashboard/app/studio/devops

# Copy new
mkdir -p apps/dashboard/app/studio/workbench/analytics
cp plugins/ui/pages/studio/workbench/page.tsx apps/dashboard/app/studio/workbench/page.tsx
cp plugins/ui/pages/studio/workbench/analytics/page.tsx apps/dashboard/app/studio/workbench/analytics/page.tsx
```

- [ ] **Step 5: Verify build**

```bash
cd apps/dashboard && npx next build 2>&1 | grep -E "error|Error|Compiled"
```
Expected: `Compiled successfully`

---

## Task 2: Create `/studio/design` from existing frontend page

**Files:**
- Move: `plugins/ui/pages/studio/frontend/page.tsx` → `plugins/ui/pages/studio/design/page.tsx`
- Delete: `plugins/ui/pages/studio/frontend/audit/page.tsx` (duplicate)
- Delete: `plugins/ui/pages/studio/renderer/page.tsx` (already inlined)

- [ ] **Step 1: Move frontend page to design**

```bash
mkdir -p plugins/ui/pages/studio/design
mv plugins/ui/pages/studio/frontend/page.tsx plugins/ui/pages/studio/design/page.tsx
```

- [ ] **Step 2: Remove fluff from design page**

In `plugins/ui/pages/studio/design/page.tsx`:
- Delete the entire `RendererSection` function and its call in the main export (lines ~318-430) — it's all static text cards and a "Cross-Hub Navigation" section with generic links to Career/Finance/Observe/Productivity
- Delete the `RENDERER_BLOCKS` constant
- Remove unused imports (`Monitor`, `FileText`, `Braces`, `Database`, `ArrowRight`, `GlassLinkCard` if no longer used)
- Keep `FrontendAuditSection` (actionable: mount/wiring verification with Run buttons)
- Keep `PageBuilderSection` (actionable: page grid with create/delete)

- [ ] **Step 3: Delete old directories**

```bash
rm -rf plugins/ui/pages/studio/frontend
rm -rf plugins/ui/pages/studio/renderer
```

- [ ] **Step 4: Sync to mounted location**

```bash
rm -rf apps/dashboard/app/studio/frontend
rm -rf apps/dashboard/app/studio/renderer
mkdir -p apps/dashboard/app/studio/design
cp plugins/ui/pages/studio/design/page.tsx apps/dashboard/app/studio/design/page.tsx
```

- [ ] **Step 5: Verify build**

```bash
cd apps/dashboard && npx next build 2>&1 | grep -E "error|Error|Compiled"
```

---

## Task 3: Create `/studio/factory` from existing mcp-app-factory page

**Files:**
- Move: `plugins/ui/pages/studio/mcp-app-factory/page.tsx` → `plugins/ui/pages/studio/factory/page.tsx`
- Move: `plugins/ui/pages/studio/mcp-app-factory/tabs/` → `plugins/ui/pages/studio/factory/tabs/`
- Merge: `plugins/ui/pages/studio/validator/compliance/page.tsx` content into factory page
- Delete: 5 thin stub pages (audit, create, import, migrate, templates)

- [ ] **Step 1: Move factory page and tabs**

```bash
mkdir -p plugins/ui/pages/studio/factory
mv plugins/ui/pages/studio/mcp-app-factory/page.tsx plugins/ui/pages/studio/factory/page.tsx
mv plugins/ui/pages/studio/mcp-app-factory/tabs plugins/ui/pages/studio/factory/tabs
```

- [ ] **Step 2: Fix import paths in factory page**

Update relative imports from `./tabs/` — these should still work since tabs/ moved with the page. Verify:
```
import OverviewTab from './tabs/OverviewTab';
```

- [ ] **Step 3: Remove fluff from factory page**

In `plugins/ui/pages/studio/factory/page.tsx`:
- Remove any generic link cards or decorative description-only sections
- Ensure the tab components (Create, Templates, Audit, Import, Migrate) render inline via tab state, not as separate routes
- The existing page may already have Quick Actions linking to sub-routes — convert those to `onClick` tab switches

- [ ] **Step 4: Delete old directories**

```bash
rm -rf plugins/ui/pages/studio/mcp-app-factory
rm -rf plugins/ui/pages/studio/validator
```

- [ ] **Step 5: Sync to mounted location**

```bash
rm -rf apps/dashboard/app/studio/mcp-app-factory
rm -rf apps/dashboard/app/studio/validator
mkdir -p apps/dashboard/app/studio/factory
cp -r plugins/ui/pages/studio/factory/ apps/dashboard/app/studio/factory/
```

- [ ] **Step 6: Verify build**

```bash
cd apps/dashboard && npx next build 2>&1 | grep -E "error|Error|Compiled"
```

---

## Task 4: Create `/studio/terminal` from existing terminal page

**Files:**
- Move: `plugins/ui/pages/studio/terminal-automation-template/terminal/page.tsx` → `plugins/ui/pages/studio/terminal/page.tsx`
- Move: `plugins/ui/pages/studio/terminal-automation-template/automations/` → `plugins/ui/pages/studio/terminal/automations/`
- Move: `plugins/ui/pages/studio/terminal-automation-template/components/` → `plugins/ui/pages/studio/terminal/components/`
- Move: `plugins/ui/pages/studio/terminal-automation-template/settings/` → `plugins/ui/pages/studio/terminal/settings/`

- [ ] **Step 1: Move terminal page**

```bash
mkdir -p plugins/ui/pages/studio/terminal
mv plugins/ui/pages/studio/terminal-automation-template/terminal/page.tsx plugins/ui/pages/studio/terminal/page.tsx
# Move supporting dirs if they exist
[ -d plugins/ui/pages/studio/terminal-automation-template/automations ] && mv plugins/ui/pages/studio/terminal-automation-template/automations plugins/ui/pages/studio/terminal/
[ -d plugins/ui/pages/studio/terminal-automation-template/components ] && mv plugins/ui/pages/studio/terminal-automation-template/components plugins/ui/pages/studio/terminal/
[ -d plugins/ui/pages/studio/terminal-automation-template/settings ] && mv plugins/ui/pages/studio/terminal-automation-template/settings plugins/ui/pages/studio/terminal/
```

- [ ] **Step 2: Fix import paths**

Update any relative imports in the moved page to account for the new directory structure.

- [ ] **Step 3: Delete old directory**

```bash
rm -rf plugins/ui/pages/studio/terminal-automation-template
```

- [ ] **Step 4: Sync to mounted location**

```bash
rm -rf apps/dashboard/app/studio/terminal-automation-template
mkdir -p apps/dashboard/app/studio/terminal
cp -r plugins/ui/pages/studio/terminal/ apps/dashboard/app/studio/terminal/
```

- [ ] **Step 5: Verify build**

```bash
cd apps/dashboard && npx next build 2>&1 | grep -E "error|Error|Compiled"
```

---

## Task 5: Update API route paths in moved pages

After moving pages, some may reference API routes with old prefixes. The studio agent already fixed `/api/dev/` → `/api/studio/` and `/api/consulting/` → `/api/studio/`, but verify:

- [ ] **Step 1: Grep for stale route references**

```bash
grep -rn '/api/dev/\|/api/consulting/\|/api/admin/' plugins/ui/pages/studio/ --include="*.tsx"
```
Expected: No matches

- [ ] **Step 2: Grep for old page-builder route**

```bash
grep -rn '/admin/page-builder' plugins/ui/pages/studio/ --include="*.tsx"
```
If found, update to `/studio/page-builder/builder`.

- [ ] **Step 3: Update internal navigation links**

Search for Links pointing to old routes:
```bash
grep -rn "href=.*studio/advisor\|href=.*studio/frontend\|href=.*studio/mcp-app-factory\|href=.*terminal-automation" plugins/ui/pages/studio/ --include="*.tsx"
```
Update any found to new routes (`/studio/workbench`, `/studio/design`, `/studio/factory`, `/studio/terminal`).

---

## Task 6: Regenerate tab registry and update hub landing

- [ ] **Step 1: Regenerate tab registry**

```bash
cd apps/dashboard && node scripts/build-scripts.mjs && node scripts/dist/generate-tab-registry.mjs
```

Expected: Studio hub shows 5 tabs (workbench, design, factory, page-builder, terminal) instead of 17+

- [ ] **Step 2: Update studio hub landing to redirect**

In `apps/dashboard/app/studio/page.tsx`, update to redirect to `/studio/workbench` instead of showing the generic HubLandingPage:

```tsx
import { redirect } from 'next/navigation';
export default function Page() {
  redirect('/studio/workbench');
}
```

- [ ] **Step 3: Full build and verify**

```bash
cd apps/dashboard && npx next build 2>&1 | tail -20
```
Expected: 0 errors, studio routes visible in output

- [ ] **Step 4: Commit**

```bash
git add plugins/ui/pages/studio/ apps/dashboard/app/studio/ apps/dashboard/lib/tabs/generated-registry.ts
git commit -m "refactor(studio): consolidate 18 routes to 5 focused pages

- Move advisor → /studio/workbench (analytics + dev tools + capability audit)
- Move frontend → /studio/design (audit + page builder)
- Move mcp-app-factory → /studio/factory (plugins + compliance)
- Move terminal-automation → /studio/terminal
- Delete 13 duplicate/stub routes
- Remove decorative fluff (cross-hub nav, static renderer cards)
- Regenerate tab registry"
```
