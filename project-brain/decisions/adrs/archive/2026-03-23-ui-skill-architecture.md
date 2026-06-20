# UI Skill Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all dashboard UI into `skills/dashboard/`, merge 3 skills, fix broken custom pages, and eliminate root workspace boilerplate.

**Deferred:** Spec step 1 (git recovery of 344 deleted files from `dist/plugins/`) is deferred — see Follow-Up Tasks item 2. This plan starts at spec step 2 (scaffold). Spec step 9 (API route audit) is included as Task 8b.

**Architecture:** A single UI skill (`skills/dashboard/`) owns all authored dashboard content — custom pages, shared components, autopage framework, and block renderers. `apps/dashboard/` becomes a thin Next.js shell with generated routes, build scripts, and node_modules. TypeScript path aliases resolve `@/` to `skills/dashboard/`. The mount system discovers pages from `skills/dashboard/pages/` cross-referenced against installed skills' SKILL.md declarations.

**Tech Stack:** Next.js 16, React 19, TypeScript, pnpm, Turbopack

**Spec:** `docs/superpowers/specs/2026-03-23-ui-skill-architecture-design.md`

---

## File Structure

### New files
- `skills/dashboard/SKILL.md` — Merged metadata from UI + mcp-app-factory + frontend + page-builder
- `skills/dashboard/pages/{hub}/{page}/page.tsx` — Moved from `apps/dashboard/lib/plugin-pages/`
- `skills/dashboard/framework/` — Placeholder for future autopage/browse/page-builder moves (out of scope for this plan, tracked as follow-up)
- `skills/dashboard/components/` — Placeholder (follow-up)
- `skills/dashboard/lib/` — Placeholder (follow-up)
- `skills/dashboard/scripts/` — MCP tool scripts from mcp-app-factory

### Modified files
- `apps/dashboard/tsconfig.json` — baseUrl, paths, include
- `apps/dashboard/next.config.ts:4-5,17-18` — Remove workspace root references
- `apps/dashboard/scripts/mount-plugins.ts:335-355,370-416,697-721` — Hub exemption, page source path, watch mode
- `apps/dashboard/scripts/mount/generate-registry.ts:114-205,222-256,258-274` — Remove manifest functions, update paths
- `apps/dashboard/package.json` — Add pnpm overrides from root

### Deleted files
- Root `package.json`
- Root `pnpm-workspace.yaml`
- `skills/mcp-app-factory/` (absorbed into skills/dashboard/)
- `skills/frontend/` (absorbed into skills/dashboard/)
- `skills/page-builder/` (absorbed into skills/dashboard/)
- `apps/dashboard/lib/plugin-pages/` (moved to skills/dashboard/pages/)

---

## Task 1: Scaffold skills/dashboard/ with merged SKILL.md

**Files:**
- Create: `skills/dashboard/SKILL.md`
- Create: `skills/dashboard/pages/.gitkeep` (temporary, replaced in Task 2)
- Create: `skills/dashboard/scripts/.gitkeep` (populated in Task 6)
- Read: `skills/mcp-app-factory/SKILL.md`, `skills/frontend/SKILL.md`, `skills/page-builder/SKILL.md`

- [ ] **Step 1: Read the three source SKILL.md files**

Read frontmatter from all three skills to extract:
- `x-augur-mcp-tools` lists
- `x-augur-dashboard-pages` arrays
- `x-augur-config.contributions` (blocks, actions)
- `x-augur-dependencies`

- [ ] **Step 2: Create skills/dashboard/ directory**

```bash
mkdir -p skills/dashboard/{pages,framework,components,lib,scripts}
```

- [ ] **Step 3: Write merged SKILL.md**

Create `skills/dashboard/SKILL.md` with combined frontmatter:

```yaml
---
name: dashboard
x-augur-type: domain
x-augur-hub: system
x-augur-tab: dashboard
x-augur-master: claude-code
version: 1.0.0
description: >
  Central UI skill — owns all dashboard custom pages, shared components,
  autopage framework, block renderers, and plugin factory tooling.
  Merges: mcp-app-factory, frontend, page-builder.
x-augur-mcp-tools:
  # IMPORTANT: Copy tool lists VERBATIM from each source SKILL.md.
  # Do NOT use this pre-drafted list — it is approximate.
  # Read: skills/mcp-app-factory/SKILL.md, skills/frontend/SKILL.md,
  #        skills/page-builder/SKILL.md
  # Merge all x-augur-mcp-tools arrays into this one.
x-augur-dashboard-pages:
  # From frontend
  - /dev/audit
  # From page-builder
  - /admin/overview
  - /admin/builder
  # All custom pages are declared by their owning skills, not here
x-augur-dependencies:
  - knowledge
  - developer
x-augur-config:
  contributions:
    blocks:
      - id: page-builder
        type: action-bar
        title: Page Builder
        icon: LayoutDashboard
        config_schema: {}
        data_source:
          mcp_tool: get-focused-tools
    actions:
      - id: create-plugin
        dispatch: ide
      - id: audit-plugin
        dispatch: oneshot
      - id: migrate-skill
        dispatch: ide
      - id: import-skill
        dispatch: ide
      - id: verify-mounts
        mcp_tool: verify-plugin-mounts
        endpoint: /api/dev/verify-mounts
---

# Dashboard UI Skill

Central UI skill for the Augur dashboard. Owns all custom pages, shared
components, autopage framework, block renderers, and plugin factory tooling.

## Merged From
- `mcp-app-factory` — Plugin creation, audit, migration, import
- `frontend` — Design system audit, component discovery
- `page-builder` — Visual page composition, template rendering
```

- [ ] **Step 4: Commit scaffold**

```bash
git add skills/dashboard/
git commit -m "feat(dashboard): scaffold skills/dashboard/ with merged SKILL.md"
```

---

## Task 2: Move custom pages to skills/dashboard/pages/

**Files:**
- Move: `apps/dashboard/lib/plugin-pages/*` → `skills/dashboard/pages/*`
- Modify: All moved `page.tsx` files (remove AUTO-GENERATED markers)

- [ ] **Step 1: Move all plugin pages**

```bash
# Move entire directory tree preserving structure
cp -R apps/dashboard/lib/plugin-pages/* skills/dashboard/pages/

# Remove old location
rm -rf apps/dashboard/lib/plugin-pages
```

- [ ] **Step 2: Remove AUTO-GENERATED markers from all moved files**

Find and remove the auto-generated comment block from every `.tsx` file. The marker looks like:

```typescript
/**
 * AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
 * Source: plugins/ui/pages/{hub}/{skill}/page.tsx
 * Generated by: mount-plugins
 */
```

```bash
# Preview which files have the marker
find skills/dashboard/pages -name "*.tsx" -exec grep -l "AUTO-GENERATED" {} \; | wc -l

# Strip the AUTO-GENERATED comment block (typically 4-5 lines at top of file)
find skills/dashboard/pages -name "*.tsx" -exec grep -l "AUTO-GENERATED" {} \; | \
  xargs perl -0777 -i -pe 's{/\*\*\s*\n\s*\*\s*AUTO-GENERATED.*?\*/\s*\n}{}gs'

# Verify removal
grep -rl "AUTO-GENERATED" skills/dashboard/pages/ && echo "FAIL: markers remain" || echo "OK: all markers removed"
```

- [ ] **Step 3: Identify the 12 SkillAutoPage wrapper stubs**

These are 3-line files that just wrap `<SkillAutoPage skillId="..." />`:

```bash
grep -rl "SkillAutoPage" skills/dashboard/pages/ | head -20
```

Review each match. Files that contain ONLY the SkillAutoPage wrapper (no custom UI) should be removed — the mount system will render autopages directly for those routes. Expected files:
- `skills/dashboard/pages/adaptive/kill-augur/page.tsx`
- `skills/dashboard/pages/life/channels/page.tsx`
- `skills/dashboard/pages/life/wealth/page.tsx`
- `skills/dashboard/pages/command/skillstore/page.tsx`
- `skills/dashboard/pages/command/evolve/page.tsx`
- `skills/dashboard/pages/career/interview-coach/page.tsx`
- `skills/dashboard/pages/brain/obsidian/page.tsx`
- `skills/dashboard/pages/brain/data-query/page.tsx`
- `skills/dashboard/pages/brain/books/page.tsx`
- `skills/dashboard/pages/brain/rag/page.tsx`
- `skills/dashboard/pages/career/venture-augur/strategy/page.tsx`
- `skills/dashboard/pages/studio/page-builder/builder/page.tsx`

- [ ] **Step 4: Remove the autopage wrapper stubs**

```bash
# Remove each confirmed wrapper (verify each before deleting)
rm skills/dashboard/pages/adaptive/kill-augur/page.tsx
# ... (repeat for each confirmed wrapper)
# Remove empty directories left behind
find skills/dashboard/pages -type d -empty -delete
```

- [ ] **Step 5: Commit page move**

```bash
git add skills/dashboard/pages/ apps/dashboard/lib/plugin-pages/
git commit -m "feat(dashboard): move custom pages to skills/dashboard/pages/

Move 328 files from apps/dashboard/lib/plugin-pages/ to skills/dashboard/pages/.
Remove AUTO-GENERATED markers. Remove 12 SkillAutoPage wrapper stubs."
```

---

## Task 3: Update TypeScript configuration

**Files:**
- Modify: `apps/dashboard/tsconfig.json`

- [ ] **Step 1: Update tsconfig.json**

Replace the full content of `apps/dashboard/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": false,
    "baseUrl": "../..",
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["skills/dashboard/*"]
    }
  },
  "include": [
    "next-env.d.ts",
    "../../skills/dashboard/**/*.ts",
    "../../skills/dashboard/**/*.tsx",
    "app/**/*.ts",
    "app/**/*.tsx",
    "scripts/**/*.ts",
    "scripts/**/*.mts",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts"
  ],
  "exclude": [
    "node_modules",
    ".next",
    "tests",
    "tests/**",
    "**/__tests__/**",
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/*.spec.ts",
    "**/*.spec.tsx"
  ]
}
```

Key changes from current:
- Added `"baseUrl": "../.."` (repo root)
- Changed `"@/*": ["./*"]` → `"@/*": ["skills/dashboard/*"]`
- Replaced `"**/*.ts"` catch-all with explicit `"../../skills/dashboard/**/*.ts{,x}"` + `"app/**/*.ts{,x}"` + `"scripts/**/*.ts"`

- [ ] **Step 2: Verify TypeScript resolves correctly**

```bash
cd apps/dashboard && npx tsc --noEmit --pretty 2>&1 | head -30
```

Expected: No errors from the alias change (existing code in `skills/dashboard/pages/` should resolve `@/components/*` etc. — though those still live in `apps/dashboard/` until the framework move, which is a follow-up). If there are errors, they indicate import paths that need rewriting in Task 4.

- [ ] **Step 3: Commit tsconfig change**

```bash
git add apps/dashboard/tsconfig.json
git commit -m "feat(dashboard): update tsconfig for skills/dashboard/ alias"
```

---

## Task 4: Rewrite import paths in moved pages

**Files:**
- Modify: All files in `skills/dashboard/pages/` that import from `@/lib/plugin-pages/`

- [ ] **Step 1: Find all internal cross-references**

Custom pages may import components from sibling pages using `@/lib/plugin-pages/` paths:

```bash
grep -r "@/lib/plugin-pages" skills/dashboard/pages/ | head -20
```

- [ ] **Step 2: Rewrite import paths**

Replace all occurrences:
- `@/lib/plugin-pages/{hub}/{skill}/` → `@/pages/{hub}/{skill}/`

```bash
# Preview the changes
grep -rl "@/lib/plugin-pages" skills/dashboard/pages/ | wc -l
```

Use find-and-replace across all files:
- Pattern: `@/lib/plugin-pages/`
- Replace: `@/pages/`

- [ ] **Step 3: Verify no broken imports remain**

```bash
# Check for any remaining references to the old path
grep -r "lib/plugin-pages" skills/dashboard/pages/
# Should return zero results

# Check for any other path issues
grep -r "plugins/ui" skills/dashboard/pages/
# Should return zero results
```

- [ ] **Step 4: Commit import rewrites**

```bash
git add skills/dashboard/pages/
git commit -m "fix(dashboard): rewrite import paths for new skills/dashboard/ location"
```

---

## Task 5: Update next.config.ts

**Files:**
- Modify: `apps/dashboard/next.config.ts:4-5,17-18`

- [ ] **Step 1: Update workspace root references**

In `apps/dashboard/next.config.ts`, change lines 4-5 and 17-18:

```typescript
// Line 4-5: Rename variable, update comment
// FROM:
// Monorepo root — needed for resolving workspace-hoisted dependencies
const workspaceRoot = path.resolve(__dirname, "../..");

// TO:
// Repository root — needed for Turbopack to resolve skills/dashboard/ imports
const repoRoot = path.resolve(__dirname, "../..");
```

```typescript
// Line 17-18: Remove outputFileTracingRoot
// FROM:
outputFileTracingRoot: workspaceRoot,

// TO:
// (remove this line entirely — no workspace hoisting)
```

```typescript
// Line 47: Update turbopack.root variable name
// FROM:
root: workspaceRoot,

// TO:
root: repoRoot,
```

Also update any other `workspaceRoot` references in the file to `repoRoot`.

- [ ] **Step 2: Verify next.config.ts is valid**

No pre-check needed — syntax validation happens at `pnpm run build` in Task 10. Just visually confirm the file has no obvious syntax issues.

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/next.config.ts
git commit -m "feat(dashboard): update next.config.ts for standalone layout"
```

---

## Task 6: Merge skills into skills/dashboard/

**Files:**
- Move: `skills/mcp-app-factory/scripts/` → `skills/dashboard/scripts/`
- Move: `skills/page-builder/augur/dashboard/` → `skills/dashboard/pages/` (template viewer)
- Delete: `skills/mcp-app-factory/`, `skills/frontend/`, `skills/page-builder/`

- [ ] **Step 1: Move mcp-app-factory scripts**

```bash
# Copy Python MCP tool scripts
cp -R skills/mcp-app-factory/scripts/* skills/dashboard/scripts/ 2>/dev/null || true

# Copy assets if they exist
cp -R skills/mcp-app-factory/assets skills/dashboard/assets 2>/dev/null || true
```

- [ ] **Step 2: Move page-builder dashboard content**

The page-builder has a template viewer at `skills/page-builder/augur/dashboard/t/[templateId]/`:

```bash
mkdir -p skills/dashboard/pages/studio/page-builder/t/\[templateId\]
cp skills/page-builder/augur/dashboard/t/\[templateId\]/* skills/dashboard/pages/studio/page-builder/t/\[templateId\]/
```

- [ ] **Step 3: Remove old skill directories**

```bash
rm -rf skills/mcp-app-factory
rm -rf skills/frontend
rm -rf skills/page-builder
```

- [ ] **Step 4: Verify SKILL.md references**

Check that no other skills depend on the removed skills:

```bash
# Two-pass: find SKILL.md files with dependencies, then check for old skill names
grep -rl "x-augur-dependencies" skills/*/SKILL.md | \
  xargs grep -l "mcp-app-factory\|frontend\|page-builder" | \
  grep -v "skills/dashboard"
```

If any skills reference the old names in `x-augur-dependencies`, update them to `dashboard`. Note: YAML dependencies are multi-line (`- frontend` on its own line), so single-line grep patterns won't match — use the two-pass approach above.

- [ ] **Step 5: Commit merge**

```bash
git add skills/dashboard/ skills/mcp-app-factory skills/frontend skills/page-builder
git commit -m "feat(dashboard): merge mcp-app-factory, frontend, page-builder into UI skill"
```

---

## Task 7: Update mount system

**Files:**
- Modify: `apps/dashboard/scripts/mount-plugins.ts:335-355,370-416,697-721`
- Modify: `apps/dashboard/scripts/mount/generate-registry.ts:114-205,243,258-274`

- [ ] **Step 1: Add hub alignment exemption for system hub**

In `apps/dashboard/scripts/mount-plugins.ts`, update Phase 3b (lines 335-355):

```typescript
// Phase 3b: Hub alignment (ADR-235)
// A plugin's contributes_to MUST match its bundle directory.
// Exception: x-augur-hub: system skills are cross-hub infrastructure.
const hubAlignmentErrors: string[] = [];
for (const plugin of plugins) {
  // System-hub skills are infrastructure — exempt from bundle-hub matching
  if (plugin.hubId === "system") continue;
  if (plugin.hubId !== plugin.bundle) {
    hubAlignmentErrors.push(
      `Plugin ${plugin.skill} at ${plugin.mountPath} has contributes_to: "${plugin.hubId}" — must match bundle "${plugin.bundle}". Update x-augur-hub in skills/${plugin.skill}/SKILL.md`,
    );
  }
}
```

- [ ] **Step 2: Update page source path**

In `apps/dashboard/scripts/mount-plugins.ts`, update Phase 4b (lines 370-416):

```typescript
// Phase 4b: Collect UI skill page entries for catch-all registry (ADR-450)
console.log(`\nCollecting UI skill pages for registry (ADR-450)...`);
const uiPagesDir = path.join(REPO_ROOT, "skills", "dashboard", "pages");

// No manifest — discovery is convention-based only
const registryEntries: RegistryPageEntry[] = [];

if (existsSync(uiPagesDir)) {
  // Scan skills/dashboard/pages/{hub}/{skill}/ for page.tsx files
  try {
    const hubDirs = await fs.readdir(uiPagesDir, { withFileTypes: true });
    for (const hubEntry of hubDirs) {
      if (!hubEntry.isDirectory()) continue;
      const hubName = hubEntry.name;
      const hubDir = path.join(uiPagesDir, hubName);

      const hubRegistryEntries = await collectConventionPages(
        hubDir,
        hubName,
        new Set<string>(), // No manifest dirs to exclude
      );
      registryEntries.push(...hubRegistryEntries);
    }
  } catch {
    // No hub directories — fine
  }
}

console.log(`   Collected ${registryEntries.length} UI skill page entries`);
```

- [ ] **Step 3: Update registry import paths**

In `apps/dashboard/scripts/mount/generate-registry.ts`, update `buildHubRegistries` (line 243):

```typescript
// FROM:
importPath: `@/lib/plugin-pages/${toPosixPath(path.join(hubId, entry.slug, "page"))}`,

// TO:
importPath: `@/pages/${toPosixPath(path.join(hubId, entry.slug, "page"))}`,
```

- [ ] **Step 4: Remove syncPluginPageSources**

In `apps/dashboard/scripts/mount/generate-registry.ts`, the `syncPluginPageSources` function (lines 258-274) copies from `plugins/ui/pages/` to `lib/plugin-pages/`. This is no longer needed — pages live directly in `skills/dashboard/pages/`:

Remove the function body or replace with a no-op:

```typescript
export async function syncPluginPageSources(
  _appDir: string,
  _repoRoot: string,
): Promise<void> {
  // No-op: pages now live directly in skills/dashboard/pages/
  // No sync needed — @/ alias resolves to skills/dashboard/
}
```

Also remove `collectManifestPages` export or mark as deprecated — it's no longer called.

- [ ] **Step 5: Update watch mode**

In `apps/dashboard/scripts/mount-plugins.ts`, update `startWatchMode` (after line 723):

```typescript
  // Also watch skills/dashboard/pages/ for custom page changes
  const uiSkillPagesDir = path.join(config.repoRoot, "skills", "dashboard", "pages");
  try {
    const stat = await fs.stat(uiSkillPagesDir);
    if (stat.isDirectory()) {
      watchPaths.push(uiSkillPagesDir);
    }
  } catch {
    // skills/dashboard/pages/ not found — skip
  }
```

Insert this block after the existing skill scan loop (line 721) and before the watch path count log (line 725).

- [ ] **Step 6: Rebuild mount scripts**

The mount scripts are TypeScript compiled to `scripts/dist/`. Rebuild BEFORE verifying:

```bash
cd apps/dashboard && pnpm run build:scripts
```

- [ ] **Step 7: Run mount-plugins to verify**

```bash
cd apps/dashboard && node scripts/dist/mount-plugins.mjs 2>&1 | tail -20
```

Expected: `Collected N UI skill page entries` where N matches the number of page.tsx files in `skills/dashboard/pages/`.

- [ ] **Step 8: Commit mount system changes**

```bash
git add apps/dashboard/scripts/
git commit -m "feat(dashboard): update mount system for skills/dashboard/pages/ source"
```

---

## Task 8: Audit API routes

**Files:**
- Review: `apps/dashboard/app/api/**/*.ts`

- [ ] **Step 1: Scan for prohibited imports**

```bash
grep -r "import fs\|require('fs')\|execSync\|execFile\|spawn" apps/dashboard/app/api/ --include="*.ts" | grep -v "@fs-exempt"
```

Expected: Zero results. Any hits without `@fs-exempt` waivers must be converted to MCP tool calls before the build (ESLint will block them).

- [ ] **Step 2: Review fs-exempt waivers**

```bash
grep -r "@fs-exempt" apps/dashboard/app/api/ --include="*.ts"
```

Expected: Only CLI infrastructure routes (`pty-setup.ts`, `cli-config.ts`). These are legitimate per ADR-266.

- [ ] **Step 3: Commit any fixes**

If any non-compliant routes were found and fixed:

```bash
git add apps/dashboard/app/api/
git commit -m "fix(dashboard): convert non-compliant API routes to MCP proxy"
```

---

## Task 9: Eliminate root workspace

**Files:**
- Delete: Root `package.json`
- Delete: Root `pnpm-workspace.yaml`
- Move: Root `pnpm-lock.yaml` → `apps/dashboard/pnpm-lock.yaml`
- Modify: `apps/dashboard/package.json` (add pnpm overrides from root)

- [ ] **Step 1: Copy pnpm overrides to dashboard package.json**

The root `package.json` has pnpm overrides and `onlyBuiltDependencies` that need to move:

Add to `apps/dashboard/package.json`:

```json
{
  "pnpm": {
    "onlyBuiltDependencies": [
      "esbuild",
      "node-pty",
      "sharp",
      "unrs-resolver"
    ],
    "overrides": {
      "flatted": ">=3.4.1",
      "dompurify": ">=3.3.3"
    }
  }
}
```

- [ ] **Step 2: Move lockfile**

```bash
mv pnpm-lock.yaml apps/dashboard/pnpm-lock.yaml
```

- [ ] **Step 3: Remove root workspace files**

```bash
rm package.json
rm pnpm-workspace.yaml
```

- [ ] **Step 4: Reinstall from apps/dashboard/**

```bash
cd apps/dashboard && pnpm install
```

Expected: pnpm resolves all deps inside `apps/dashboard/node_modules/`. If install fails due to lockfile format mismatch (workspace → standalone), delete `apps/dashboard/pnpm-lock.yaml` and rerun — pnpm will regenerate it.

```bash
# Verify no root node_modules was created
ls ~/Projects/Augur/node_modules 2>/dev/null && echo "WARNING: root node_modules still exists" || echo "OK: no root node_modules"
```

- [ ] **Step 5: Remove root node_modules**

```bash
rm -rf node_modules
```

- [ ] **Step 6: Verify pnpm scripts work from dashboard**

```bash
cd apps/dashboard && pnpm dev --help 2>&1 | head -5
cd apps/dashboard && pnpm run mount-plugins 2>&1 | tail -10
```

- [ ] **Step 7: Check for CI workflows that assume workspace layout**

```bash
find . -maxdepth 3 -name "*.yml" -o -name "*.yaml" | grep -v node_modules | xargs grep -l "pnpm install\|pnpm run build" 2>/dev/null
```

If any CI workflows run `pnpm install` from the repo root, update them to `cd apps/dashboard && pnpm install`.

- [ ] **Step 8: Commit workspace elimination**

```bash
git add -A
git commit -m "feat(dashboard): eliminate root workspace — standalone apps/dashboard/

Remove root package.json, pnpm-workspace.yaml. Move pnpm-lock.yaml and
pnpm overrides to apps/dashboard/. Dashboard is now a standalone package."
```

---

## Task 10: Full build verification

**Files:** None (verification only)

- [ ] **Step 1: Rebuild mount scripts**

```bash
cd apps/dashboard && pnpm run build:scripts
```

- [ ] **Step 2: Run mount-plugins**

```bash
cd apps/dashboard && pnpm run mount-plugins
```

Expected output should show:
- Hub alignment check passes (system hub exempted)
- Page entries collected from `skills/dashboard/pages/`
- Registry files generated for all 6 hubs

- [ ] **Step 3: Build dashboard**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -30
```

Expected: Build succeeds. All pages compile. No import resolution errors.

- [ ] **Step 4: Verify page count matches**

```bash
# Count pages in skills/dashboard/pages/
find skills/dashboard/pages -name "page.tsx" | wc -l

# Count registry entries across all hubs
grep -c "import(" apps/dashboard/app/*/\[\[...slug\]\]/registry.ts | paste -sd+ - | bc
```

The two numbers should be close (registry may exclude autopage-only routes).

- [ ] **Step 5: Spot-check critical pages**

Start dev server and verify key pages load:

```bash
cd apps/dashboard && pnpm dev &
sleep 5

# Check a few critical pages return 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/career/pipeline
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/brain/knowledge
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/command/daemon
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/life/finance

# Kill dev server
kill %1
```

Expected: All return 200.

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix(dashboard): address build verification issues"
```

---

## Follow-Up Tasks (Out of Scope)

These are identified but deliberately excluded from this plan to keep scope manageable:

1. **Move framework code** — Move `apps/dashboard/components/`, `apps/dashboard/lib/` (hooks, stores, MCP client, blocks, autopage) into `skills/dashboard/framework/`, `skills/dashboard/components/`, `skills/dashboard/lib/`. This is the largest migration (~300 files) and should be its own spec + plan.

2. **Recover deleted pages from git** — The 344 files deleted from `dist/plugins/` need evaluation. Many are stale compiled copies, but some (growth dashboard, project-dev, enterprise pages) may have unique content worth recovering. Run `git show <pre-deletion-commit>:dist/plugins/` to evaluate.

3. **Vault dashboard preferences** — Create `get_vault_dir()/dashboard/` for user layout preferences, saved widget configs, and custom themes. Currently in localStorage.

4. **Update dev-build skill** — The `/dev-build` command may reference root `package.json` or assume workspace layout. Update path resolution after root workspace elimination.

5. **Update CLAUDE.md** — Reflect new directory layout, update "Plugin File Mounting" section, add skills/dashboard/ to directory layout.

6. **Write ADR** — Document the architectural decision formally in `get_vault_dir()/dev/adrs/`.
