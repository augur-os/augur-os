# Framework Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move ~98 domain-specific files from `apps/dashboard/` to `skills/dashboard/`, establish `@/` (framework) and `@skill/` (features) dual-alias architecture.

**Architecture:** Two TypeScript path aliases partition the dashboard codebase by stability: `@/` → `apps/dashboard/*` (framework — stable) and `@skill/` → `skills/dashboard/*` (features — volatile). The boundary is enforced by the rule: `@/` never imports `@skill/`. Classification was validated by exhaustive import-graph analysis.

**Tech Stack:** Next.js 16, React 19, TypeScript, pnpm, Turbopack

**Spec:** `docs/superpowers/specs/2026-03-23-framework-migration-design.md`

---

## File Structure

### Modified files
- `apps/dashboard/tsconfig.json` — Add `@skill/*` alias, remove `@/pages/*`
- `apps/dashboard/scripts/mount/generate-registry.ts` — `@/pages/` → `@skill/pages/`
- `apps/dashboard/components/plugin/sections/shared.ts` — Import formatFileSize from new location
- `apps/dashboard/components/chat/utils.ts` — Remove formatFileSize (extracted)

### Created files
- `apps/dashboard/lib/utils/format.ts` — Extracted formatFileSize utility

### Moved files (apps/dashboard/ → skills/dashboard/)
- `components/chat/` (~27 files, without utils.ts)
- `components/agents/` (~14 files)
- `components/action-bar/` (~6 files)
- `components/attention/` (~1 file)
- `components/inbox/` (~3 files)
- `components/layout-config/` (~7 files)
- `components/files/` (~2 files)
- ~20 top-level domain widget components
- `lib/prompts/` (~1 file)
- `lib/stores/layoutStore.ts`, `lib/stores/searchStore.ts` (~2 files)
- ~15 domain hooks

### Deleted
- `apps/dashboard/lib/plugins/` (~91 dead mount files)

---

## Task 1: Extract formatFileSize to framework utils

**Files:**
- Create: `apps/dashboard/lib/utils/format.ts`
- Modify: `apps/dashboard/components/chat/utils.ts`
- Modify: `apps/dashboard/components/plugin/sections/shared.ts`

- [ ] **Step 1: Read the current chat/utils.ts to find formatFileSize**

```bash
grep -n "formatFileSize" apps/dashboard/components/chat/utils.ts
```

- [ ] **Step 2: Create the framework utility file**

Create `apps/dashboard/lib/utils/format.ts` with the `formatFileSize` function extracted from `components/chat/utils.ts`. Copy the function exactly.

- [ ] **Step 3: Update the framework importer**

In `apps/dashboard/components/plugin/sections/shared.ts`, change:
```typescript
// FROM:
export { formatFileSize } from "@/components/chat/utils";
// TO:
export { formatFileSize } from "@/lib/utils/format";
```

- [ ] **Step 4: Keep chat/utils.ts exporting formatFileSize (re-export from new location)**

In `apps/dashboard/components/chat/utils.ts`, replace the `formatFileSize` function body with a re-export:
```typescript
export { formatFileSize } from "@/lib/utils/format";
```
This keeps existing chat component imports working during migration.

- [ ] **Step 5: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```
Expected: Build passes with zero errors.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/utils/format.ts apps/dashboard/components/chat/utils.ts apps/dashboard/components/plugin/sections/shared.ts
git commit -m "refactor(dashboard): extract formatFileSize to lib/utils/format

Decouple plugin/sections/shared.ts from chat/utils so chat components
can move to @skill/ without breaking framework imports."
```

---

## Task 2: Audit and delete dead lib/plugins/

**Files:**
- Delete: `apps/dashboard/lib/plugins/` (entire directory)
- Modify: Any API routes importing from `lib/plugins/` (convert to MCP calls)

- [ ] **Step 1: Find all live imports of lib/plugins/**

```bash
grep -r "lib/plugins" apps/dashboard/app/ apps/dashboard/components/ apps/dashboard/lib/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"
```

- [ ] **Step 2: For each live import found, resolve it**

For each file that imports from `lib/plugins/`:
- If the imported module exists in `skills/dashboard/lib/` (moved in ADR-483 Task 6), update the import to use the new path
- If the imported module is a utility function, convert the API route to use an MCP proxy call instead
- Document each resolution

- [ ] **Step 3: Delete lib/plugins/**

```bash
rm -rf apps/dashboard/lib/plugins
```

- [ ] **Step 4: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/plugins apps/dashboard/app/
git commit -m "cleanup(dashboard): delete dead lib/plugins/ mount directory

91 files of stale plugin mounts removed. Live imports converted to
MCP proxy calls or redirected to skills/dashboard/lib/."
```

---

## Task 3: Update tsconfig + registry (atomic)

**Files:**
- Modify: `apps/dashboard/tsconfig.json`
- Modify: `apps/dashboard/scripts/mount/generate-registry.ts`

- [ ] **Step 1: Update tsconfig.json**

Read `apps/dashboard/tsconfig.json`. Change the paths:

```json
"paths": {
  "@/pages/*": ["skills/dashboard/pages/*"],
  "@/*": ["apps/dashboard/*"]
}
```

To:

```json
"paths": {
  "@/*": ["apps/dashboard/*"],
  "@skill/*": ["skills/dashboard/*"]
}
```

- [ ] **Step 2: Update generate-registry.ts import path**

In `apps/dashboard/scripts/mount/generate-registry.ts`, find the `importPath` line in `buildHubRegistries`:

```typescript
// FROM:
importPath: `@/pages/${toPosixPath(path.join(hubId, entry.slug, "page"))}`,
// TO:
importPath: `@skill/pages/${toPosixPath(path.join(hubId, entry.slug, "page"))}`,
```

- [ ] **Step 3: Rebuild mount scripts and regenerate registries**

```bash
cd apps/dashboard && pnpm run build:scripts && pnpm run mount-plugins 2>&1 | tail -15
```

Expected: `Generated 6 hub registries (58 total pages)` with `@skill/pages/` import paths.

- [ ] **Step 4: Verify a registry file uses @skill/**

```bash
head -5 apps/dashboard/app/career/\[\[...slug\]\]/registry.ts
```

Expected: Import paths start with `@skill/pages/career/...`.

- [ ] **Step 5: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 6: Commit (tsconfig + registry + generated files in ONE commit)**

```bash
git add apps/dashboard/tsconfig.json apps/dashboard/scripts/mount/generate-registry.ts apps/dashboard/app/
git commit -m "feat(dashboard): add @skill/* alias, migrate registry to @skill/pages/

Replace @/pages/* with @skill/* (covers all of skills/dashboard/).
Registries now import from @skill/pages/{hub}/{page}/page."
```

---

## Task 4: Move chat components

**Files:**
- Move: `apps/dashboard/components/chat/` → `skills/dashboard/components/chat/` (~27 files, utils.ts stays)

- [ ] **Step 1: Create target directory and move files**

```bash
mkdir -p skills/dashboard/components/chat
# Move all files EXCEPT utils.ts (it stays as framework re-export)
find apps/dashboard/components/chat -name "*.tsx" -o -name "*.ts" | grep -v "utils.ts" | while read f; do
  rel="${f#apps/dashboard/components/chat/}"
  mkdir -p "skills/dashboard/components/chat/$(dirname "$rel")"
  mv "$f" "skills/dashboard/components/chat/$rel"
done
```

- [ ] **Step 2: Rewrite imports in moved files**

In the moved files, any imports like `@/components/chat/SomeComponent` need to become `@skill/components/chat/SomeComponent`. Also update relative imports if they reference sibling files.

```bash
# Find all @/components/chat imports in moved files
grep -r "@/components/chat" skills/dashboard/components/chat/
```

Replace each `@/components/chat/` with `@skill/components/chat/`.

- [ ] **Step 3: Rewrite imports in consumers (pages)**

Pages in `skills/dashboard/pages/` that import from `@/components/chat/` need updating:

```bash
grep -rl "@/components/chat" skills/dashboard/pages/
```

Replace each `@/components/chat/` with `@skill/components/chat/`.

- [ ] **Step 4: Remove empty source directory**

```bash
# Check if only utils.ts remains
ls apps/dashboard/components/chat/
# If only utils.ts, leave it. If empty, remove the directory.
```

- [ ] **Step 5: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add skills/dashboard/components/chat/ apps/dashboard/components/chat/ skills/dashboard/pages/
git commit -m "feat(dashboard): move chat components to @skill/components/chat/"
```

---

## Task 5: Move agents + action-bar

**Files:**
- Move: `apps/dashboard/components/agents/` → `skills/dashboard/components/agents/` (~14 files)
- Move: `apps/dashboard/components/action-bar/` → `skills/dashboard/components/action-bar/` (~6 files)

- [ ] **Step 1: Move directories**

```bash
mv apps/dashboard/components/agents skills/dashboard/components/agents
mv apps/dashboard/components/action-bar skills/dashboard/components/action-bar
```

- [ ] **Step 2: Rewrite imports in moved files**

```bash
grep -r "@/components/agents\|@/components/action-bar" skills/dashboard/components/agents/ skills/dashboard/components/action-bar/
```

Replace `@/components/agents/` → `@skill/components/agents/`, `@/components/action-bar/` → `@skill/components/action-bar/`.

- [ ] **Step 3: Rewrite imports in consumers (pages)**

```bash
grep -rl "@/components/agents\|@/components/action-bar" skills/dashboard/pages/
```

Replace in each file.

- [ ] **Step 4: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/components/agents/ skills/dashboard/components/action-bar/ apps/dashboard/components/agents apps/dashboard/components/action-bar skills/dashboard/pages/
git commit -m "feat(dashboard): move agents + action-bar to @skill/"
```

---

## Task 6: Move attention + inbox + layout-config + files

**Files:**
- Move: `apps/dashboard/components/attention/` → `skills/dashboard/components/attention/` (~1 file)
- Move: `apps/dashboard/components/inbox/` → `skills/dashboard/components/inbox/` (~3 files)
- Move: `apps/dashboard/components/layout-config/` → `skills/dashboard/components/layout-config/` (~7 files)
- Move: `apps/dashboard/components/files/` → `skills/dashboard/components/files/` (~2 files)

- [ ] **Step 1: Move directories**

```bash
mv apps/dashboard/components/attention skills/dashboard/components/attention
mv apps/dashboard/components/inbox skills/dashboard/components/inbox
mv apps/dashboard/components/layout-config skills/dashboard/components/layout-config
mv apps/dashboard/components/files skills/dashboard/components/files
```

- [ ] **Step 2: Rewrite imports in moved files and consumers**

```bash
grep -rl "@/components/attention\|@/components/inbox\|@/components/layout-config\|@/components/files" skills/dashboard/
```

Replace `@/components/{category}/` → `@skill/components/{category}/` for each.

- [ ] **Step 3: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add skills/dashboard/components/ apps/dashboard/components/attention apps/dashboard/components/inbox apps/dashboard/components/layout-config apps/dashboard/components/files
git commit -m "feat(dashboard): move attention, inbox, layout-config, files to @skill/"
```

---

## Task 7: Move domain widgets

**Files:**
- Move: ~20 top-level component files from `apps/dashboard/components/` to `skills/dashboard/components/`

- [ ] **Step 1: Classify top-level components**

Run an import-graph check to identify which top-level components are domain-only (safe to move):

```bash
# List all top-level component files
ls apps/dashboard/components/*.tsx apps/dashboard/components/*.ts 2>/dev/null | sort

# For each file, check if framework code imports it
for f in apps/dashboard/components/*.tsx apps/dashboard/components/*.ts; do
  name=$(basename "$f" .tsx)
  name=$(echo "$name" | sed 's/.ts$//')
  # Search framework dirs for imports of this component
  hits=$(grep -rl "components/$name" \
    apps/dashboard/components/plugin/ \
    apps/dashboard/components/ui/ \
    apps/dashboard/components/blocks/ \
    apps/dashboard/components/bridge/ \
    apps/dashboard/components/remote/ \
    apps/dashboard/components/shared/ \
    apps/dashboard/components/plugin-wizard/ \
    apps/dashboard/lib/ \
    apps/dashboard/app/ \
    --include="*.ts" --include="*.tsx" 2>/dev/null)
  if [ -z "$hits" ]; then
    echo "DOMAIN (move): $f"
  else
    echo "FRAMEWORK (stay): $f  ← imported by: $(echo $hits | tr '\n' ' ')"
  fi
done
```

- [ ] **Step 2: Move confirmed domain widgets**

For each file classified as DOMAIN in step 1:

```bash
mv apps/dashboard/components/{FileName}.tsx skills/dashboard/components/
```

- [ ] **Step 3: Rewrite imports in consumers**

```bash
# For each moved widget, find consumers and rewrite
grep -rl "@/components/{WidgetName}" skills/dashboard/pages/ skills/dashboard/components/
```

Replace `@/components/{WidgetName}` → `@skill/components/{WidgetName}`.

- [ ] **Step 4: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/components/ apps/dashboard/components/ skills/dashboard/pages/
git commit -m "feat(dashboard): move domain widgets to @skill/components/"
```

---

## Task 8: Move domain lib + stores

**Files:**
- Move: `apps/dashboard/lib/prompts/` → `skills/dashboard/lib/prompts/`
- Move: `apps/dashboard/lib/stores/layoutStore.ts` → `skills/dashboard/lib/stores/layoutStore.ts`
- Move: `apps/dashboard/lib/stores/searchStore.ts` → `skills/dashboard/lib/stores/searchStore.ts`

- [ ] **Step 1: Verify these stores are NOT imported by framework**

```bash
grep -r "layoutStore\|searchStore" apps/dashboard/components/plugin/ apps/dashboard/components/ui/ apps/dashboard/components/blocks/ apps/dashboard/lib/mcp/ apps/dashboard/lib/webmcp/ apps/dashboard/lib/server/ apps/dashboard/app/ --include="*.ts" --include="*.tsx"
```

Expected: Zero results (only pages/domain components import these).

- [ ] **Step 2: Move files**

```bash
mkdir -p skills/dashboard/lib/prompts skills/dashboard/lib/stores
mv apps/dashboard/lib/prompts/* skills/dashboard/lib/prompts/
mv apps/dashboard/lib/stores/layoutStore.ts skills/dashboard/lib/stores/
mv apps/dashboard/lib/stores/searchStore.ts skills/dashboard/lib/stores/
```

- [ ] **Step 3: Rewrite imports**

```bash
grep -rl "@/lib/prompts\|@/lib/stores/layoutStore\|@/lib/stores/searchStore" skills/dashboard/
```

Replace with `@skill/lib/prompts/`, `@skill/lib/stores/layoutStore`, `@skill/lib/stores/searchStore`.

- [ ] **Step 4: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/lib/ apps/dashboard/lib/prompts apps/dashboard/lib/stores/
git commit -m "feat(dashboard): move domain lib + stores to @skill/"
```

---

## Task 9: Move domain hooks

**Files:**
- Move: ~15 domain hooks from `apps/dashboard/hooks/` to `skills/dashboard/hooks/`

- [ ] **Step 1: Classify hooks as framework vs domain**

```bash
# For each hook file, check if framework code imports it
for f in apps/dashboard/hooks/*.ts apps/dashboard/hooks/*.tsx; do
  name=$(basename "$f" | sed 's/\.\(ts\|tsx\)$//')
  hits=$(grep -rl "$name" \
    apps/dashboard/components/plugin/ \
    apps/dashboard/components/ui/ \
    apps/dashboard/components/blocks/ \
    apps/dashboard/components/bridge/ \
    apps/dashboard/components/remote/ \
    apps/dashboard/components/shared/ \
    apps/dashboard/lib/ \
    apps/dashboard/app/ \
    --include="*.ts" --include="*.tsx" 2>/dev/null)
  if [ -z "$hits" ]; then
    echo "DOMAIN (move): $name"
  else
    echo "FRAMEWORK (stay): $name"
  fi
done
```

- [ ] **Step 2: Move confirmed domain hooks**

```bash
mkdir -p skills/dashboard/hooks
# For each DOMAIN hook:
mv apps/dashboard/hooks/{hookName}.ts skills/dashboard/hooks/
```

- [ ] **Step 3: Rewrite imports in consumers**

```bash
grep -rl "@/hooks/{hookName}" skills/dashboard/
```

Replace `@/hooks/{hookName}` → `@skill/hooks/{hookName}` for each moved hook.

- [ ] **Step 4: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add skills/dashboard/hooks/ apps/dashboard/hooks/ skills/dashboard/pages/ skills/dashboard/components/
git commit -m "feat(dashboard): move domain hooks to @skill/hooks/"
```

---

## Task 10: Final verification

**Files:** None (verification only)

- [ ] **Step 1: Full build**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -20
```

Expected: Build succeeds, all routes compiled.

- [ ] **Step 2: Verify dependency direction**

Confirm no framework file imports from `@skill/`:

```bash
grep -r "@skill/" apps/dashboard/components/ apps/dashboard/lib/ apps/dashboard/hooks/ apps/dashboard/app/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"
```

Expected: Only `app/{hub}/[[...slug]]/registry.ts` files (generated, allowed). Zero matches from `components/`, `lib/`, or `hooks/`.

- [ ] **Step 3: Verify page count**

```bash
find skills/dashboard/pages -name "page.tsx" | wc -l
```

Expected: 58 (unchanged from before migration).

- [ ] **Step 4: Run tests**

```bash
cd apps/dashboard && pnpm test 2>&1 | tail -20
```

Fix any test import issues (stale `@/components/chat/` references in test files).

- [ ] **Step 5: Update test imports if needed**

```bash
grep -r "@/components/chat\|@/components/agents\|@/components/action-bar\|@/components/attention\|@/components/inbox\|@/components/layout-config\|@/components/files" apps/dashboard/__tests__/ skills/dashboard/pages/ --include="*.test.*"
```

Replace with `@skill/` equivalents.

- [ ] **Step 6: Spot-check critical pages**

```bash
cd apps/dashboard && pnpm dev &
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/career/pipeline
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/brain/knowledge
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/command/daemon
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/life/finance
kill %1
```

Expected: All return 200.

- [ ] **Step 7: Commit any final fixes**

```bash
git add -A
git commit -m "fix(dashboard): address verification issues from framework migration"
```

---

## Follow-Up (Out of Scope)

1. **ESLint rule** — Add `no-restricted-imports` rule to prevent `@/` files from importing `@skill/`, making the boundary enforceable at lint time.
2. **Update CLAUDE.md** — Document the `@/` vs `@skill/` convention and the dependency rule.
3. **CI workflow** — Add a CI check that greps for `@skill/` imports in framework code and fails if found.
