# Augur App Page Staging Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flatten Brain memory into direct app pages, remove nested Brain tabs, and move Dev/Life leftover page surfaces into staged release payloads while keeping needed backend skills live.

**Architecture:** Active dashboard pages remain under `apps/dashboard/features/pages/{hub}/` or skill-local `skills/{skill}/augur/pages/`. Deferred page surfaces move under `staging/{release}/pages/` using repo-relative paths so `/port-release` can copy them back later. Backend skills stay in `skills/` unless this plan explicitly moves only their dashboard page source.

**Tech Stack:** Next.js dashboard, TypeScript route discovery, YAML page wrappers, skill `SKILL.md` frontmatter, Python staged release tooling, Jest, Playwright.

---

## File Structure

Create:
- `apps/dashboard/features/pages/brain/search/page.tsx` - standalone memory search page.
- `tests/dashboard/visual/app-page-staging.spec.ts` - browser-level route and nav assertions.

Modify:
- `tests/unit/test_staged_skill_catalog.py` - live feature page roots match the flattened MVP surface.
- `tests/dashboard/lib/generate-tab-registry.test.ts` - generated tabs expose flattened Brain pages and no staged leftovers.
- `tests/dashboard/lib/navigation-hidden-hub.test.ts` - Dev and Life are hidden from primary sidebar navigation.
- `apps/dashboard/features/pages/brain/memory/page.tsx` - remove inner section nav and point cards at top-level Brain routes.
- `apps/dashboard/features/pages/brain/daily-logs/page.tsx` - top-level route imports shared memory components.
- `apps/dashboard/features/pages/brain/profile/page.tsx` - top-level route imports shared memory components.
- `apps/dashboard/features/pages/brain/workspace/page.tsx` - top-level route imports shared memory components.
- `skills/knowledge/SKILL.md` - active Brain page declarations become `/brain/memory`, `/brain/search`, `/brain/daily-logs`, `/brain/profile`, `/brain/workspace`, and `/brain/ingest`.
- `skills/ai/SKILL.md` - remove active `/brain/ai` and `/brain/ai/agents` page declarations.
- `skills/rag/SKILL.md` - remove the active `/brain/rag` block expansion target from visible app nav.
- `skills/platform-admin/SKILL.md` - keep backend skill live, hide Dev hub nav, remove active Dev page declarations.
- `skills/auto-skill-quality/SKILL.md` - keep loop live, remove active `skill-scores` page contribution.
- `skills/file-manager/SKILL.md` - keep backend skill live, hide Life hub nav, remove active Life page declarations.
- `staging/r1/manifest.md` - record staged File Manager page artifacts.
- `staging/r3/manifest.md` - record staged Brain operator and Dev page artifacts.

Move:
- `apps/dashboard/features/pages/brain/knowledge/memory/` -> `apps/dashboard/features/pages/brain/memory/`.
- `apps/dashboard/features/pages/brain/memory/daily-logs/` -> `apps/dashboard/features/pages/brain/daily-logs/`.
- `apps/dashboard/features/pages/brain/memory/profile/` -> `apps/dashboard/features/pages/brain/profile/`.
- `apps/dashboard/features/pages/brain/memory/workspace/` -> `apps/dashboard/features/pages/brain/workspace/`.
- `apps/dashboard/features/pages/brain/ai/` -> `staging/r3/pages/apps/dashboard/features/pages/brain/ai/`.
- `apps/dashboard/features/pages/brain/harness/` -> `staging/r3/pages/apps/dashboard/features/pages/brain/harness/`.
- `apps/dashboard/features/pages/dev/skill-scores/` -> `staging/r3/pages/apps/dashboard/features/pages/dev/skill-scores/`.
- `apps/dashboard/features/pages/life/file-manager/` -> `staging/r1/pages/apps/dashboard/features/pages/life/file-manager/`.
- `skills/file-manager/augur/pages/browse.yaml` -> `staging/r1/pages/skills/file-manager/augur/pages/browse.yaml`.
- `skills/file-manager/augur/pages/organize.yaml` -> `staging/r1/pages/skills/file-manager/augur/pages/organize.yaml`.
- `tests/dashboard/features/pages/brain/harness-page.test.tsx` -> `staging/r3/pages/tests/dashboard/features/pages/brain/harness-page.test.tsx`.
- `tests/dashboard/features/pages/brain/ai/` -> `staging/r3/pages/tests/dashboard/features/pages/brain/ai/`.

Delete:
- `apps/dashboard/features/pages/brain/memory/components/MemorySectionNav.tsx`.
- `skills/loop-repo/augur/pages/vault-hygiene.yaml`.

Generated after source edits:
- `apps/dashboard/app/brain/[[...slug]]/registry.ts`
- `apps/dashboard/lib/configs/*.tsx`
- `apps/dashboard/lib/configs/*.json`
- `apps/dashboard/lib/tabs/generated-registry.ts`
- `apps/dashboard/lib/plugin-runtime/assembled-hubs.json`

### Task 1: Lock The Desired Live Surface In Tests

**Files:**
- Modify: `tests/unit/test_staged_skill_catalog.py`
- Modify: `tests/dashboard/lib/generate-tab-registry.test.ts`
- Modify: `tests/dashboard/lib/navigation-hidden-hub.test.ts`

- [ ] **Step 1: Update live feature root expectations**

Replace the expected list in `test_repo_live_feature_page_roots_match_mvp_surface` with this list:

```python
    assert live_page_roots == [
        "brain/daily-logs",
        "brain/memory",
        "brain/profile",
        "brain/search",
        "brain/workspace",
        "command/workflows",
        "settings/providers",
    ]
```

- [ ] **Step 2: Replace the harness tab test with flattened Brain assertions**

Replace `includes harness dashboard page in brain tabs` in `tests/dashboard/lib/generate-tab-registry.test.ts` with:

```ts
  it('exposes flattened Brain memory pages and no nested memory routes', () => {
    const brainTabs = [...registry.brain.tabs, ...(registry.brain.overflow || [])];
    const brainConfigPages = registry.brain.configPages || [];
    const brainAutoPages = registry.brain.autoPages || [];
    const serialized = JSON.stringify([...brainTabs, ...brainConfigPages, ...brainAutoPages]);

    for (const href of [
      '/brain/memory',
      '/brain/search',
      '/brain/daily-logs',
      '/brain/profile',
      '/brain/workspace',
    ]) {
      expect(serialized).toContain(`"href":"${href}"`);
    }

    for (const staleHref of [
      '/brain/knowledge',
      '/brain/knowledge/memory',
      '/brain/knowledge/memory/daily-logs',
      '/brain/knowledge/memory/profile',
      '/brain/knowledge/memory/workspace',
      '/brain/harness',
      '/brain/ai',
      '/brain/ai/agents',
      '/brain/rag',
    ]) {
      expect(serialized).not.toContain(`"href":"${staleHref}"`);
    }
  });
```

- [ ] **Step 3: Add Dev and Life generated-registry assertions**

Add this test below the Brain test:

```ts
  it('does not expose staged Dev and Life pages in generated page collections', () => {
    const serialized = JSON.stringify(registry);
    for (const stagedHref of [
      '/dev/auto-vault-hygiene',
      '/dev/auto-skill-quality',
      '/dev/platform-admin',
      '/dev/skill-scores',
      '/life/file-manager',
      '/life/file-manager/organize',
    ]) {
      expect(serialized).not.toContain(`"href":"${stagedHref}"`);
    }
  });
```

- [ ] **Step 4: Add sidebar hiding assertions**

Append this test to `tests/dashboard/lib/navigation-hidden-hub.test.ts`:

```ts
  it('Dev and Life hubs are excluded from primary navigation in development mode', () => {
    const { getEnabledSections } = require('../../../apps/dashboard/lib/navigation');
    const sections = getEnabledSections(true);
    const allItems = sections.flatMap((s: any) => s.items);

    expect(allItems.find((item: any) => item.href === '/dev')).toBeUndefined();
    expect(allItems.find((item: any) => item.href === '/life')).toBeUndefined();
  });
```

- [ ] **Step 5: Run tests and confirm the failure is meaningful**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/lib/generate-tab-registry.test.ts tests/dashboard/lib/navigation-hidden-hub.test.ts --runInBand
python3 -m pytest tests/unit/test_staged_skill_catalog.py -q
```

Expected:
- Jest fails because current generated registry still contains nested Brain routes and staged Dev/Life pages.
- Pytest fails because the live feature page roots still contain `brain/ai`, `brain/harness`, `brain/knowledge`, `dev/skill-scores`, and `life/file-manager`.

- [ ] **Step 6: Commit the failing tests**

```bash
git add tests/unit/test_staged_skill_catalog.py tests/dashboard/lib/generate-tab-registry.test.ts tests/dashboard/lib/navigation-hidden-hub.test.ts
git commit -m "test: lock app page staging expectations"
```

### Task 2: Flatten Brain Memory Pages

**Files:**
- Move: `apps/dashboard/features/pages/brain/knowledge/memory/`
- Create: `apps/dashboard/features/pages/brain/search/page.tsx`
- Delete: `apps/dashboard/features/pages/brain/memory/components/MemorySectionNav.tsx`

- [ ] **Step 1: Move Brain memory routes to top level**

Run:

```bash
git mv apps/dashboard/features/pages/brain/knowledge/memory apps/dashboard/features/pages/brain/memory
git mv apps/dashboard/features/pages/brain/memory/daily-logs apps/dashboard/features/pages/brain/daily-logs
git mv apps/dashboard/features/pages/brain/memory/profile apps/dashboard/features/pages/brain/profile
git mv apps/dashboard/features/pages/brain/memory/workspace apps/dashboard/features/pages/brain/workspace
```

Expected:
- `apps/dashboard/features/pages/brain/memory/page.tsx` exists.
- `apps/dashboard/features/pages/brain/daily-logs/page.tsx` exists.
- `apps/dashboard/features/pages/brain/profile/page.tsx` exists.
- `apps/dashboard/features/pages/brain/workspace/page.tsx` exists.

- [ ] **Step 2: Remove the inner memory nav**

Run:

```bash
git rm apps/dashboard/features/pages/brain/memory/components/MemorySectionNav.tsx
```

Edit `apps/dashboard/features/pages/brain/memory/page.tsx`:
- Remove `import { MemorySectionNav } from './components/MemorySectionNav';`.
- Remove the `<MemorySectionNav />` element.
- Change the card links to:

```tsx
href="/brain/workspace"
href="/brain/profile"
href="/brain/daily-logs"
```

- [ ] **Step 3: Fix imports in top-level child pages**

Use these import replacements:

```tsx
// apps/dashboard/features/pages/brain/daily-logs/page.tsx
import { Calendar } from 'lucide-react';
import { DeferredSection } from '../memory/components/DeferredSection';
import { DailyLogsSection } from '../memory/components/DailyLogsSection';
import { useMemoryDashboardData } from '../memory/hooks';
```

```tsx
// apps/dashboard/features/pages/brain/profile/page.tsx
import { User } from 'lucide-react';
import { DeferredSection } from '../memory/components/DeferredSection';
import { HumanApiProfileSection } from '../memory/components/HumanApiProfileSection';
import { useMemoryWorkspace } from '../memory/hooks';
```

```tsx
// apps/dashboard/features/pages/brain/workspace/page.tsx
import { usePathname } from 'next/navigation';
import { FolderOpen } from 'lucide-react';
import { useMemoryWorkspace, useMemoryReportAction } from '../memory/hooks';
import { MemoryWorkspacePanel } from '../memory/components/MemoryWorkspacePanel';
import { HumanReportPreview } from '../memory/components/HumanReportPreview';
```

Remove each `<MemorySectionNav />` element from the three pages.

- [ ] **Step 4: Create the standalone search page**

Create `apps/dashboard/features/pages/brain/search/page.tsx` with:

```tsx
'use client';

import { Search } from 'lucide-react';
import { useMemoryDashboardData, useMemorySearch } from '../memory/hooks';
import { MemorySearchWidget } from '../memory/components/MemorySearchWidget';

export default function BrainSearchPage() {
  const { categories } = useMemoryDashboardData();
  const searchHook = useMemorySearch();

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-3">
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-3">
          <Search className="h-5 w-5 text-emerald-400" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Memory Search</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Search decisions, patterns, preferences, and linked knowledge without opening a nested section.
          </p>
        </div>
      </header>

      <MemorySearchWidget
        searchQuery={searchHook.searchQuery}
        setSearchQuery={searchHook.setSearchQuery}
        isSearching={searchHook.isSearching}
        searchResults={searchHook.searchResults}
        hasSearched={searchHook.hasSearched}
        searchError={searchHook.searchError}
        onSearch={searchHook.handleSearch}
        categories={categories}
      />
    </div>
  );
}
```

- [ ] **Step 5: Remove stale route strings from Brain feature pages**

Run:

```bash
rg -n "MemorySectionNav|/brain/knowledge/memory|/brain/knowledge" apps/dashboard/features/pages/brain
```

Expected:
- No matches.

- [ ] **Step 6: Run focused type and feature tests**

Run:

```bash
pnpm --filter dashboard typecheck
python3 -m pytest tests/unit/test_staged_skill_catalog.py -q
```

Expected:
- TypeScript passes.
- `test_repo_live_feature_page_roots_match_mvp_surface` still fails until staged pages are moved in Task 3.

- [ ] **Step 7: Commit the Brain flattening**

```bash
git add apps/dashboard/features/pages/brain tests/unit/test_staged_skill_catalog.py
git commit -m "feat(brain): flatten memory pages"
```

### Task 3: Stage Dev, Life, And Operator Page Surfaces

**Files:**
- Move TSX page surfaces into `staging/r1/pages/` and `staging/r3/pages/`.
- Move File Manager YAML pages into `staging/r1/pages/skills/file-manager/augur/pages/`.
- Delete `skills/loop-repo/augur/pages/vault-hygiene.yaml`.
- Modify `staging/r1/manifest.md`.
- Modify `staging/r3/manifest.md`.

- [ ] **Step 1: Move Brain operator and Dev TSX pages to r3**

Run:

```bash
mkdir -p staging/r3/pages/apps/dashboard/features/pages/brain
mkdir -p staging/r3/pages/apps/dashboard/features/pages/dev
mkdir -p staging/r3/pages/tests/dashboard/features/pages/brain
git mv apps/dashboard/features/pages/brain/ai staging/r3/pages/apps/dashboard/features/pages/brain/ai
git mv apps/dashboard/features/pages/brain/harness staging/r3/pages/apps/dashboard/features/pages/brain/harness
git mv apps/dashboard/features/pages/dev/skill-scores staging/r3/pages/apps/dashboard/features/pages/dev/skill-scores
git mv tests/dashboard/features/pages/brain/ai staging/r3/pages/tests/dashboard/features/pages/brain/ai
git mv tests/dashboard/features/pages/brain/harness-page.test.tsx staging/r3/pages/tests/dashboard/features/pages/brain/harness-page.test.tsx
```

- [ ] **Step 2: Move Life page surfaces to r1**

Run:

```bash
mkdir -p staging/r1/pages/apps/dashboard/features/pages/life
mkdir -p staging/r1/pages/skills/file-manager/augur/pages
git mv apps/dashboard/features/pages/life/file-manager staging/r1/pages/apps/dashboard/features/pages/life/file-manager
git mv skills/file-manager/augur/pages/browse.yaml staging/r1/pages/skills/file-manager/augur/pages/browse.yaml
git mv skills/file-manager/augur/pages/organize.yaml staging/r1/pages/skills/file-manager/augur/pages/organize.yaml
```

- [ ] **Step 3: Delete the superseded Dev YAML page**

Run:

```bash
git rm skills/loop-repo/augur/pages/vault-hygiene.yaml
```

- [ ] **Step 4: Update r1 manifest pages**

Replace `pages: []` in `staging/r1/manifest.md` with:

```yaml
pages:
- apps/dashboard/features/pages/life/file-manager/page.tsx
- apps/dashboard/features/pages/life/file-manager/tsconfig.json
- skills/file-manager/augur/pages/browse.yaml
- skills/file-manager/augur/pages/organize.yaml
```

- [ ] **Step 5: Update r3 manifest pages**

Replace `pages: []` in `staging/r3/manifest.md` with:

```yaml
pages:
- apps/dashboard/features/pages/brain/ai/agents/control-state.test.ts
- apps/dashboard/features/pages/brain/ai/agents/control-state.ts
- apps/dashboard/features/pages/brain/ai/agents/page.tsx
- apps/dashboard/features/pages/brain/ai/memory/GraphStats.tsx
- apps/dashboard/features/pages/brain/ai/memory/LinkedFolders.tsx
- apps/dashboard/features/pages/brain/ai/memory/RagProjects.tsx
- apps/dashboard/features/pages/brain/ai/memory/RagSearch.tsx
- apps/dashboard/features/pages/brain/ai/memory/RagSettings.tsx
- apps/dashboard/features/pages/brain/ai/memory/ReasoningSearch.tsx
- apps/dashboard/features/pages/brain/ai/memory/RelationshipQuery.tsx
- apps/dashboard/features/pages/brain/ai/schedules/components.tsx
- apps/dashboard/features/pages/brain/ai/tsconfig.json
- apps/dashboard/features/pages/brain/harness/page.tsx
- apps/dashboard/features/pages/dev/skill-scores/SkillGateVisualizer.tsx
- apps/dashboard/features/pages/dev/skill-scores/page.tsx
- apps/dashboard/features/pages/dev/skill-scores/types.ts
- tests/dashboard/features/pages/brain/ai/agents/control-state.test.ts
- tests/dashboard/features/pages/brain/harness-page.test.tsx
```

- [ ] **Step 6: Validate staged payload layout**

Run:

```bash
python3 scripts/manage_porting_payload.py validate-release --release-root staging/r1
python3 scripts/manage_porting_payload.py validate-release --release-root staging/r3
python3 -m pytest tests/scripts/test_manage_porting_payload.py tests/scripts/test_port_release_into_main.py -q
python3 -m pytest tests/unit/test_staged_skill_catalog.py -q
```

Expected:
- Both `validate-release` calls print `ok`.
- Porting payload tests pass.
- Staged skill catalog test passes after all active page roots match the new list.

- [ ] **Step 7: Commit staged page moves**

```bash
git add -A apps/dashboard/features/pages staging skills/file-manager skills/loop-repo/augur/pages tests/dashboard/features/pages tests/unit/test_staged_skill_catalog.py
git commit -m "chore(staging): move deferred app pages"
```

### Task 4: Remove Active Page Declarations And Regenerate Dashboard Surfaces

**Files:**
- Modify: `skills/knowledge/SKILL.md`
- Modify: `skills/ai/SKILL.md`
- Modify: `skills/rag/SKILL.md`
- Modify: `skills/platform-admin/SKILL.md`
- Modify: `skills/auto-skill-quality/SKILL.md`
- Modify: `skills/file-manager/SKILL.md`
- Regenerate generated dashboard files.

- [ ] **Step 1: Update Knowledge page declarations**

In `skills/knowledge/SKILL.md`, replace:

```yaml
x-augur-dashboard-pages:
- /brain/knowledge
- /brain/knowledge/memory
- /brain/harness
```

with:

```yaml
x-augur-dashboard-pages:
- /brain/memory
- /brain/search
- /brain/daily-logs
- /brain/profile
- /brain/workspace
- /brain/ingest
```

In `x-augur-config.contributions.pages`, remove the `knowledge` and `harness` page entries. Add these page entries:

```yaml
    - id: memory
      title: Memory
      icon: Brain
      order: 10
      purpose: Review decisions, patterns, preferences, curation, and wiki maintenance.
      keywords: [memory, decisions, patterns, preferences]
    - id: search
      title: Search
      icon: Search
      order: 11
      purpose: Search memory and linked knowledge from a dedicated page.
      keywords: [search, memory, knowledge]
    - id: daily-logs
      title: Daily Logs
      icon: Calendar
      order: 12
      purpose: Browse daily memory logs directly from the Brain app.
      keywords: [daily, logs, memory]
    - id: profile
      title: Profile
      icon: User
      order: 13
      purpose: Review and regenerate the human API profile.
      keywords: [profile, human-api, memory]
    - id: workspace
      title: Workspace
      icon: FolderOpen
      order: 14
      purpose: Open canonical memory files and the generated knowledge report.
      keywords: [workspace, report, files]
```

Also change block expansion targets:

```yaml
expandTo: /brain/memory
```

for the `index` and `memory` blocks.

- [ ] **Step 2: Remove AI active Brain page declarations**

In `skills/ai/SKILL.md`, replace:

```yaml
x-augur-dashboard-pages:
- /brain/ai
- /brain/ai/agents
```

with:

```yaml
x-augur-dashboard-pages: []
```

Remove the `ai` entry from `x-augur-config.contributions.pages`. Keep AI commands, MCP tools, and agent metadata in the skill.

- [ ] **Step 3: Remove RAG visible app expansion**

In `skills/rag/SKILL.md`, change the `rag` block from:

```yaml
      expandTo: /brain/rag
```

to:

```yaml
      expandTo: /brain/search
```

- [ ] **Step 4: Hide Dev hub and remove active Dev page declarations**

In `skills/platform-admin/SKILL.md`, replace:

```yaml
x-augur-dashboard-pages:
- /dev/overview
- /dev/refactor
```

with:

```yaml
x-augur-dashboard-pages: []
```

Add this skill-local hub config before `x-augur-config-file`:

```yaml
x-augur-config:
  hub:
    id: dev
    owner: true
    title: Dev
    subtitle: Developer tools and system internals
    icon: Wrench
    category: dev
    nav_hidden: true
```

- [ ] **Step 5: Remove Skill Scores active page contribution**

In `skills/auto-skill-quality/SKILL.md`, remove this page contribution:

```yaml
    pages:
    - id: skill-scores
      title: Skill Scores
      icon: BarChart3
      page_type: custom
```

Leave the `commands` and loop metadata unchanged.

- [ ] **Step 6: Hide Life hub and remove active File Manager page declarations**

In `skills/file-manager/SKILL.md`, replace:

```yaml
x-augur-dashboard-pages:
- /life/file-manager
- /life/file-manager/organize
```

with:

```yaml
x-augur-dashboard-pages: []
```

Add this skill-local hub config before `x-augur-file-intake`:

```yaml
x-augur-config:
  hub:
    id: life
    owner: true
    title: Life
    subtitle: Personal operating system surfaces
    icon: Home
    category: personal
    nav_hidden: true
```

- [ ] **Step 7: Regenerate dashboard mount and tab surfaces**

Run:

```bash
pnpm --filter dashboard run build:scripts
pnpm --filter dashboard run mount-plugins
pnpm --filter dashboard run generate-tabs
```

Expected:
- `mount-plugins` completes without orphan route errors.
- `generate-tabs` completes and writes `apps/dashboard/lib/tabs/generated-registry.ts`.
- `apps/dashboard/app/brain/[[...slug]]/registry.ts` maps `memory`, `search`, `daily-logs`, `profile`, and `workspace`.

- [ ] **Step 8: Check for stale route strings**

Run:

```bash
rg -n "/brain/knowledge|/brain/ai|/brain/harness|/brain/rag|/dev/auto-vault-hygiene|/dev/auto-skill-quality|/dev/platform-admin|/dev/skill-scores|/life/file-manager" apps/dashboard skills/knowledge/SKILL.md skills/ai/SKILL.md skills/rag/SKILL.md skills/platform-admin/SKILL.md skills/auto-skill-quality/SKILL.md skills/file-manager/SKILL.md
```

Expected:
- No matches in `apps/dashboard`.
- Matches under `staging/` are allowed by the command exclusion because this command does not scan `staging/`.

- [ ] **Step 9: Run focused registry tests**

Run:

```bash
pnpm --filter dashboard test -- tests/dashboard/lib/generate-tab-registry.test.ts tests/dashboard/lib/navigation-hidden-hub.test.ts tests/dashboard/lib/page-discovery.test.ts --runInBand
python3 -m pytest tests/unit/test_staged_skill_catalog.py tests/scripts/test_manage_porting_payload.py tests/scripts/test_port_release_into_main.py -q
```

Expected:
- All listed tests pass.

- [ ] **Step 10: Commit declaration and generated surface changes**

```bash
git add skills apps/dashboard tests staging
git commit -m "chore(dashboard): regenerate app page staging surface"
```

### Task 5: Browser Verification And Final Gates

**Files:**
- Create: `tests/dashboard/visual/app-page-staging.spec.ts`

- [ ] **Step 1: Add Playwright verification spec**

Create `tests/dashboard/visual/app-page-staging.spec.ts` with:

```ts
import { test, expect } from '@playwright/test';

test.describe('app page staging cleanup', () => {
  test('Brain exposes flattened memory pages and no nested memory tabs', async ({ page }) => {
    await page.goto('/brain', { waitUntil: 'networkidle' });

    for (const href of [
      '/brain/memory',
      '/brain/search',
      '/brain/daily-logs',
      '/brain/profile',
      '/brain/workspace',
    ]) {
      await expect(page.locator(`a[href="${href}"]`).first()).toBeVisible();
    }

    for (const staleHref of [
      '/brain/knowledge',
      '/brain/knowledge/memory',
      '/brain/harness',
      '/brain/ai',
      '/brain/rag',
    ]) {
      await expect(page.locator(`a[href="${staleHref}"]`)).toHaveCount(0);
    }
  });

  test('Memory pages render meaningful live sections', async ({ page }) => {
    await page.goto('/brain/memory', { waitUntil: 'networkidle' });
    await expect(page.getByRole('heading', { name: 'Session Memory' })).toBeVisible();
    await expect(page.getByText(/Decisions, patterns, and preferences/i)).toBeVisible();

    await page.goto('/brain/search', { waitUntil: 'networkidle' });
    await expect(page.getByRole('heading', { name: 'Memory Search' })).toBeVisible();
    await expect(page.getByRole('textbox')).toBeVisible();
  });

  test('Dev and Life are hidden from primary navigation', async ({ page }) => {
    await page.goto('/brain', { waitUntil: 'networkidle' });
    await expect(page.locator('nav a[href="/dev"]')).toHaveCount(0);
    await expect(page.locator('nav a[href="/life"]')).toHaveCount(0);
  });
});
```

- [ ] **Step 2: Run dashboard build through the repo gate**

Run this slash command, not a direct `npm run build`:

```text
/dev-build --pages /brain,/brain/memory,/brain/search,/brain/daily-logs,/brain/profile,/brain/workspace,/dev,/life
```

Expected:
- Dashboard build completes.
- The dev server is refreshed through the lifecycle gate.
- `/brain` and the flattened Brain pages return 200.
- `/dev` and `/life` no longer appear in primary sidebar navigation.

- [ ] **Step 3: Run browser verification**

Run:

```bash
pnpm --filter dashboard exec playwright test tests/dashboard/visual/app-page-staging.spec.ts --project=chromium
```

Expected:
- All three Playwright tests pass.
- The run opens the verified dashboard server and checks visible page content, not only HTTP responses.

- [ ] **Step 4: Run final source checks**

Run:

```bash
pnpm --filter dashboard typecheck
pnpm --filter dashboard test -- tests/dashboard/lib/generate-tab-registry.test.ts tests/dashboard/lib/navigation-hidden-hub.test.ts tests/dashboard/lib/page-discovery.test.ts --runInBand
python3 -m pytest tests/unit/test_staged_skill_catalog.py tests/scripts/test_manage_porting_payload.py tests/scripts/test_port_release_into_main.py -q
git diff --check
git status --short
```

Expected:
- TypeScript passes.
- Jest passes.
- Pytest passes.
- `git diff --check` prints no whitespace errors.
- `git status --short` shows only intentional changed files before the final commit.

- [ ] **Step 5: Commit browser verification**

```bash
git add tests/dashboard/visual/app-page-staging.spec.ts
git commit -m "test(dashboard): verify app page staging cleanup"
```

- [ ] **Step 6: Final report**

Report:
- The exact commits created.
- Brain routes verified: `/brain`, `/brain/memory`, `/brain/search`, `/brain/daily-logs`, `/brain/profile`, `/brain/workspace`.
- Staged r1 paths verified under `staging/r1/pages/`.
- Staged r3 paths verified under `staging/r3/pages/`.
- Any residual direct links to `/dev` or `/life` outside primary nav.
