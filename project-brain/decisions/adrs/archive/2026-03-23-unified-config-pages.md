# Unified Config-Driven Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SkillAutoPage, DashboardWidget, and dropdown components with a single ConfigPage renderer that builds pages from YAML block lists.

**Architecture:** Skills declare pages in `augur/pages/*.yaml` as ordered lists of blocks. A `ConfigPage` client component renders them using the existing `BlockRenderer` pipeline. A `FlowLayout` component handles size-based auto-flow (`full`/`half`/`third`). Custom TSX pages coexist unchanged. The scanner discovers both YAML and TSX pages and registers them as hub tabs.

**Tech Stack:** Next.js 16, React 19, TypeScript, pnpm, Turbopack, existing block system (`useBlockData`, `BlockRenderer`)

**Spec:** `docs/superpowers/specs/2026-03-23-unified-config-pages-design.md`

---

## File Structure

### Created files
- `apps/dashboard/lib/blocks/flow-layout.tsx` — FlowLayout component (size-based auto-flow)
- `apps/dashboard/lib/blocks/flow-types.ts` — BlockConfig, PageConfig, FlowBlockRenderer types
- `apps/dashboard/components/plugin/ConfigPage.tsx` — Page renderer from YAML config
- `apps/dashboard/components/plugin/CustomizePanel.tsx` — Block add/reorder/remove panel
- `apps/dashboard/lib/blocks/custom-block-registry.ts` — AUTO-GENERATED custom component map
- `skills/career/augur/pages/pipeline.yaml` — First YAML page (pilot migration)

### Modified files
- `apps/dashboard/lib/plugin-discovery/scanner.ts` — Add YAML page discovery from `skills/{skill}/augur/pages/`
- `apps/dashboard/scripts/generate-tab-registry.ts` — Register YAML pages as hub tabs, generate config JSON chunks
- `apps/dashboard/lib/blocks/block-resolver.ts` — Add new block types (health, vault-notes, custom-sources, file-list, data-preview, custom)
- `apps/dashboard/lib/blocks/types.ts` — Extend BlockType union with new types
- `apps/dashboard/components/HubTabBar.tsx` — Replace BlocksDropdown + AutoPagesDropdown with Customize button
- `apps/dashboard/components/plugin/HubTabNav.tsx` — Pass customize handler to HubTabBar
- `apps/dashboard/app/{hub}/[[...slug]]/page.tsx` — Route YAML pages to ConfigPage

---

## Task 1: FlowLayout component + types

**Files:**
- Create: `apps/dashboard/lib/blocks/flow-types.ts`
- Create: `apps/dashboard/lib/blocks/flow-layout.tsx`
- Create: `tests/dashboard/blocks/flow-layout.test.tsx`

- [ ] **Step 1: Define flow types**

Create `apps/dashboard/lib/blocks/flow-types.ts`:

```typescript
import type { BlockType, BlockSearch, BlockFilter, RowAction, ConfigSchema } from "./types";

export type BlockSize = "full" | "half" | "third";

export interface BlockConfig {
  type: BlockType | "custom";
  mcp_tool?: string;
  component?: string;
  size?: BlockSize;
  scope?: "hub" | "skill";
  skill_id?: string;
  manifest_id?: string;
  search?: BlockSearch;
  filters?: BlockFilter[];
  row_actions?: RowAction[];
  config_schema?: ConfigSchema;
  [key: string]: unknown;
}

export interface PageConfig {
  title: string;
  icon: string;
  hub: string;
  route: string;
  order?: number;
  blocks: BlockConfig[];
}

export const SIZE_FRACTIONS: Record<BlockSize, number> = {
  full: 1,
  half: 0.5,
  third: 1 / 3,
};
```

- [ ] **Step 2: Write FlowLayout test**

Create `tests/dashboard/blocks/flow-layout.test.tsx` with tests for:
- All `full` blocks → each in its own row
- Two `half` blocks → same row
- Three `third` blocks → same row
- Orphan `half` → stays half-width, not stretched
- Mixed: `third` + `half` → half wraps to next row
- Empty blocks array → renders nothing

- [ ] **Step 3: Implement FlowLayout**

Create `apps/dashboard/lib/blocks/flow-layout.tsx`:
- Takes `children: ReactNode[]` and `sizes: BlockSize[]`
- Groups children into rows based on size fractions
- Renders rows with CSS flex, each child gets `flex: 0 0 {percent}%` based on size
- Responsive: below `md` breakpoint, all blocks become `full`

- [ ] **Step 4: Run tests, verify pass**

```bash
cd apps/dashboard && pnpm test -- --testPathPattern="flow-layout" 2>&1 | tail -10
```

- [ ] **Step 5: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/blocks/flow-types.ts apps/dashboard/lib/blocks/flow-layout.tsx tests/dashboard/blocks/flow-layout.test.tsx
git commit -m "feat(dashboard): add FlowLayout component for config-driven pages"
```

---

## Task 2: ConfigPage renderer

**Files:**
- Create: `apps/dashboard/components/plugin/ConfigPage.tsx`
- Modify: `apps/dashboard/lib/blocks/block-resolver.ts`
- Modify: `apps/dashboard/lib/blocks/types.ts`

- [ ] **Step 1: Extend BlockType with new types**

In `apps/dashboard/lib/blocks/types.ts`, add to the `BlockType` union:
```typescript
| "health" | "vault-notes" | "custom-sources" | "file-list" | "data-preview" | "custom"
```

- [ ] **Step 2: Add new block type imports to block-resolver.ts**

Add lazy imports to `BLOCK_COMPONENTS` for the 5 new data block types. For now, create placeholder components that render `<BlockShell>` with a "Coming soon" message. The `custom` type is handled separately (not in BLOCK_COMPONENTS).

- [ ] **Step 3: Create FlowBlockRenderer wrapper**

Create a thin `FlowBlockRenderer` in `apps/dashboard/components/plugin/ConfigPage.tsx` (or separate file) that:
- Accepts `BlockConfig` directly (no `BlockInstance`)
- Constructs `dataSource: { mcpTool: blockConfig.mcp_tool }` from the config
- Merges inline YAML fields (search, filters, row_actions) with manifest defaults if `manifest_id` is set (lookup by `BlockManifest.id`, not by tool name)
- Constructs a `BlockInstance` internally: `{ blockId, config, position: { x:0, y:0, w:1, h:1 } }` — position is a sentinel ignored by flow layout
- Passes `editing={false}` to `BlockRenderer`
- For `type === "custom"`: resolves via `CUSTOM_BLOCK_COMPONENTS` (Task 5), renders with `next/dynamic`, passes `CustomBlockProps`

This encapsulates the `BlockInstance` construction so `ConfigPage` only works with `BlockConfig`.

- [ ] **Step 4: Implement ConfigPage**

Create `apps/dashboard/components/plugin/ConfigPage.tsx`:

```typescript
'use client';

interface ConfigPageProps {
  config: PageConfig;
  skillId?: string;
}
```

Logic:
- Render page header (title + icon from config)
- For each `BlockConfig` in `config.blocks`, render `<FlowBlockRenderer block={block} />`
- Collect sizes array from blocks, pass children + sizes to `FlowLayout`
- If dev mode (`useModeStore`), append dev-only blocks (health, assets, config, tools, logs)
- Wrap each block in `ErrorBoundary`

- [ ] **Step 4: Build to verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/plugin/ConfigPage.tsx apps/dashboard/lib/blocks/types.ts apps/dashboard/lib/blocks/block-resolver.ts
git commit -m "feat(dashboard): add ConfigPage renderer for YAML-driven pages"
```

---

## Task 3: YAML page scanner

**Files:**
- Modify: `apps/dashboard/lib/plugin-discovery/scanner.ts`
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts`

- [ ] **Step 1: Extend DiscoveredPage interface**

In `scanner.ts` at the `DiscoveredPage` interface (~line 582), add:
```typescript
yamlConfig?: string;  // absolute path to .yaml source file (config-driven page)
```

- [ ] **Step 2: Add YAML page discovery inside the existing client skill loop**

In `discoverPagesFromFilesystem()` in `scanner.ts`, INSIDE the existing `for (const [clientId, clientDir] of Object.entries(clientDirsForPages))` loop (~line 803), inside the per-skill iteration (~line 814), add an inner section AFTER the `augur/dashboard/` scan that reads `augur/pages/*.yaml`:

```typescript
// Inside the per-skill loop, after the augur/dashboard/ scan:
const yamlPagesDir = path.join(skillDir, "augur", "pages");
let yamlFiles: fsSync.Dirent[];
try {
  yamlFiles = fsSync.readdirSync(yamlPagesDir, { withFileTypes: true });
} catch { yamlFiles = []; }

for (const yf of yamlFiles) {
  if (!yf.isFile() || !yf.name.endsWith(".yaml")) continue;
  const yamlPath = path.join(yamlPagesDir, yf.name);
  const parsed = yaml.parse(fsSync.readFileSync(yamlPath, "utf8"));
  if (!parsed?.hub || !parsed?.route) continue;
  const routePath = `/${parsed.hub}/${parsed.route}`;
  if (pages.find(p => p.routePath === routePath)) continue; // skip if TSX page exists
  pages.push({
    pageId: parsed.route,
    routePath,
    skill,
    bundle: parsed.hub,
    hubId: parsed.hub,
    isOwner: false,
    overrides: { label: parsed.title, icon: parsed.icon, order: parsed.order },
    yamlConfig: yamlPath,
  });
}
```

This is NOT a separate outer loop — it goes inside the existing per-skill iteration to avoid double-counting.

- [ ] **Step 3: Update generate-tab-registry.ts to handle YAML pages**

When processing discovered pages, if `page.yamlConfig` is set:
- Parse the YAML file
- Write the parsed config as a JSON file to `apps/dashboard/lib/configs/{hub}-{route}.json`
- Add `apps/dashboard/lib/configs/` to `.gitignore` (generated files, rebuilt on `mount-plugins`)
- Add a cleanup step at the start of generation: delete all `*.json` in `lib/configs/` before writing new ones (prevents stale files from renamed/deleted pages)
- Register the page in the hub registry with `importPath` pointing to `ConfigPage` and a per-route dynamic config import

- [ ] **Step 4: Update hub catch-all page.tsx to route YAML pages**

In `apps/dashboard/app/{hub}/[[...slug]]/page.tsx`, when the registry entry is a YAML page, render `<ConfigPage config={...} />` instead of the TSX component.

- [ ] **Step 5: Build and verify**

```bash
cd apps/dashboard && pnpm run build:scripts && pnpm run mount-plugins 2>&1 | tail -15
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/plugin-discovery/scanner.ts apps/dashboard/scripts/generate-tab-registry.ts apps/dashboard/app/ .gitignore
git commit -m "feat(dashboard): add YAML page discovery and config JSON generation"
```

---

## Task 4: Pilot migration — career/pipeline

**Files:**
- Create: `skills/career/augur/pages/pipeline.yaml`
- Delete: `skills/dashboard/pages/career/pipeline/page.tsx` (after verification)

- [ ] **Step 1: Create the YAML page**

Create `skills/career/augur/pages/pipeline.yaml`:

```yaml
title: Job Pipeline
icon: Briefcase
hub: career
route: pipeline
order: 30
blocks:
  - type: stat-grid
    mcp_tool: get-career-status
  - type: data-table
    mcp_tool: get-career-jobs
    search:
      enabled: true
      fields: [title, company, status]
    filters:
      - field: status
        type: pills
        values: [inbox, active, offer, rejected, archive]
    row_actions:
      - id: analyze
        icon: Search
        label: Analyze
        dispatch: ide
```

- [ ] **Step 2: Regenerate registries**

```bash
cd apps/dashboard && pnpm run build:scripts && pnpm run mount-plugins 2>&1 | tail -15
```

Expected: pipeline page appears in career hub registry as a YAML page.

- [ ] **Step 3: Build and verify in browser**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

Navigate to `http://localhost:3000/career/pipeline` — should render stat-grid + data-table from ConfigPage.

- [ ] **Step 4: Compare with original TSX page**

Verify the YAML-driven page renders equivalent content:
- Stat cards showing career status
- Pipeline table with search, filters, row actions

- [ ] **Step 5: Delete the entire TSX page directory**

The pipeline directory contains 7+ files (page.tsx + companion components). Delete the entire directory — the YAML page replaces all of it:

```bash
rm -rf skills/dashboard/pages/career/pipeline/
```

- [ ] **Step 6: Rebuild and verify**

```bash
cd apps/dashboard && pnpm run build:scripts && pnpm run mount-plugins && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 7: Commit**

```bash
git add skills/career/augur/pages/pipeline.yaml skills/dashboard/pages/career/
git commit -m "feat(dashboard): migrate career/pipeline to YAML config page

291 lines TSX → 25 lines YAML. First config-driven page migration."
```

---

## Task 5: Custom block registry

**Files:**
- Create: `apps/dashboard/lib/blocks/custom-block-registry.ts` (generated)
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts` — generate the registry
- Modify: `apps/dashboard/components/plugin/ConfigPage.tsx` — resolve custom blocks

- [ ] **Step 1: Add custom block collection to generator**

In `generate-tab-registry.ts`, after scanning all YAML pages, collect `type: custom` references:

```typescript
const customComponents = new Map<string, string>();
// For each YAML page with type: custom blocks
//   customComponents.set(block.component, `@skill/components/${block.component}`)
// Note: @skill/* resolves to skills/dashboard/* per tsconfig.json.
// Custom components must live at skills/dashboard/components/{component}.tsx.
// Example: component: "daemon/TerminalView" → @skill/components/daemon/TerminalView
//        → skills/dashboard/components/daemon/TerminalView.tsx
// Verify each component path exists on disk before adding to registry.
```

Write `apps/dashboard/lib/blocks/custom-block-registry.ts`:

```typescript
export const CUSTOM_BLOCK_COMPONENTS: Record<string, () => Promise<{ default: ComponentType }>> = {
  // entries from scan
};
```

- [ ] **Step 2: Update ConfigPage to use registry**

For `type: custom` blocks, look up in `CUSTOM_BLOCK_COMPONENTS`, use `next/dynamic` with the factory. Pass `CustomBlockProps` to the resolved component.

- [ ] **Step 3: Build to verify**

```bash
cd apps/dashboard && pnpm run build:scripts && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/lib/blocks/custom-block-registry.ts apps/dashboard/scripts/generate-tab-registry.ts apps/dashboard/components/plugin/ConfigPage.tsx
git commit -m "feat(dashboard): add custom block component registry"
```

---

## Task 6: Customize button (replace dropdowns)

**Files:**
- Create: `apps/dashboard/components/plugin/CustomizePanel.tsx`
- Modify: `apps/dashboard/components/HubTabBar.tsx`
- Delete: `skills/dashboard/components/BlocksDropdown.tsx`
- Delete: `skills/dashboard/components/AutoPagesDropdown.tsx`

- [ ] **Step 1: Build CustomizePanel**

Create `apps/dashboard/components/plugin/CustomizePanel.tsx`:
- Slide-out panel showing available blocks from the hub's contributing skills
- Groups blocks by skill
- Each block has an "Add" button
- Drag handle for reorder (or simple up/down arrows for v1)
- Remove button per block
- Size selector (full/half/third) per block
- "Reset to default" button
- Persistence: read/write `localStorage` keyed by `augur:page-layout:{route}`

- [ ] **Step 2: Find and remove all imports of BlocksDropdown and AutoPagesDropdown**

```bash
grep -rl "BlocksDropdown\|AutoPagesDropdown" apps/dashboard/ skills/dashboard/ --include="*.tsx" --include="*.ts"
```

Remove all imports and usages from every file found (primarily `HubTabBar.tsx`).

- [ ] **Step 3: Replace dropdowns in HubTabBar**

In `HubTabBar.tsx`:
- Remove the now-dead `BlocksDropdown` and `AutoPagesDropdown` rendering slots
- Add a single "Customize" button (icon: `Sliders`) that opens `CustomizePanel`
- Pass the hub's `blocks` list to `CustomizePanel` for the block catalog

- [ ] **Step 4: Delete old dropdown components**

After all imports are removed:

```bash
rm skills/dashboard/components/BlocksDropdown.tsx
rm skills/dashboard/components/AutoPagesDropdown.tsx
```

- [ ] **Step 5: Build and verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

Navigate to a hub page — should see Customize button instead of Blocks/Auto dropdowns.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/components/plugin/CustomizePanel.tsx apps/dashboard/components/HubTabBar.tsx skills/dashboard/components/
git commit -m "feat(dashboard): replace Blocks + Auto dropdowns with Customize button"
```

---

## Task 7: Browse detail page (auto-generated)

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/[skill]/page.tsx` — render ConfigPage instead of current detail view
- Modify: `apps/dashboard/components/plugin/ConfigPage.tsx` — add default config builder

- [ ] **Step 1: Add default config generator**

In `ConfigPage.tsx` or a helper, add `buildDefaultPageConfig(skillId: string)`:

```typescript
function buildDefaultPageConfig(skillId: string): PageConfig {
  return {
    title: smartLabel(skillId),
    icon: "FileText",
    hub: "",
    route: skillId,
    blocks: [
      { type: "health", mcp_tool: "get-skill-health", skill_id: skillId },
      { type: "action-bar", mcp_tool: "list-skill-actions", skill_id: skillId },
      { type: "notes", scope: "skill", skill_id: skillId },
      { type: "markdown", mcp_tool: "get-skill-doc", skill_id: skillId },
    ],
  };
}
```

- [ ] **Step 2: Wire into Browse detail view**

In `apps/dashboard/app/(views)/browse/[skill]/page.tsx`, replace the existing skill detail rendering with `<ConfigPage config={buildDefaultPageConfig(skillId)} />`. Remove the old rendering logic (which may use SkillAutoPage or BrowseBlockStack).

- [ ] **Step 3: Build and verify**

Navigate to Browse → click a skill → should see health + actions + notes + docs rendered by ConfigPage.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/plugin/ConfigPage.tsx apps/dashboard/
git commit -m "feat(dashboard): render Browse skill detail via ConfigPage"
```

---

## Task 8: New block types (health, vault-notes, custom-sources, file-list, data-preview)

**Files:**
- Create: `apps/dashboard/components/blocks/types/HealthBlock.tsx`
- Create: `apps/dashboard/components/blocks/types/VaultNotesBlock.tsx`
- Create: `apps/dashboard/components/blocks/types/CustomSourcesBlock.tsx`
- Create: `apps/dashboard/components/blocks/types/FileListBlock.tsx`
- Create: `apps/dashboard/components/blocks/types/DataPreviewBlock.tsx`
- Modify: `apps/dashboard/lib/blocks/block-resolver.ts`

- [ ] **Step 1: Implement each block type**

Each block follows the existing pattern: receives `BlockProps`, uses `useBlockData` for MCP data, renders inside `BlockShell`. Extract rendering logic from the corresponding SkillAutoPage sections.

- [ ] **Step 2: Register in block-resolver.ts**

Replace the placeholder imports from Task 2 with real components.

- [ ] **Step 3: Build and verify**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/blocks/types/ apps/dashboard/lib/blocks/block-resolver.ts
git commit -m "feat(dashboard): add health, vault-notes, custom-sources, file-list, data-preview block types"
```

---

## Task 9: Batch migration + cleanup

**Files:**
- Create: Multiple `skills/{skill}/augur/pages/*.yaml` files
- Delete: Corresponding `skills/dashboard/pages/{hub}/{slug}/page.tsx` files
- Delete: `apps/dashboard/components/plugin/SkillAutoPage.tsx` (after all consumers migrated)
- Delete: `skills/dashboard/components/DashboardWidget.tsx`
- Delete: `skills/dashboard/components/WidgetVisibilityWrapper.tsx`

- [ ] **Step 1: Identify simple pages for migration**

Pages that are just stat-grid + data-table (no complex state or custom interactions):
- List candidates by reading each page.tsx and classifying as migratable or not

- [ ] **Step 2: Create YAML pages for each candidate**

For each migratable page, create `skills/{skill}/augur/pages/{route}.yaml`.

- [ ] **Step 3: Regenerate and build**

```bash
cd apps/dashboard && pnpm run build:scripts && pnpm run mount-plugins && pnpm run build 2>&1 | tail -10
```

- [ ] **Step 4: Verify each migrated page in browser**

Navigate to each migrated page route, confirm it renders correctly.

- [ ] **Step 5: Delete migrated TSX pages**

Remove each successfully migrated `page.tsx`.

- [ ] **Step 6: Remove SkillAutoPage and legacy components**

After all SkillAutoPage consumers are migrated:
```bash
rm apps/dashboard/components/plugin/SkillAutoPage.tsx
rm skills/dashboard/components/DashboardWidget.tsx
rm skills/dashboard/components/WidgetVisibilityWrapper.tsx
```

Remove all imports of these components.

- [ ] **Step 7: Build and run tests**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -10
cd apps/dashboard && pnpm test 2>&1 | tail -15
```

- [ ] **Step 8: Commit**

```bash
git add -A skills/ apps/dashboard/
git commit -m "feat(dashboard): batch migrate pages to YAML, remove SkillAutoPage + DashboardWidget"
```

---

## Task 10: Final verification

- [ ] **Step 1: Full build**

```bash
cd apps/dashboard && pnpm run build 2>&1 | tail -20
```

- [ ] **Step 2: Run tests**

```bash
cd apps/dashboard && pnpm test 2>&1 | tail -20
```

- [ ] **Step 3: Verify all hub pages load**

Check each hub's tabs render correctly — both YAML and remaining TSX pages.

- [ ] **Step 4: Verify Browse detail**

Navigate to Browse → click 3-4 different skills → ConfigPage renders default layout.

- [ ] **Step 5: Verify Customize button**

On a YAML page, click Customize → add a block → verify it renders → reset to default → verify it restores.

- [ ] **Step 6: Verify dev-only blocks**

Toggle to dev mode → verify dev blocks (assets, config, tools, logs) auto-append.

- [ ] **Step 7: Commit any fixes**

```bash
git add -A && git commit -m "fix(dashboard): address verification issues from config pages migration"
```

---

## Parallelization Notes

Tasks 5 (custom block registry) and 8 (new block types) have no dependency on Task 4 (pilot migration). They depend only on Tasks 1-3. These can be parallelized with Task 4 by separate agents.

Task 6 (Customize button) depends on Tasks 1-2 only. It can run in parallel with Tasks 3-5.

---

## Follow-Up (Out of Scope)

1. **Migrate remaining TSX pages** — Complex pages (quiz, terminal, file-manager) can use `custom` block type or stay as TSX indefinitely.
2. **Remove `/api/skill-meta/[skillId]`** — After SkillAutoPage is fully removed and Browse detail uses ConfigPage.
3. **Block type enrichment** — Improve the 5 new block types (health, vault-notes, etc.) to match or exceed the SkillAutoPage section quality.
