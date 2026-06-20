# Turbopack Catch-All Routes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 140 individually mounted page.tsx files with 6 hub-level optional catch-all routes backed by auto-generated registries, and split the top 5 oversized pages into focused sub-pages.

**Architecture:** Mount-plugins generates one `registry.ts` per hub (slug → dynamic import mapping) instead of copying page files. Each hub gets a `[[...slug]]/page.tsx` optional catch-all that resolves the slug via the registry and renders the component via `next/dynamic` with a module-level cache. Oversized pages are decomposed into focused sub-pages at the plugin source level before registration.

**Tech Stack:** Next.js 16.1.7, Turbopack, TypeScript, next/dynamic, mount-plugins build scripts

**Spec:** `docs/superpowers/specs/2026-03-22-turbopack-catchall-routes-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `apps/dashboard/app/{hub}/[[...slug]]/page.tsx` (×6) | Catch-all route — resolves slug from registry, renders via cached `dynamic()` |
| `apps/dashboard/app/{hub}/[[...slug]]/registry.ts` (×6) | Auto-generated slug → import path mapping + default redirect path |
| `apps/dashboard/scripts/mount/generate-registry.ts` | New module: generates registry.ts files from plugin manifest |
| `plugins/ui/pages/brain/ai_bridge/providers/page.tsx` | New: extracted from ai_bridge monolith |
| `plugins/ui/pages/brain/ai_bridge/sync/page.tsx` | New: extracted from ai_bridge monolith |
| `plugins/ui/pages/brain/reading-list/articles/page.tsx` | New: extracted from reading-list monolith |
| `plugins/ui/pages/brain/reading-list/books/page.tsx` | New: extracted from reading-list monolith |
| `plugins/ui/pages/brain/reading-list/notes/page.tsx` | New: extracted from reading-list monolith |
| `plugins/ui/pages/brain/reading-list/import/page.tsx` | New: extracted from reading-list monolith |
| `plugins/ui/pages/career/learning/courses/page.tsx` | New: extracted from learning monolith |
| `plugins/ui/pages/career/learning/knowledge/page.tsx` | New: extracted from learning monolith |
| `plugins/ui/pages/career/learning/guard/page.tsx` | New: extracted from learning monolith |
| `plugins/ui/pages/career/learning/habits/page.tsx` | New: extracted from learning monolith |
| `plugins/ui/pages/career/learning/hardening/page.tsx` | New: extracted from learning monolith |
| `plugins/ui/pages/studio/workbench/tools/page.tsx` | New: extracted from workbench monolith |
| `plugins/ui/pages/studio/workbench/audit/page.tsx` | New: extracted from workbench monolith |
| `plugins/ui/pages/command/daemon/self-heal/page.tsx` | New: extracted from daemon monolith |

### Modified Files

| File | Change |
|------|--------|
| `apps/dashboard/scripts/mount-plugins.ts` | Replace page-copy logic with registry generation; simplify watcher |
| `apps/dashboard/scripts/generate-tab-registry.ts` | Update ADR-177 validation to check source files instead of mounted files |
| `apps/dashboard/scripts/mount/resolver.ts` | No changes needed — hub filtering works on plugin manifest, not mounted files |

### Deleted Files

| Category | What |
|----------|------|
| ~125 mounted page.tsx files | All auto-generated pages in `app/{hub}/**/page.tsx` |
| ~50 mounted loading.tsx files | All auto-generated loading skeletons (replaced by `dynamic()` loading prop) |
| ~32 mounted layout.tsx files | All passthrough sub-route layouts (hub-level layout preserved) |
| ~3 mounted error.tsx files | Replaced by catch-all error handling |
| 7 hub landing page.tsx files | `app/brain/page.tsx`, `app/career/page.tsx`, etc. (replaced by optional catch-all) |
| 5 monolith source pages | `plugins/ui/pages/*/page.tsx` for reading-list, learning, ai_bridge, workbench, daemon |

---

## Phase 1: Catch-All Infrastructure

### Task 1: Create the Catch-All Route Template

**Files:**
- Create: `apps/dashboard/app/brain/[[...slug]]/page.tsx`
- Create: `apps/dashboard/app/brain/[[...slug]]/registry.ts` (manual test registry)

This task creates the catch-all template for one hub (brain) and verifies it works alongside existing mounted pages before switching everything over.

- [ ] **Step 1: Create the catch-all page component**

Create `apps/dashboard/app/brain/[[...slug]]/page.tsx`:

```tsx
'use client';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { PAGES, DEFAULT_PATH } from './registry';

const DynamicCache = new Map<string, React.ComponentType>();

function getDynamicPage(path: string) {
  if (!DynamicCache.has(path)) {
    const loader = PAGES[path];
    if (!loader) return null;
    DynamicCache.set(path, dynamic(loader, {
      loading: () => <div className="animate-pulse h-full min-h-[200px]" />,
    }));
  }
  return DynamicCache.get(path)!;
}

export default function HubPage() {
  const { slug } = useParams<{ slug?: string[] }>();
  const router = useRouter();
  const path = slug?.join('/') ?? '';

  useEffect(() => {
    if (!path && DEFAULT_PATH) {
      router.replace(DEFAULT_PATH);
    }
  }, [path, router]);

  if (!path) return null;

  const Page = getDynamicPage(path);
  if (!Page) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--text-muted)]">
        Page not found: {path}
      </div>
    );
  }

  return <Page />;
}
```

- [ ] **Step 2: Create a manual test registry for brain hub**

Create `apps/dashboard/app/brain/[[...slug]]/registry.ts` with a few known pages:

```tsx
// MANUAL TEST REGISTRY — will be auto-generated by mount-plugins
export const DEFAULT_PATH = '/brain/knowledge/memory';

export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {
  'ai_bridge/agents': () => import('../../../../plugins/ui/pages/brain/ai_bridge/agents/page'),
};
```

- [ ] **Step 3: Verify the catch-all resolves correctly**

Delete the existing mounted `apps/dashboard/app/brain/ai_bridge/agents/page.tsx` (the one with AUTO-GENERATED comment). Navigate to `http://localhost:3000/brain/ai_bridge/agents` in the browser. Verify:
- Page loads via the catch-all (may show loading skeleton briefly)
- Tab bar still works (hub layout wraps catch-all)
- Agent cards render correctly

- [ ] **Step 4: Verify hub landing redirect works**

Delete `apps/dashboard/app/brain/page.tsx`. Navigate to `http://localhost:3000/brain`. Verify it redirects to `/brain/knowledge/memory`.

- [ ] **Step 5: Restore deleted files and commit**

Restore the test files via `git checkout` (we'll do the real deletion in Phase 1c). Keep the catch-all template. Commit.

```bash
git checkout -- apps/dashboard/app/brain/ai_bridge/agents/page.tsx apps/dashboard/app/brain/page.tsx
git add apps/dashboard/app/brain/\[\[...slug\]\]/
git commit -m "feat: add catch-all route template for brain hub (proof of concept)"
```

---

### Task 2: Build Registry Generator in Mount-Plugins

**Files:**
- Create: `apps/dashboard/scripts/mount/generate-registry.ts`
- Modify: `apps/dashboard/scripts/mount-plugins.ts`

This task adds a new module that generates registry.ts files from the plugin manifest, and wires it into the mount-plugins pipeline.

- [ ] **Step 1: Create the registry generator module**

Create `apps/dashboard/scripts/mount/generate-registry.ts`:

```typescript
import { writeFile, mkdir } from 'fs/promises';
import path from 'path';

interface PageEntry {
  slug: string;        // e.g. 'ai_bridge/agents'
  sourcePath: string;  // absolute path to plugin source page.tsx
}

interface HubRegistry {
  hubId: string;
  defaultPath: string; // e.g. '/brain/knowledge/memory'
  pages: PageEntry[];
}

const CATCHALL_TEMPLATE = `'use client';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { PAGES, DEFAULT_PATH } from './registry';

const DynamicCache = new Map<string, React.ComponentType>();

function getDynamicPage(path: string) {
  if (!DynamicCache.has(path)) {
    const loader = PAGES[path];
    if (!loader) return null;
    DynamicCache.set(path, dynamic(loader, {
      loading: () => <div className="animate-pulse h-full min-h-[200px]" />,
    }));
  }
  return DynamicCache.get(path)!;
}

export default function HubPage() {
  const { slug } = useParams<{ slug?: string[] }>();
  const router = useRouter();
  const path = slug?.join('/') ?? '';

  useEffect(() => {
    if (!path && DEFAULT_PATH) {
      router.replace(DEFAULT_PATH);
    }
  }, [path, router]);

  if (!path) return null;

  const Page = getDynamicPage(path);
  if (!Page) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--text-muted)]">
        Page not found: {path}
      </div>
    );
  }

  return <Page />;
}
`;

export async function generateRegistries(
  appDir: string,
  hubRegistries: HubRegistry[],
): Promise<void> {
  for (const hub of hubRegistries) {
    const catchallDir = path.join(appDir, hub.hubId, '[[...slug]]');
    await mkdir(catchallDir, { recursive: true });

    // Generate registry.ts
    const registryLines = [
      '// AUTO-GENERATED by mount-plugins — do not edit',
      `export const DEFAULT_PATH = '/${hub.hubId}/${hub.defaultPath}';`,
      '',
      'export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {',
    ];

    for (const page of hub.pages) {
      const relativePath = path.relative(catchallDir, page.sourcePath).replace(/\.tsx$/, '');
      registryLines.push(`  '${page.slug}': () => import('${relativePath}'),`);
    }

    registryLines.push('};', '');

    await writeFile(
      path.join(catchallDir, 'registry.ts'),
      registryLines.join('\n'),
    );

    // Write catch-all page.tsx
    await writeFile(
      path.join(catchallDir, 'page.tsx'),
      CATCHALL_TEMPLATE,
    );
  }
}

export function buildHubRegistries(
  mountedPages: Array<{ hubId: string; slug: string; sourcePath: string }>,
  hubDefaults: Record<string, string>,
): HubRegistry[] {
  const hubMap = new Map<string, PageEntry[]>();

  for (const page of mountedPages) {
    if (!hubMap.has(page.hubId)) {
      hubMap.set(page.hubId, []);
    }
    hubMap.get(page.hubId)!.push({ slug: page.slug, sourcePath: page.sourcePath });
  }

  return Array.from(hubMap.entries()).map(([hubId, pages]) => ({
    hubId,
    defaultPath: hubDefaults[hubId] ?? pages[0]?.slug ?? '',
    pages: pages.sort((a, b) => a.slug.localeCompare(b.slug)),
  }));
}
```

- [ ] **Step 2: Wire registry generation into mount-plugins**

In `apps/dashboard/scripts/mount-plugins.ts`, find the section where pages are copied (Phase 4/4b). Add a call to collect page entries for registry generation instead of copying. After the existing mount logic, call `generateRegistries()`.

Read the existing mount-plugins.ts to find exact insertion points. The key changes:
1. During page mounting, collect `{ hubId, slug, sourcePath }` entries instead of (or in addition to) copying files
2. After hub assembly (Phase 5), call `generateRegistries()` with the collected entries
3. Read hub default paths from the existing redirect config (brain → `knowledge/memory`, etc.)

This step modifies mount-plugins to generate registries IN ADDITION to the existing copy behavior. Both coexist temporarily — the catch-all will shadow the old pages.

- [ ] **Step 3: Run mount-plugins and verify registries are generated**

```bash
cd apps/dashboard && node scripts/dist/mount-plugins.mjs
```

Verify that `apps/dashboard/app/{hub}/[[...slug]]/registry.ts` files exist for all 6 hubs and contain correct import paths.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/scripts/mount/generate-registry.ts apps/dashboard/scripts/mount-plugins.ts
git commit -m "feat: add registry generator to mount-plugins pipeline"
```

---

### Task 3: Update Tab Registry Validation (ADR-177)

**Files:**
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts`

The ADR-177 validation at lines 604-653 checks that each tab's href has a corresponding `page.tsx` on the filesystem under `app/`. With catch-all routes, these files no longer exist. Update the validation to check source files instead.

- [ ] **Step 1: Read the current validation logic**

Read `apps/dashboard/scripts/generate-tab-registry.ts` lines 600-660 to understand the exact validation flow.

- [ ] **Step 2: Modify validation to check source files**

The validation currently does:
```typescript
const pageTsxPath = path.join(appDir, hrefPath, 'page.tsx');
await fs.stat(pageTsxPath);
```

Change it to also check the plugin source paths. The tab discovery already uses `discoverPagesFromFilesystem()` (line 178) which knows about plugin source locations. Reuse that source-of-truth:

```typescript
// Check mounted path first (for native routes like settings)
const mountedPath = path.join(appDir, hrefPath, 'page.tsx');
const mountedExists = await fs.stat(mountedPath).then(() => true, () => false);

// Check plugin source path (for catch-all routes)
const catchallRegistry = path.join(appDir, hubId, '[[...slug]]', 'registry.ts');
const registryExists = await fs.stat(catchallRegistry).then(() => true, () => false);

// Valid if either mounted page exists OR catch-all registry exists for this hub
const isValid = mountedExists || registryExists;
```

- [ ] **Step 3: Build and verify**

```bash
cd apps/dashboard && node scripts/build-scripts.mjs && node scripts/dist/generate-tab-registry.mjs
```

Verify: no orphan tab errors, all tabs registered successfully.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/scripts/generate-tab-registry.ts
git commit -m "fix: update ADR-177 tab validation for catch-all routes"
```

---

### Task 4: Switch to Catch-All — Delete Old Mounted Files

**Files:**
- Delete: ~125 mounted page.tsx, ~46 loading.tsx, ~25 layout.tsx, ~2 error.tsx in hub subdirectories
- Delete: 6 hub landing page.tsx files
- Modify: `apps/dashboard/scripts/mount-plugins.ts` (remove page-copy logic)

This is the big switch. After this task, all plugin pages are served through catch-all routes.

- [ ] **Step 1: Create a safety checkpoint**

```bash
git stash push -m "pre-catchall-switch checkpoint"
git stash pop
```

- [ ] **Step 2: Remove page-copy logic from mount-plugins**

In `apps/dashboard/scripts/mount-plugins.ts`, find Phase 4/4b where page files are copied. Remove or disable the file-copy logic for page.tsx, loading.tsx, layout.tsx, and error.tsx files. Keep the registry generation from Task 2.

Also update Phase 5 (hub assembly) to NOT generate hub landing `page.tsx` files — the optional catch-all handles the bare hub path.

Keep hub `layout.tsx` generation — the `HubTabNav` layout wraps the catch-all and must remain.

- [ ] **Step 3: Delete all old mounted files**

```bash
cd apps/dashboard

# Delete all auto-generated page/loading/layout/error files in hub dirs
# (preserving hub layout.tsx and catch-all dirs)
for hub in brain career command life studio adaptive hidden; do
  find "app/$hub" -name 'page.tsx' -not -path '*/\[\[...slug\]\]/*' -exec grep -l 'AUTO-GENERATED' {} \; -exec rm {} \;
  find "app/$hub" -name 'loading.tsx' -exec grep -l 'AUTO-GENERATED' {} \; -exec rm {} \;
  find "app/$hub" -name 'error.tsx' -exec grep -l 'AUTO-GENERATED' {} \; -exec rm {} \;
  # Delete sub-route layouts (NOT hub-level layout.tsx)
  find "app/$hub" -mindepth 2 -name 'layout.tsx' -exec grep -l 'AUTO-GENERATED' {} \; -exec rm {} \;
  # Delete hub landing page (replaced by catch-all)
  rm -f "app/$hub/page.tsx"
done

# Clean up empty directories
find app -type d -empty -delete
```

- [ ] **Step 4: Rebuild and verify**

```bash
node scripts/build-scripts.mjs
node scripts/dist/mount-plugins.mjs
node scripts/dist/generate-tab-registry.mjs
```

Verify:
- No build errors
- Registry files generated for all 6 hubs
- Tab registry generates without orphan errors

- [ ] **Step 5: Browser verification**

Navigate to these URLs and verify each works:
- `http://localhost:3000/brain` → redirects to `/brain/knowledge/memory`
- `http://localhost:3000/brain/ai_bridge/agents` → renders agents page
- `http://localhost:3000/career` → redirects to career default tab
- `http://localhost:3000/command` → redirects to command default tab
- Tab bar navigation works across all hubs
- Back button works
- Deep linking works (paste URL directly into browser)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: switch to catch-all routes — 140 mounted pages replaced by 6 hub registries"
```

---

### Task 5: Simplify the Watcher

**Files:**
- Modify: `apps/dashboard/scripts/mount-plugins.ts` (watcher section)

The watcher currently re-copies files on any change. It now only needs to regenerate registries on page add/delete.

- [ ] **Step 1: Update watcher to regenerate registries only**

In the `startWatchMode()` function (~lines 677-850), the rebuild trigger calls `main()` which re-runs the full pipeline. This is still correct — `main()` now generates registries instead of copying files. The simplification is that the watcher no longer needs to watch for content changes in page.tsx files — only structural changes (new/deleted files).

However, since `main()` is idempotent and fast (generating 6 small registry files), the current full-rebuild-on-any-change approach is acceptable. The debounce at 500ms prevents thrashing.

If the watcher is already working correctly with the registry generation from Task 4, no code change is needed here. Verify by:
1. Adding a new page.tsx to a plugin source directory
2. Confirming the watcher regenerates the registry
3. Navigating to the new page in the browser

- [ ] **Step 2: Commit (if changes made)**

```bash
git add apps/dashboard/scripts/mount-plugins.ts
git commit -m "refactor: simplify watcher to registry-only regeneration"
```

---

## Phase 2: Split Oversized Pages

Each task extracts sections from a monolith page into focused sub-pages at the plugin source level. The catch-all registry picks them up automatically on next mount-plugins run.

### Task 6: Split reading-list (1019 lines → 4 sub-pages)

**Files:**
- Read: `plugins/ui/pages/brain/reading-list/page.tsx`
- Create: `plugins/ui/pages/brain/reading-list/articles/page.tsx`
- Create: `plugins/ui/pages/brain/reading-list/books/page.tsx`
- Create: `plugins/ui/pages/brain/reading-list/notes/page.tsx`
- Create: `plugins/ui/pages/brain/reading-list/import/page.tsx`
- Delete: `plugins/ui/pages/brain/reading-list/page.tsx`

- [ ] **Step 1: Read the source and identify section boundaries**

Read `plugins/ui/pages/brain/reading-list/page.tsx`. Identify the 4 sections by their component functions and line ranges:
- ReadingListSection (articles)
- BooksCatalogSection (books)
- BookNotesSection (notes)
- OcrImportSection (import/OCR)

- [ ] **Step 2: Extract articles section**

Create `plugins/ui/pages/brain/reading-list/articles/page.tsx` containing only the ReadingListSection component and its dependencies (imports, types, sub-components). The component becomes the default export.

- [ ] **Step 3: Extract books section**

Create `plugins/ui/pages/brain/reading-list/books/page.tsx` containing only the BooksCatalogSection.

- [ ] **Step 4: Extract notes section**

Create `plugins/ui/pages/brain/reading-list/notes/page.tsx` containing only the BookNotesSection.

- [ ] **Step 5: Extract import/OCR section**

Create `plugins/ui/pages/brain/reading-list/import/page.tsx` containing only the OcrImportSection.

- [ ] **Step 6: Delete the monolith and update tab config**

Delete `plugins/ui/pages/brain/reading-list/page.tsx`. Update the plugin's SKILL.md or tab config to point to the sub-pages instead of the monolith. Run mount-plugins to regenerate registries.

- [ ] **Step 7: Verify in browser**

Navigate to each sub-page and verify it renders correctly. Check tab bar shows the new sub-tabs.

- [ ] **Step 8: Commit**

```bash
git add plugins/ui/pages/brain/reading-list/
git commit -m "refactor: split reading-list into 4 focused sub-pages (articles, books, notes, import)"
```

---

### Task 7: Split learning (918 lines → 5 sub-pages)

**Files:**
- Read: `plugins/ui/pages/career/learning/page.tsx`
- Create: `plugins/ui/pages/career/learning/courses/page.tsx`
- Create: `plugins/ui/pages/career/learning/knowledge/page.tsx`
- Create: `plugins/ui/pages/career/learning/guard/page.tsx`
- Create: `plugins/ui/pages/career/learning/habits/page.tsx`
- Create: `plugins/ui/pages/career/learning/hardening/page.tsx`
- Delete: `plugins/ui/pages/career/learning/page.tsx`

Follow the same pattern as Task 6:

- [ ] **Step 1:** Read source and identify section boundaries (Courses, Knowledge Domains, Retention Guard, Habits, Hardening Reports)
- [ ] **Step 2:** Extract courses section
- [ ] **Step 3:** Extract knowledge section
- [ ] **Step 4:** Extract guard/retention section
- [ ] **Step 5:** Extract habits section
- [ ] **Step 6:** Extract hardening section
- [ ] **Step 7:** Delete monolith, update tab config, regenerate registries
- [ ] **Step 8:** Verify in browser
- [ ] **Step 9:** Commit

```bash
git commit -m "refactor: split learning into 5 focused sub-pages (courses, knowledge, guard, habits, report)"
```

---

### Task 8: Split ai_bridge (1529 lines → 3 sub-pages)

**Files:**
- Read: `plugins/ui/pages/brain/ai_bridge/page.tsx`
- Create: `plugins/ui/pages/brain/ai_bridge/providers/page.tsx`
- Create: `plugins/ui/pages/brain/ai_bridge/sync/page.tsx`
- Delete: `plugins/ui/pages/brain/ai_bridge/page.tsx`

Note: `ai_bridge/agents/page.tsx` already exists (improved earlier this session).

- [ ] **Step 1:** Read source and identify sections (Agent Registry ~already extracted, Providers & Usage, Skill Sync)
- [ ] **Step 2:** Extract providers section (provider cards, config modal, budget widget, usage stats)
- [ ] **Step 3:** Extract sync section (skill inventory, sync status, client status)
- [ ] **Step 4:** Delete monolith, update tab config, regenerate registries
- [ ] **Step 5:** Verify in browser — all 3 sub-tabs render correctly
- [ ] **Step 6:** Commit

```bash
git commit -m "refactor: split ai_bridge into 3 sub-pages (agents, providers, sync)"
```

---

### Task 9: Split workbench (950 lines → 2 sub-pages + reduced parent)

**Files:**
- Read: `plugins/ui/pages/studio/workbench/page.tsx`
- Create: `plugins/ui/pages/studio/workbench/tools/page.tsx`
- Create: `plugins/ui/pages/studio/workbench/audit/page.tsx`
- Modify: `plugins/ui/pages/studio/workbench/page.tsx` (reduce to ~400 lines — advisor section stays)

- [ ] **Step 1:** Read source and identify sections (Advisor Analytics, Developer Tools, Capability Migration Audit)
- [ ] **Step 2:** Extract tools section (migration, simplification, refactor forms)
- [ ] **Step 3:** Extract audit section (findings grid, parity table, risk assessment)
- [ ] **Step 4:** Reduce parent page to advisor analytics only (~400 lines). Rename if needed.
- [ ] **Step 5:** Update tab config, regenerate registries
- [ ] **Step 6:** Verify in browser
- [ ] **Step 7:** Commit

```bash
git commit -m "refactor: split workbench — extract tools and audit into sub-pages"
```

---

### Task 10: Extract daemon/self-heal (1092 → extract 240 lines)

**Files:**
- Read: `plugins/ui/pages/command/daemon/page.tsx`
- Create: `plugins/ui/pages/command/daemon/self-heal/page.tsx`
- Modify: `plugins/ui/pages/command/daemon/page.tsx` (remove self-heal section)

- [ ] **Step 1:** Read source and identify self-heal section (EventCard, severity badges, fix tracking, ~lines 491-730)
- [ ] **Step 2:** Extract self-heal section into its own page
- [ ] **Step 3:** Remove section from daemon parent page
- [ ] **Step 4:** Update tab config, regenerate registries
- [ ] **Step 5:** Verify in browser
- [ ] **Step 6:** Commit

```bash
git commit -m "refactor: extract self-heal log from daemon page into dedicated sub-page"
```

---

## Phase 3: Cleanup & Verification

### Task 11: Final Cleanup and Verification

**Files:**
- Modify: `apps/dashboard/next.config.ts` — add hub landing rewrites to eliminate client-side redirect flash
- Clean: Remove any remaining empty directories in `app/` hub subdirectories

- [ ] **Step 1: Add hub landing rewrites to next.config.ts**

In the `rewrites()` section, add entries for each hub to eliminate the client-side redirect flash:

```typescript
{ source: '/brain', destination: '/brain/knowledge/memory' },
{ source: '/career', destination: '/career/pipeline' },
{ source: '/command', destination: '/command/daemon' },
{ source: '/life', destination: '/life/home-automation' },
{ source: '/studio', destination: '/studio/workbench' },
{ source: '/adaptive', destination: '/adaptive/auto-skill-quality' },
{ source: '/hidden', destination: '/hidden/...' }, // check actual default
```

Read the existing hub landing pages to get the correct default paths for each hub. Audit existing rewrites (lines 135-143 of next.config.ts) for overlap with the catch-all — particularly `/command/observe` → `/command/daemon` which maps to a hub sub-path.

- [ ] **Step 2: Clean empty directories**

```bash
find apps/dashboard/app -type d -empty -delete
```

- [ ] **Step 3: Run full build verification**

```bash
cd apps/dashboard
node scripts/build-scripts.mjs
node scripts/dist/mount-plugins.mjs
node scripts/dist/generate-tab-registry.mjs
pnpm exec tsc --noEmit
```

All must pass with zero errors.

- [ ] **Step 4: Browser smoke test**

Test these scenarios:
- Navigate to each hub landing URL — verify redirect works
- Navigate to 3-4 pages per hub — verify content renders
- Use tab bar to switch between pages — verify navigation
- Use browser back button — verify history works
- Paste a deep link directly — verify it resolves
- Check dev server RSS in Activity Monitor — should be under 1.5 GB after visiting ~10 pages

- [ ] **Step 5: Verify start-dev.sh heap limit is 4 GB**

Confirm `apps/dashboard/scripts/start-dev.sh` has `--max-old-space-size=4096` (changed from 8192 earlier this session). If not, update it.

- [ ] **Step 6: Verify no page exceeds 400 lines**

```bash
find plugins/ui/pages -name 'page.tsx' -exec wc -l {} \; | sort -rn | head -10
```

All should be under ~400 lines.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup — hub rewrites, empty dir removal, verification"
```

---

## Summary

| Phase | Tasks | What it achieves |
|-------|-------|-----------------|
| Phase 1 (Tasks 1-5) | Catch-all infrastructure | 140 routes → ~25. Immediate memory fix. |
| Phase 2 (Tasks 6-10) | Page splits | Top 5 monoliths decomposed. Per-visit compile cost drops ~70%. |
| Phase 3 (Task 11) | Cleanup | Polish, verification, rewrites for flash elimination. |

**Total estimated effort:** Tasks 1-5 are the critical path (~60% of work). Tasks 6-10 are independent and can be parallelized. Task 11 is polish.
