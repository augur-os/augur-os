# Vault Browse Surface Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Augur's legacy dashboard page model with app surfaces, generated capability profiles, operation-mode Browse categories, and dev-only surface diagnostics while preserving runtime-protected vault roots.

**Architecture:** Build a surface inventory and capability-profile model first, then change Browse taxonomy and move extension management into Browse. Only after every current legacy page route is classified and mapped should legacy skill-owned page discovery be frozen and retired.

**Tech Stack:** Next.js App Router, React, TypeScript, Jest/Testing Library, Python indexer scripts, MCP-backed Browse data, existing `src.config.paths` helpers.

**Spec:** `docs/superpowers/specs/2026-04-30-vault-browse-surface-refactor-design.md`

---

## Scope Split

The approved design touches several subsystems. This plan keeps the work shippable by using independent tracks:

- Track 1: dashboard surface inventory and classification.
- Track 2: Browse taxonomy and operation/dev split.
- Track 3: capability profile data model and rendering.
- Track 4: Extensions & Bundles migration from Settings to Browse.
- Track 5: vault journey categories, protected-root indexing, and dry-run migration ledger.
- Track 6: MCP server development inventory.
- Track 7: legacy page authoring freeze.
- Track 8: legacy discovery retirement after inventory reaches zero active legacy routes.

Tracks 1-7 can land before any destructive route deletion. Track 8 must only run after inventory output proves all current legacy routes are classified and migrated.

## File Structure

- `apps/dashboard/lib/surfaces/types.ts` — shared surface inventory types.
- `apps/dashboard/lib/surfaces/classifySurface.ts` — pure route/source classifier.
- `apps/dashboard/lib/surfaces/buildSurfaceInventory.ts` — converts indexed page entries and app route entries into inventory rows.
- `tests/dashboard/surfaces/classifySurface.test.ts` — classifier regression coverage.
- `tests/dashboard/surfaces/buildSurfaceInventory.test.ts` — inventory aggregation coverage.
- `apps/dashboard/lib/browse/types.ts` — Browse category taxonomy and visibility.
- `apps/dashboard/lib/browse/viewModeMapping.ts` — legacy URL/category normalization and index-category routing.
- `apps/dashboard/app/(views)/browse/useBrowseState.ts` — category gating and grouping behavior.
- `tests/dashboard/browse/useBrowseState.test.tsx` — Browse split regressions.
- `apps/dashboard/lib/capabilities/profile.ts` — generated capability profile sections.
- `tests/dashboard/lib/capabilities/profile.test.ts` — profile generation regressions.
- `apps/dashboard/components/shared/BrowseDetailPanel.tsx` and `apps/dashboard/components/browse/SkillDetailTabs.tsx` — render capability profile sections.
- `apps/dashboard/features/extensions-bundles/ExtensionsBundlesPanel.tsx` — Browse-owned extension and bundle management surface moved from Settings.
- `apps/dashboard/features/extensions-bundles/plugins/*` — existing plugin manager submodules moved out of Settings.
- `apps/dashboard/app/settings/tabs/PluginsTab.tsx` — becomes a lightweight link to Browse after the Browse surface exists.
- `src/lib/index/_scanners_structural.py` — vault journey category indexing and legacy page index changes.
- `src/lib/index/unified_indexer.py` — category routing for vault journey aliases and MCP server inventory.
- `skills/rag/augur/tests/test_unified_indexer.py` — indexer regression coverage.
- `apps/dashboard/scripts/validate-no-legacy-pages.ts` — freeze gate for new legacy page authoring.
- `tests/dashboard/scripts/validate-no-legacy-pages.test.ts` — freeze gate coverage.
- `apps/dashboard/lib/plugin-discovery/page-discovery.ts` and `apps/dashboard/scripts/generate-tab-registry.ts` — legacy discovery retirement in the final track.
- `skills/platform-admin/scripts/vault_migration_inventory.py` — dry-run vault root classifier and migration ledger writer.
- `skills/platform-admin/augur/tests/test_vault_migration_inventory.py` — protected-root and legacy-root migration coverage.

---

### Task 1: Add Dashboard Surface Classification

**Files:**
- Create: `apps/dashboard/lib/surfaces/types.ts`
- Create: `apps/dashboard/lib/surfaces/classifySurface.ts`
- Create: `tests/dashboard/surfaces/classifySurface.test.ts`

- [ ] **Step 1: Write the failing classifier tests**

```ts
import { classifySurface } from "@/lib/surfaces/classifySurface";

describe("classifySurface", () => {
  it("classifies feature routes as app surfaces", () => {
    expect(classifySurface({
      route: "/brain/ingest/inbox",
      sourcePath: "apps/dashboard/features/pages/brain/inbox/page.tsx",
      pageType: "custom",
      devOnly: false,
    })).toEqual({
      surfaceClass: "app_surface",
      implementation: "custom",
      legacy: false,
      recommendedAction: "keep_app_surface",
    });
  });

  it("classifies skill dashboard pages as legacy app-surface candidates", () => {
    expect(classifySurface({
      route: "/command/plugin-pack",
      sourcePath: "skills/plugin-pack/augur/dashboard/page.tsx",
      pageType: "custom",
      devOnly: false,
    })).toEqual({
      surfaceClass: "app_surface",
      implementation: "legacy_skill_dashboard",
      legacy: true,
      recommendedAction: "classify_for_migration",
    });
  });

  it("classifies standalone YAML pages as capability profile section candidates", () => {
    expect(classifySurface({
      route: "/brain/obsidian/vault",
      sourcePath: "/Users/example/Projects/Au-vault/skills/obsidian/augur/pages/vault.yaml",
      pageType: "yaml",
      devOnly: false,
    })).toEqual({
      surfaceClass: "capability_profile",
      implementation: "legacy_standalone_yaml",
      legacy: true,
      recommendedAction: "convert_profile_section",
    });
  });

  it("keeps dev-only route inventory as developer surfaces", () => {
    expect(classifySurface({
      route: "/brain/ai/agents",
      sourcePath: "apps/dashboard/features/pages/brain/agents/page.tsx",
      pageType: "custom",
      devOnly: true,
    })).toEqual({
      surfaceClass: "developer_surface",
      implementation: "custom",
      legacy: false,
      recommendedAction: "keep_dev_surface",
    });
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/surfaces/classifySurface.test.ts --runInBand
```

Expected: FAIL because `@/lib/surfaces/classifySurface` does not exist.

- [ ] **Step 3: Add shared surface types**

Create `apps/dashboard/lib/surfaces/types.ts`:

```ts
export type DashboardSurfaceClass =
  | "app_surface"
  | "capability_profile"
  | "developer_surface";

export type DashboardSurfaceImplementation =
  | "custom"
  | "config"
  | "generated_profile"
  | "legacy_skill_dashboard"
  | "legacy_standalone_yaml"
  | "legacy_auto_page"
  | "unknown";

export type DashboardSurfaceAction =
  | "keep_app_surface"
  | "keep_dev_surface"
  | "convert_profile_section"
  | "classify_for_migration"
  | "delete_after_inventory";

export interface SurfaceClassificationInput {
  route: string;
  sourcePath: string;
  pageType?: string;
  devOnly?: boolean;
}

export interface SurfaceClassification {
  surfaceClass: DashboardSurfaceClass;
  implementation: DashboardSurfaceImplementation;
  legacy: boolean;
  recommendedAction: DashboardSurfaceAction;
}
```

- [ ] **Step 4: Add the classifier implementation**

Create `apps/dashboard/lib/surfaces/classifySurface.ts`:

```ts
import type {
  SurfaceClassification,
  SurfaceClassificationInput,
} from "./types";

function normalizedPath(path: string): string {
  return path.replace(/\\/g, "/");
}

export function classifySurface(input: SurfaceClassificationInput): SurfaceClassification {
  const sourcePath = normalizedPath(input.sourcePath || "");
  const pageType = String(input.pageType || "").toLowerCase();

  if (input.devOnly) {
    return {
      surfaceClass: "developer_surface",
      implementation: pageType === "yaml" ? "config" : "custom",
      legacy: false,
      recommendedAction: "keep_dev_surface",
    };
  }

  if (sourcePath.includes("/augur/dashboard/") || sourcePath.includes("skills/") && sourcePath.includes("augur/dashboard")) {
    return {
      surfaceClass: "app_surface",
      implementation: "legacy_skill_dashboard",
      legacy: true,
      recommendedAction: "classify_for_migration",
    };
  }

  if (sourcePath.includes("/augur/pages/") || pageType === "yaml") {
    return {
      surfaceClass: "capability_profile",
      implementation: "legacy_standalone_yaml",
      legacy: true,
      recommendedAction: "convert_profile_section",
    };
  }

  if (pageType === "auto") {
    return {
      surfaceClass: "capability_profile",
      implementation: "legacy_auto_page",
      legacy: true,
      recommendedAction: "convert_profile_section",
    };
  }

  if (sourcePath.startsWith("apps/dashboard/features/pages/") || sourcePath.includes("/apps/dashboard/features/pages/")) {
    return {
      surfaceClass: "app_surface",
      implementation: "custom",
      legacy: false,
      recommendedAction: "keep_app_surface",
    };
  }

  return {
    surfaceClass: "developer_surface",
    implementation: "unknown",
    legacy: true,
    recommendedAction: "classify_for_migration",
  };
}
```

- [ ] **Step 5: Run the classifier tests**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/surfaces/classifySurface.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/surfaces/types.ts apps/dashboard/lib/surfaces/classifySurface.ts tests/dashboard/surfaces/classifySurface.test.ts
git commit -m "feat(dashboard): classify dashboard surfaces"
```

---

### Task 2: Build Surface Inventory From Indexed Pages

**Files:**
- Create: `apps/dashboard/lib/surfaces/buildSurfaceInventory.ts`
- Create: `tests/dashboard/surfaces/buildSurfaceInventory.test.ts`

- [ ] **Step 1: Write the failing inventory tests**

```ts
import { buildSurfaceInventory } from "@/lib/surfaces/buildSurfaceInventory";

describe("buildSurfaceInventory", () => {
  it("adds classification fields to indexed page entries", () => {
    const rows = buildSurfaceInventory([
      {
        route: "/brain/ingest/inbox",
        source_path: "apps/dashboard/features/pages/brain/inbox/page.tsx",
        pageType: "custom",
        hub: "brain",
        skill: "ingest",
        name: "inbox",
        description: "Review watched folders",
      },
      {
        route: "/brain/obsidian/vault",
        source_path: "/Users/example/Projects/Au-vault/skills/obsidian/augur/pages/vault.yaml",
        pageType: "yaml",
        hub: "brain",
        skill: "obsidian",
        name: "vault",
        description: "Obsidian Vault",
      },
    ]);

    expect(rows).toEqual([
      expect.objectContaining({
        route: "/brain/ingest/inbox",
        ownerSkill: "ingest",
        surfaceClass: "app_surface",
        implementation: "custom",
        legacy: false,
        recommendedAction: "keep_app_surface",
      }),
      expect.objectContaining({
        route: "/brain/obsidian/vault",
        ownerSkill: "obsidian",
        surfaceClass: "capability_profile",
        implementation: "legacy_standalone_yaml",
        legacy: true,
        recommendedAction: "convert_profile_section",
      }),
    ]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/surfaces/buildSurfaceInventory.test.ts --runInBand
```

Expected: FAIL because `buildSurfaceInventory` does not exist.

- [ ] **Step 3: Add the inventory builder**

Create `apps/dashboard/lib/surfaces/buildSurfaceInventory.ts`:

```ts
import { classifySurface } from "./classifySurface";
import type {
  DashboardSurfaceAction,
  DashboardSurfaceClass,
  DashboardSurfaceImplementation,
} from "./types";

interface IndexedPageEntry {
  route?: string;
  source_path?: string;
  sourcePath?: string;
  pageType?: string;
  page_type?: string;
  hub?: string;
  skill?: string;
  name?: string;
  description?: string;
  metadata?: Record<string, unknown>;
}

export interface SurfaceInventoryRow {
  route: string;
  ownerSkill: string;
  hub: string;
  name: string;
  description: string;
  sourcePath: string;
  pageType: string;
  surfaceClass: DashboardSurfaceClass;
  implementation: DashboardSurfaceImplementation;
  legacy: boolean;
  recommendedAction: DashboardSurfaceAction;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function buildSurfaceInventory(entries: IndexedPageEntry[]): SurfaceInventoryRow[] {
  return entries.map((entry) => {
    const sourcePath = stringValue(entry.source_path) || stringValue(entry.sourcePath);
    const pageType = stringValue(entry.pageType) || stringValue(entry.page_type) || stringValue(entry.metadata?.pageType);
    const classification = classifySurface({
      route: stringValue(entry.route),
      sourcePath,
      pageType,
      devOnly: stringValue(entry.metadata?.devOnly) === "true",
    });

    return {
      route: stringValue(entry.route),
      ownerSkill: stringValue(entry.skill),
      hub: stringValue(entry.hub),
      name: stringValue(entry.name),
      description: stringValue(entry.description),
      sourcePath,
      pageType,
      ...classification,
    };
  });
}
```

- [ ] **Step 4: Run the inventory tests**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/surfaces/buildSurfaceInventory.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/surfaces/buildSurfaceInventory.ts tests/dashboard/surfaces/buildSurfaceInventory.test.ts
git commit -m "feat(dashboard): build surface inventory"
```

---

### Task 3: Implement The Operation/Development Browse Taxonomy

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`
- Create: `apps/dashboard/lib/browse/viewModeMapping.ts`
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: `tests/dashboard/browse/useBrowseState.test.tsx`

- [ ] **Step 1: Add failing Browse split tests**

Append this test to `tests/dashboard/browse/useBrowseState.test.tsx`:

```tsx
it("shows the operation-first Browse categories in operation mode", async () => {
  mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
    selector({ mode: "operation" }),
  );

  const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
  const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

  await waitFor(() => {
    expect(result.current.visibleCategories.map((category) => category.id)).toEqual([
      "inbox",
      "notes",
      "sources",
      "wiki",
      "skills",
      "actions",
      "prompts",
      "integrations",
      "extensions-bundles",
      "scheduled-executions",
      "drafts",
      "archive",
    ]);
  });
});

it("moves commands, profiles, workflow definitions, MCP servers, and dashboard surfaces to development mode", async () => {
  localStorage.setItem("augur:browse:view", "dashboard-surfaces");
  mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
    selector({ mode: "development" }),
  );

  const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
  const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

  await waitFor(() => {
    expect(result.current.visibleCategories.map((category) => category.id)).toEqual(
      expect.arrayContaining([
        "dashboard-surfaces",
        "agent-profiles",
        "workflow-definitions",
        "commands",
        "mcp-servers",
        "mcp-tools",
        "system-metadata",
      ]),
    );
    expect(result.current.activeCategory.label).toBe("Dashboard Surfaces");
  });
});

it("normalizes legacy Browse URLs to the new taxonomy", async () => {
  mockSearchParams.set("category", "pages");
  mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
    selector({ mode: "development" }),
  );

  const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
  const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

  await waitFor(() => {
    expect(result.current.effectiveViewMode).toBe("dashboard-surfaces");
    expect(result.current.activeCategory.label).toBe("Dashboard Surfaces");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/browse/useBrowseState.test.tsx --runInBand
```

Expected: FAIL because the new Browse category IDs and URL normalization do not exist.

- [ ] **Step 3: Replace the Browse category taxonomy**

In `apps/dashboard/lib/browse/types.ts`, replace `ViewMode` with:

```ts
export type ViewMode =
  | "inbox"
  | "notes"
  | "sources"
  | "wiki"
  | "skills"
  | "actions"
  | "prompts"
  | "integrations"
  | "extensions-bundles"
  | "scheduled-executions"
  | "drafts"
  | "archive"
  | "dashboard-surfaces"
  | "agent-profiles"
  | "workflow-definitions"
  | "commands"
  | "mcp-servers"
  | "mcp-tools"
  | "api-routes"
  | "scripts"
  | "tests"
  | "logs"
  | "system-metadata";
```

Replace `BROWSE_CATEGORIES` with:

```ts
export const BROWSE_CATEGORIES: BrowseCategory[] = [
  { id: "inbox", label: "Inbox", singularLabel: "Inbox Item", icon: "Inbox", devOnly: false, group: "content" },
  { id: "notes", label: "Notes", singularLabel: "Note", icon: "BookOpen", devOnly: false, group: "content" },
  { id: "sources", label: "Sources", singularLabel: "Source", icon: "FileSearch", devOnly: false, group: "content" },
  { id: "wiki", label: "Wiki", singularLabel: "Wiki Page", icon: "NotebookTabs", devOnly: false, group: "content" },
  { id: "skills", label: "Skills", singularLabel: "Skill", icon: "Puzzle", devOnly: false, group: "content" },
  { id: "actions", label: "Actions", singularLabel: "Action", icon: "Zap", devOnly: false, group: "content" },
  { id: "prompts", label: "Prompts", singularLabel: "Prompt", icon: "MessageSquare", devOnly: false, group: "content" },
  { id: "integrations", label: "Integrations", singularLabel: "Integration", icon: "Plug", devOnly: false, group: "system" },
  { id: "extensions-bundles", label: "Extensions & Bundles", singularLabel: "Extension", icon: "Package", devOnly: false, group: "system" },
  { id: "scheduled-executions", label: "Scheduled Executions", singularLabel: "Scheduled Execution", icon: "Clock3", devOnly: false, group: "system", viewLayout: "table" },
  { id: "drafts", label: "Drafts", singularLabel: "Draft", icon: "FilePenLine", devOnly: false, group: "content" },
  { id: "archive", label: "Archive", singularLabel: "Archived Item", icon: "Archive", devOnly: false, group: "content" },
  { id: "dashboard-surfaces", label: "Dashboard Surfaces", singularLabel: "Surface", icon: "PanelsTopLeft", devOnly: true, group: "dev", viewLayout: "table" },
  { id: "agent-profiles", label: "Agent Profiles", singularLabel: "Agent Profile", icon: "Bot", devOnly: true, group: "dev" },
  { id: "workflow-definitions", label: "Workflow Definitions", singularLabel: "Workflow Definition", icon: "GitBranch", devOnly: true, group: "dev" },
  { id: "commands", label: "Commands", singularLabel: "Command", icon: "Terminal", devOnly: true, group: "dev" },
  { id: "mcp-servers", label: "MCP Servers", singularLabel: "MCP Server", icon: "Server", devOnly: true, group: "dev", viewLayout: "table" },
  { id: "mcp-tools", label: "MCP Tools", singularLabel: "Tool", icon: "Wrench", devOnly: true, group: "dev" },
  { id: "api-routes", label: "API Routes", singularLabel: "Route", icon: "Route", devOnly: true, group: "dev", viewLayout: "table" },
  { id: "scripts", label: "Scripts", singularLabel: "Script", icon: "Terminal", devOnly: true, group: "dev" },
  { id: "tests", label: "Tests", singularLabel: "Test", icon: "FlaskConical", devOnly: true, group: "dev" },
  { id: "logs", label: "Logs", singularLabel: "Log", icon: "ScrollText", devOnly: true, group: "dev" },
  { id: "system-metadata", label: "_System Metadata", singularLabel: "Metadata Entry", icon: "Database", devOnly: true, group: "dev", viewLayout: "table" },
];
```

- [ ] **Step 4: Add view-mode normalization and index routing**

Create `apps/dashboard/lib/browse/viewModeMapping.ts`:

```ts
import { BROWSE_CATEGORIES, type ViewMode } from "./types";

const LEGACY_VIEW_MODE_MAP: Record<string, ViewMode> = {
  pages: "dashboard-surfaces",
  vault: "notes",
  documents: "sources",
  agents: "agent-profiles",
  workflows: "workflow-definitions",
};

const VAULT_JOURNEY_MODES = new Set<ViewMode>([
  "inbox",
  "notes",
  "sources",
  "drafts",
  "archive",
  "system-metadata",
]);

export function normalizeRequestedViewMode(value: string | null | undefined): ViewMode | null {
  if (!value) return null;
  const mapped = LEGACY_VIEW_MODE_MAP[value] ?? value;
  const category = BROWSE_CATEGORIES.find((item) => item.id === mapped);
  return category ? category.id : null;
}

export function indexCategoryForViewMode(mode: ViewMode): string {
  if (mode === "dashboard-surfaces") return "pages";
  if (mode === "agent-profiles") return "agents";
  if (mode === "workflow-definitions") return "workflows";
  if (VAULT_JOURNEY_MODES.has(mode)) return "vault";
  return mode;
}

export function itemMatchesViewMode(item: { metadata?: Record<string, string> }, mode: ViewMode): boolean {
  if (!VAULT_JOURNEY_MODES.has(mode)) return true;
  return item.metadata?.journey_category === mode;
}
```

- [ ] **Step 5: Use the mapping in Browse state**

In `apps/dashboard/app/(views)/browse/useBrowseState.ts`, import:

```ts
import {
  indexCategoryForViewMode,
  itemMatchesViewMode,
  normalizeRequestedViewMode,
} from "@/lib/browse/viewModeMapping";
```

In `readViewMode`, replace direct category lookup with:

```ts
const normalized = normalizeRequestedViewMode(stored);
if (!normalized) return "skills";
const category = BROWSE_CATEGORIES.find((c) => c.id === normalized);
if (!category) return "skills";
if (category.devOnly && !isDev) return "skills";
return category.id;
```

In `readUrlViewMode`, replace direct category lookup with:

```ts
const normalized = normalizeRequestedViewMode(value);
if (!normalized) return null;
const category = BROWSE_CATEGORIES.find((c) => c.id === normalized);
if (!category) return null;
if (category.devOnly && !isDev) return null;
return category.id;
```

Before the `useMcpQuery` call, add:

```ts
const indexCategory = indexCategoryForViewMode(effectiveViewMode);
```

Change the query key and args to:

```ts
["browse-index", indexCategory, debouncedSearch],
"browse-index",
"config",
{
  args: {
    category: indexCategory,
    ...(debouncedSearch ? { search: debouncedSearch } : {}),
  },
},
```

In `rawItems`, transform with the index category and filter by the visible journey mode:

```ts
const rawItems = useMemo<BrowseItem[]>(() => {
  if (isPageFallback) {
    return transformPages(allPages);
  }
  if (!indexData?.items) return [];
  return indexData.items
    .map((entry) => transformIndexEntry(entry as Record<string, any>, indexCategory))
    .filter((item) => itemMatchesViewMode(item, effectiveViewMode));
}, [isPageFallback, allPages, indexData, indexCategory, effectiveViewMode]);
```

Update page fallback detection:

```ts
const isPageFallback = effectiveViewMode === "dashboard-surfaces" && (!indexData?.items?.length || notIndexed);
```

- [ ] **Step 6: Run the Browse state tests**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/browse/useBrowseState.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/viewModeMapping.ts apps/dashboard/app/\(views\)/browse/useBrowseState.ts tests/dashboard/browse/useBrowseState.test.tsx
git commit -m "feat(browse): split operation and development categories"
```

---

### Task 4: Add Generated Capability Profile Sections

**Files:**
- Create: `apps/dashboard/lib/capabilities/profile.ts`
- Create: `tests/dashboard/lib/capabilities/profile.test.ts`
- Modify: `apps/dashboard/lib/browse/types.ts`
- Modify: `apps/dashboard/lib/browse/useSkillDetail.ts`

- [ ] **Step 1: Write failing capability profile tests**

```ts
import { buildCapabilityProfileSections } from "@/lib/capabilities/profile";

describe("buildCapabilityProfileSections", () => {
  it("creates sections from tools, actions, prompts, commands, docs, and health", () => {
    const sections = buildCapabilityProfileSections({
      skillId: "gmail-triage",
      description: "Triage Gmail messages.",
      tools: [{ name: "gmail-search", description: "Search Gmail" }],
      actions: [{ id: "triage", label: "Triage Inbox", description: "Rank inbox", dispatch: "mcp" }],
      prompts: [{ id: "reply-draft", label: "Draft Reply", prompt: "Draft a reply" }],
      commands: [{ id: "gmail-triage", label: "/gmail-triage", command: "/gmail-triage" }],
      integrations: [{ id: "gmail", label: "Gmail", status: "connected" }],
      docs: "## Gmail Triage\nUse it to rank mail.",
      health: { status: "healthy" },
    });

    expect(sections.map((section) => section.id)).toEqual([
      "summary",
      "tools",
      "actions",
      "prompts",
      "commands",
      "integrations",
      "docs",
      "health",
    ]);
  });

  it("omits empty sections but keeps summary", () => {
    const sections = buildCapabilityProfileSections({
      skillId: "empty",
      description: "Empty skill",
    });

    expect(sections).toEqual([
      {
        id: "summary",
        title: "Summary",
        kind: "summary",
        items: [{ label: "empty", description: "Empty skill" }],
      },
    ]);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/lib/capabilities/profile.test.ts --runInBand
```

Expected: FAIL because the profile builder does not exist.

- [ ] **Step 3: Add capability profile types to Browse types**

In `apps/dashboard/lib/browse/types.ts`, add:

```ts
export type CapabilityProfileSectionKind =
  | "summary"
  | "tools"
  | "actions"
  | "prompts"
  | "commands"
  | "integrations"
  | "docs"
  | "health";

export interface CapabilityProfileItem {
  label: string;
  description?: string;
  metadata?: Record<string, string>;
}

export interface CapabilityProfileSection {
  id: string;
  title: string;
  kind: CapabilityProfileSectionKind;
  items: CapabilityProfileItem[];
}
```

Add this field to `SkillDetail`:

```ts
capabilityProfileSections?: CapabilityProfileSection[];
```

- [ ] **Step 4: Add the capability profile builder**

Create `apps/dashboard/lib/capabilities/profile.ts`:

```ts
import type {
  CapabilityProfileItem,
  CapabilityProfileSection,
  SkillAction,
  SkillCommand,
  SkillPrompt,
} from "@/lib/browse/types";

interface CapabilityTool {
  name: string;
  description?: string;
}

interface CapabilityIntegration {
  id: string;
  label: string;
  status?: string;
}

export interface BuildCapabilityProfileInput {
  skillId: string;
  description: string;
  tools?: CapabilityTool[];
  actions?: SkillAction[];
  prompts?: SkillPrompt[];
  commands?: SkillCommand[];
  integrations?: CapabilityIntegration[];
  docs?: string;
  health?: { status: string; lastCheck?: string; errors24h?: number };
}

function section(
  id: CapabilityProfileSection["id"],
  title: string,
  kind: CapabilityProfileSection["kind"],
  items: CapabilityProfileItem[],
): CapabilityProfileSection | null {
  return items.length > 0 ? { id, title, kind, items } : null;
}

function compact(sections: Array<CapabilityProfileSection | null>): CapabilityProfileSection[] {
  return sections.filter((item): item is CapabilityProfileSection => item !== null);
}

export function buildCapabilityProfileSections(input: BuildCapabilityProfileInput): CapabilityProfileSection[] {
  return compact([
    section("summary", "Summary", "summary", [
      { label: input.skillId, description: input.description },
    ]),
    section("tools", "Tools", "tools", (input.tools ?? []).map((tool) => ({
      label: tool.name,
      description: tool.description,
    }))),
    section("actions", "Actions", "actions", (input.actions ?? []).map((action) => ({
      label: action.label,
      description: action.description,
      metadata: { dispatch: action.dispatch },
    }))),
    section("prompts", "Prompts", "prompts", (input.prompts ?? []).map((prompt) => ({
      label: prompt.label,
      description: prompt.description || prompt.prompt,
    }))),
    section("commands", "Commands", "commands", (input.commands ?? []).map((command) => ({
      label: command.label,
      description: command.description || command.command,
    }))),
    section("integrations", "Integrations", "integrations", (input.integrations ?? []).map((integration) => ({
      label: integration.label,
      description: integration.status,
      metadata: { id: integration.id },
    }))),
    section("docs", "Docs", "docs", input.docs ? [{ label: "Skill Documentation", description: input.docs }] : []),
    section("health", "Health", "health", input.health ? [{
      label: input.health.status,
      description: input.health.lastCheck,
      metadata: input.health.errors24h != null ? { errors24h: String(input.health.errors24h) } : undefined,
    }] : []),
  ]);
}
```

- [ ] **Step 5: Wire profile sections into `useSkillDetail`**

In `apps/dashboard/lib/browse/useSkillDetail.ts`, import:

```ts
import { buildCapabilityProfileSections } from "@/lib/capabilities/profile";
```

Inside the returned `detail` object, add:

```ts
capabilityProfileSections: buildCapabilityProfileSections({
  skillId,
  description: data.skill.description,
  actions: data.actions ?? [],
  prompts: data.prompts ?? [],
  commands: data.commands ?? [],
  docs: data.skillDoc?.skillDoc,
  health: data.health,
}),
```

- [ ] **Step 6: Run capability and skill detail tests**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/lib/capabilities/profile.test.ts ../../tests/dashboard/browse/useSkillDetail.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/lib/capabilities/profile.ts apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/useSkillDetail.ts tests/dashboard/lib/capabilities/profile.test.ts
git commit -m "feat(browse): generate capability profile sections"
```

---

### Task 5: Render Capability Profiles In Skill Detail

**Files:**
- Modify: `apps/dashboard/components/browse/SkillDetailTabs.tsx`
- Modify: `tests/dashboard/browse/SkillDetailTabs.test.tsx`

- [ ] **Step 1: Add a failing render test**

Append this test to `tests/dashboard/browse/SkillDetailTabs.test.tsx`:

```tsx
it("renders generated capability profile sections", () => {
  render(
    <SkillDetailTabs
      detail={{
        skillId: "gmail-triage",
        hub: "brain",
        title: "Gmail Triage",
        icon: "Mail",
        description: "Triage Gmail messages",
        blocks: [],
        actions: [],
        prompts: [],
        commands: [],
        capabilityProfileSections: [
          {
            id: "integrations",
            title: "Integrations",
            kind: "integrations",
            items: [{ label: "Gmail", description: "connected" }],
          },
        ],
      }}
    />,
  );

  expect(screen.getByText("Integrations")).toBeInTheDocument();
  expect(screen.getByText("Gmail")).toBeInTheDocument();
  expect(screen.getByText("connected")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/browse/SkillDetailTabs.test.tsx --runInBand
```

Expected: FAIL because profile sections are not rendered.

- [ ] **Step 3: Add profile section rendering**

In `apps/dashboard/components/browse/SkillDetailTabs.tsx`, render `detail.capabilityProfileSections` in the overview tab after the summary block:

```tsx
{detail.capabilityProfileSections?.map((section) => (
  <section key={section.id} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]/40 p-3">
    <h4 className="text-sm font-semibold text-[var(--text-primary)]">{section.title}</h4>
    <div className="mt-2 space-y-2">
      {section.items.map((item) => (
        <div key={`${section.id}-${item.label}`} className="rounded-md bg-[var(--bg-card)]/70 p-2">
          <div className="text-sm font-medium text-[var(--text-primary)]">{item.label}</div>
          {item.description ? (
            <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{item.description}</div>
          ) : null}
        </div>
      ))}
    </div>
  </section>
))}
```

- [ ] **Step 4: Run the SkillDetailTabs test**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/browse/SkillDetailTabs.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/browse/SkillDetailTabs.tsx tests/dashboard/browse/SkillDetailTabs.test.tsx
git commit -m "feat(browse): render capability profile sections"
```

---

### Task 6: Move Extensions And Bundles Into Browse

**Files:**
- Create: `apps/dashboard/features/extensions-bundles/ExtensionsBundlesPanel.tsx`
- Move plugin manager helpers into `apps/dashboard/features/extensions-bundles/plugins/*`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`
- Modify: `apps/dashboard/app/settings/tabs/PluginsTab.tsx`
- Modify: `tests/dashboard/browse/BrowseLayout.test.tsx`

- [ ] **Step 1: Add failing Browse layout test**

Add this test to `tests/dashboard/browse/BrowseLayout.test.tsx`:

```tsx
it("renders Extensions & Bundles as a Browse category", async () => {
  mockUseBrowseState.mockReturnValue({
    ...baseBrowseState,
    effectiveViewMode: "extensions-bundles",
    activeCategory: { id: "extensions-bundles", label: "Extensions & Bundles", singularLabel: "Extension", icon: "Package", devOnly: false, group: "system" },
    visibleCategories: [{ id: "extensions-bundles", label: "Extensions & Bundles", group: "system" }],
    sorted: [],
    filtered: [],
  });

  render(<BrowsePage />);

  expect(await screen.findByText("Extensions & Bundles")).toBeInTheDocument();
  expect(screen.getByText("Install Plugin")).toBeInTheDocument();
  expect(screen.getByText("Enable All")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/browse/BrowseLayout.test.tsx --runInBand
```

Expected: FAIL because the panel is not rendered from Browse.

- [ ] **Step 3: Move the plugin manager submodules out of Settings**

Run:

```bash
mkdir -p apps/dashboard/features/extensions-bundles
git status --short apps/dashboard/features/extensions-bundles/plugins
git status --short apps/dashboard/features/extensions-bundles/RebuildDialog.tsx
```

Expected: the plugin manager helper modules now live under `apps/dashboard/features/extensions-bundles/plugins/`.

- [ ] **Step 4: Move the existing plugin tab implementation into Browse features**

Run:

```bash
git mv apps/dashboard/app/settings/tabs/PluginsTab.tsx apps/dashboard/features/extensions-bundles/ExtensionsBundlesPanel.tsx
```

Then update `apps/dashboard/features/extensions-bundles/ExtensionsBundlesPanel.tsx`:

Replace this import:

```tsx
import RebuildDialog from "../components/RebuildDialog";
```

with:

```tsx
import RebuildDialog from "./RebuildDialog";
```

Replace the exported component declaration:

```tsx
export default function PluginsTab() {
```

with:

```tsx
export default function ExtensionsBundlesPanel() {
```

The edit is intentionally a move plus rename. Do not replace the manager with a static summary; keep the existing install, uninstall, enable, disable, dependency, export, rebuild, and archive controls.

- [ ] **Step 5: Add a lightweight Settings link to the new Browse surface**

Create a new `apps/dashboard/app/settings/tabs/PluginsTab.tsx`:

```tsx
"use client";

import Link from "next/link";
import { PackageOpen } from "lucide-react";

export default function PluginsTab() {
  return (
    <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
      <div className="flex items-center gap-2">
        <PackageOpen className="h-5 w-5 text-[var(--accent-primary)]" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Extensions & Bundles</h2>
      </div>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">
        Bundle management now lives in Browse with the rest of the capability catalog.
      </p>
      <Link
        href="/browse?category=extensions-bundles"
        className="mt-4 inline-flex items-center rounded-md bg-[var(--accent-primary)] px-3 py-2 text-sm font-medium text-[var(--text-on-accent)]"
      >
        Open Extensions & Bundles
      </Link>
    </section>
  );
}
```

- [ ] **Step 6: Render the panel in Browse**

In `apps/dashboard/app/(views)/browse/page.tsx`, import:

```tsx
import ExtensionsBundlesPanel from "@/features/extensions-bundles/ExtensionsBundlesPanel";
```

Before rendering normal results, branch on the active category:

```tsx
{state.effectiveViewMode === "extensions-bundles" ? (
  <ExtensionsBundlesPanel />
) : (
  <BrowseContentGrid
    items={state.sorted}
    visibleCount={state.visibleCount}
    pageSize={state.pageSize}
    onShowMore={() => state.setVisibleCount((count) => count + state.pageSize)}
    onRunMcp={state.handleRunMcp}
    onSelectSkill={state.selectSkill}
    onSelectScheduledExecution={state.selectScheduledExecution}
    viewLayout={state.activeCategory.viewLayout}
    category={state.effectiveViewMode}
  />
)}
```

Keep the existing `BrowseContentGrid` props unchanged at the edit site; only wrap the existing grid branch.

- [ ] **Step 7: Run Browse layout tests**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/browse/BrowseLayout.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/features/extensions-bundles apps/dashboard/app/settings/tabs/PluginsTab.tsx apps/dashboard/app/\(views\)/browse/page.tsx tests/dashboard/browse/BrowseLayout.test.tsx
git commit -m "feat(browse): move extensions and bundles into browse"
```

---

### Task 7: Add Vault Journey Categories To The Index

**Files:**
- Modify: `src/lib/index/_scanners_structural.py`
- Modify: `src/lib/index/unified_indexer.py`
- Modify: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Write failing indexer tests**

Add this test to `skills/rag/augur/tests/test_unified_indexer.py`:

```python
def test_vault_journey_category_from_relative_path(tmp_path):
    from src.lib.index._scanners_structural import _vault_journey_category

    assert _vault_journey_category(tmp_path / "vault" / "inbox" / "capture.md", tmp_path / "vault") == "inbox"
    assert _vault_journey_category(tmp_path / "vault" / "notes" / "career" / "plan.md", tmp_path / "vault") == "notes"
    assert _vault_journey_category(tmp_path / "vault" / "sources" / "web" / "source.md", tmp_path / "vault") == "sources"
    assert _vault_journey_category(tmp_path / "vault" / "wiki" / "overview.md", tmp_path / "vault") == "wiki"
    assert _vault_journey_category(tmp_path / "vault" / "_drafts" / "staging" / "item.md", tmp_path / "vault") == "drafts"
    assert _vault_journey_category(tmp_path / "vault" / "archive" / "old.md", tmp_path / "vault") == "archive"
    assert _vault_journey_category(tmp_path / "vault" / "_system" / "migrations" / "ledger.md", tmp_path / "vault") == "system-metadata"
    assert _vault_journey_category(tmp_path / "vault" / "skills" / "apple" / "SKILL.md", tmp_path / "vault") == "skills"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -q
```

Expected: FAIL because `_vault_journey_category` does not exist.

- [ ] **Step 3: Add the helper**

In `src/lib/index/_scanners_structural.py`, before `index_vault`, add:

```python
def _vault_journey_category(vault_file: Path, vault_dir: Path) -> str:
    """Return the operation-mode Browse journey bucket for a vault file."""
    try:
        rel = vault_file.relative_to(vault_dir)
    except ValueError:
        return "other"
    if not rel.parts:
        return "other"
    root = rel.parts[0]
    if root == "_drafts":
        return "drafts"
    if root == "_system":
        return "system-metadata"
    if root in {"inbox", "notes", "sources", "wiki", "archive", "skills", "memory"}:
        return root
    return "other"
```

- [ ] **Step 4: Include journey category in vault index entries**

In `index_vault`, add this field to `entry_meta`:

```python
"journey_category": _vault_journey_category(vault_file, vault_dir),
```

- [ ] **Step 5: Run indexer tests**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -q
```

Expected: PASS.

- [ ] **Step 6: Reindex vault locally**

Run:

```bash
python3 src/lib/index/unified_indexer.py --category vault
```

Expected output includes `Indexed` and `vault entries`.

- [ ] **Step 7: Commit**

```bash
git add src/lib/index/_scanners_structural.py skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat(index): tag vault journey categories"
```

---

### Task 8: Add A Safe Vault Migration Inventory Ledger

**Files:**
- Create: `skills/platform-admin/scripts/vault_migration_inventory.py`
- Create: `skills/platform-admin/augur/tests/test_vault_migration_inventory.py`

- [ ] **Step 1: Write failing vault migration inventory tests**

Create `skills/platform-admin/augur/tests/test_vault_migration_inventory.py`:

```python
from pathlib import Path

from skills.platform_admin.scripts.vault_migration_inventory import (
    classify_vault_path,
    render_migration_ledger,
)


def test_classify_vault_path_preserves_runtime_roots(tmp_path: Path):
    vault = tmp_path / "vault"

    assert classify_vault_path(vault / "skills" / "apple" / "SKILL.md", vault).classification == "protected_runtime_root"
    assert classify_vault_path(vault / "memory" / "index.md", vault).classification == "protected_runtime_root"
    assert classify_vault_path(vault / "wiki" / "overview.md", vault).classification == "protected_runtime_root"
    assert classify_vault_path(vault / "sources" / "web" / "item.md", vault).classification == "protected_runtime_root"
    assert classify_vault_path(vault / "_drafts" / "staging" / "item.md", vault).classification == "protected_runtime_root"


def test_classify_vault_path_marks_legacy_roots_for_review(tmp_path: Path):
    vault = tmp_path / "vault"
    result = classify_vault_path(vault / "career" / "interview.md", vault)

    assert result.classification == "legacy_review_required"
    assert result.suggested_action == "review_for_notes_archive_delete_or_consolidation"
    assert result.suggested_target == "notes/career/interview.md"


def test_render_migration_ledger_uses_frontmatter(tmp_path: Path):
    vault = tmp_path / "vault"
    items = [
        classify_vault_path(vault / "career" / "interview.md", vault),
        classify_vault_path(vault / "skills" / "apple" / "SKILL.md", vault),
    ]

    markdown = render_migration_ledger(items)

    assert markdown.startswith("---\ntitle: Vault Migration Inventory\n")
    assert "| career/interview.md | legacy_review_required | review_for_notes_archive_delete_or_consolidation | notes/career/interview.md |" in markdown
    assert "| skills/apple/SKILL.md | protected_runtime_root | keep_in_place | skills/apple/SKILL.md |" in markdown
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest skills/platform-admin/augur/tests/test_vault_migration_inventory.py -q
```

Expected: FAIL because the inventory script does not exist.

- [ ] **Step 3: Add the inventory script**

Create `skills/platform-admin/scripts/vault_migration_inventory.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.paths import get_vault_dir

PROTECTED_ROOTS = {"skills", "memory", "wiki", "sources", "_drafts"}
USER_ROOTS = {"inbox", "notes", "archive", "_system"}
OBSIDIAN_ROOTS = {".obsidian", ".trash"}


@dataclass(frozen=True)
class VaultMigrationItem:
    relative_path: str
    classification: str
    suggested_action: str
    suggested_target: str


def _relative_path(path: Path, vault_dir: Path) -> Path:
    try:
        return path.relative_to(vault_dir)
    except ValueError:
        return path


def classify_vault_path(path: Path, vault_dir: Path) -> VaultMigrationItem:
    rel = _relative_path(path, vault_dir)
    rel_text = rel.as_posix()
    root = rel.parts[0] if rel.parts else ""

    if root in PROTECTED_ROOTS:
        return VaultMigrationItem(rel_text, "protected_runtime_root", "keep_in_place", rel_text)
    if root in USER_ROOTS:
        return VaultMigrationItem(rel_text, "already_in_target_root", "keep_in_place", rel_text)
    if root in OBSIDIAN_ROOTS or root.startswith("."):
        return VaultMigrationItem(rel_text, "obsidian_system_root", "keep_in_place", rel_text)
    if not path.suffix.lower() == ".md":
        return VaultMigrationItem(rel_text, "non_markdown_review_required", "review_for_archive_or_keep", f"archive/{rel_text}")

    target = Path("notes") / rel
    return VaultMigrationItem(
        rel_text,
        "legacy_review_required",
        "review_for_notes_archive_delete_or_consolidation",
        target.as_posix(),
    )


def render_migration_ledger(items: list[VaultMigrationItem]) -> str:
    lines = [
        "---",
        "title: Vault Migration Inventory",
        "status: draft",
        "type: migration-ledger",
        "---",
        "",
        "# Vault Migration Inventory",
        "",
        "| Path | Classification | Suggested Action | Suggested Target |",
        "| --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| {item.relative_path} | {item.classification} | {item.suggested_action} | {item.suggested_target} |"
        )
    lines.append("")
    return "\n".join(lines)


def collect_inventory(vault_dir: Path) -> list[VaultMigrationItem]:
    return [
        classify_vault_path(path, vault_dir)
        for path in sorted(vault_dir.rglob("*"))
        if path.is_file()
    ]


def main() -> int:
    vault_dir = get_vault_dir()
    ledger = render_migration_ledger(collect_inventory(vault_dir))
    print(ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the inventory tests**

Run:

```bash
uv run pytest skills/platform-admin/augur/tests/test_vault_migration_inventory.py -q
```

Expected: PASS.

- [ ] **Step 5: Generate the dry-run ledger without moving files**

Run:

```bash
python3 skills/platform-admin/scripts/vault_migration_inventory.py > /tmp/augur-vault-migration-inventory.md
```

Expected: `/tmp/augur-vault-migration-inventory.md` contains protected-root `keep_in_place` rows and legacy-root `legacy_review_required` rows. No vault files are moved, archived, consolidated, or deleted in this task.

- [ ] **Step 6: Commit**

```bash
git add skills/platform-admin/scripts/vault_migration_inventory.py skills/platform-admin/augur/tests/test_vault_migration_inventory.py
git commit -m "feat(vault): inventory migration candidates"
```

---

### Task 9: Index MCP Servers For Development Browse

**Files:**
- Modify: `src/lib/index/_scanners_structural.py`
- Modify: `src/lib/index/unified_indexer.py`
- Modify: `apps/dashboard/lib/browse/transforms.ts`
- Modify: `skills/rag/augur/tests/test_unified_indexer.py`

- [ ] **Step 1: Write failing MCP server index tests**

Add this test to `skills/rag/augur/tests/test_unified_indexer.py`:

```python
def test_index_mcp_servers_reads_system_manifest(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "project_tier:\n"
        "  - id: augur-core\n"
        "    description: Core registry\n"
        "    command: python\n"
        "    args: [-m, augur_core]\n"
        "vault_tier:\n"
        "  - id: augur-gmail\n"
        "    description: Gmail bundle\n"
        "    command: python\n"
        "    args: [-m, augur_shared.bundle_server, gmail]\n"
        "    bundle: gmail\n",
        encoding="utf-8",
    )

    assert index_mcp_servers(root, rag_dir) == 2
    core = (rag_dir / "mcp-servers" / "augur-core.md").read_text(encoding="utf-8")
    gmail = (rag_dir / "mcp-servers" / "augur-gmail.md").read_text(encoding="utf-8")
    assert "tier: project-tier" in core
    assert "command: python" in core
    assert "bundle: gmail" in gmail
    assert "tier: vault-tier" in gmail
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -q
```

Expected: FAIL because `index_mcp_servers` does not exist.

- [ ] **Step 3: Add the MCP server scanner**

In `src/lib/index/_scanners_structural.py`, after `index_mcp_tools`, add:

```python
def index_mcp_servers(root: Path, rag_dir: Path) -> int:
    """Index configured MCP servers from config/system/mcp_servers.yaml."""
    import shutil

    manifest = root / "config" / "system" / "mcp_servers.yaml"
    category_dir = rag_dir / "mcp-servers"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    if not manifest.exists():
        return 0

    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    count = 0
    for key, tier in (("project_tier", "project-tier"), ("vault_tier", "vault-tier")):
        servers = data.get(key) or []
        if not isinstance(servers, list):
            continue
        for server in servers:
            if not isinstance(server, dict):
                continue
            server_id = str(server.get("id") or "").strip()
            if not server_id:
                continue
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", server_id).strip("-") or "server"
            args = server.get("args") or []
            args_text = " ".join(str(arg) for arg in args) if isinstance(args, list) else str(args)
            entry_meta = {
                "id": server_id,
                "title": server_id,
                "name": server_id,
                "description": str(server.get("description") or ""),
                "category": "mcp-servers",
                "tier": tier,
                "command": str(server.get("command") or ""),
                "args": args_text,
                "bundle": str(server.get("bundle") or ""),
                "source_path": str(manifest),
                "status": "configured",
                "mtime": _mtime_iso(manifest),
                "checksum": _checksum(manifest),
            }
            body = "\n".join(
                line
                for line in [
                    f"# {server_id}",
                    "",
                    str(server.get("description") or ""),
                    "",
                    f"Tier: {tier}",
                    f"Command: {entry_meta['command']} {args_text}".strip(),
                    f"Bundle: {entry_meta['bundle']}" if entry_meta["bundle"] else "",
                ]
                if line != ""
            )
            _write_entry(category_dir / f"{safe_name}.md", entry_meta, body)
            count += 1
    return count
```

- [ ] **Step 4: Wire `mcp-servers` into the unified indexer**

In `src/lib/index/unified_indexer.py`, add `index_mcp_servers` to the structural scanner import. In `reindex_category`, add:

```python
if category == "mcp-servers":
    return index_mcp_servers(root, rag_dir)
```

In `_INDEX_CATEGORIES`, include `"mcp-servers"` next to `"mcp-tools"`.

- [ ] **Step 5: Add Browse transform support**

In `apps/dashboard/lib/browse/transforms.ts`, add a case for `"mcp-servers"` next to `"mcp-tools"`:

```ts
case "mcp-servers": {
  const id = firstString(entry.id, entry.name, entry.title) || "mcp-server";
  return {
    id,
    title: firstString(entry.title, entry.name, entry.id) || id,
    description: firstString(entry.description, entry.command, entry.args) || "",
    hub: "system",
    icon: "Server",
    typeBadge: firstString(entry.tier) || "mcp-server",
    path: firstString(entry.source_path),
    primaryAction: {
      label: "Open Manifest",
      type: "open-file",
      target: firstString(entry.source_path) || "",
    },
    metadata: {
      tier: firstString(entry.tier) || "",
      command: firstString(entry.command) || "",
      bundle: firstString(entry.bundle) || "",
      status: firstString(entry.status) || "configured",
    },
  };
}
```

- [ ] **Step 6: Run MCP server index verification**

Run:

```bash
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -q
python3 src/lib/index/unified_indexer.py --category mcp-servers
```

Expected: tests pass and the indexer reports configured MCP server entries from `config/system/mcp_servers.yaml`.

- [ ] **Step 7: Commit**

```bash
git add src/lib/index/_scanners_structural.py src/lib/index/unified_indexer.py apps/dashboard/lib/browse/transforms.ts skills/rag/augur/tests/test_unified_indexer.py
git commit -m "feat(browse): index mcp servers"
```

---

### Task 10: Freeze New Legacy Page Authoring

**Files:**
- Create: `apps/dashboard/scripts/validate-no-legacy-pages.ts`
- Create: `tests/dashboard/scripts/validate-no-legacy-pages.test.ts`
- Modify: `package.json` or `apps/dashboard/package.json` if this repo keeps dashboard script commands there.

- [ ] **Step 1: Write failing validation tests**

```ts
import { validateNoLegacyPages } from "@/scripts/validate-no-legacy-pages";

describe("validateNoLegacyPages", () => {
  it("rejects skill-owned dashboard pages", () => {
    const result = validateNoLegacyPages([
      "skills/demo/augur/dashboard/page.tsx",
    ]);

    expect(result.ok).toBe(false);
    expect(result.errors).toEqual([
      "Legacy dashboard page source is not allowed: skills/demo/augur/dashboard/page.tsx",
    ]);
  });

  it("rejects standalone YAML page routes", () => {
    const result = validateNoLegacyPages([
      "skills/demo/augur/pages/overview.yaml",
    ]);

    expect(result.ok).toBe(false);
    expect(result.errors).toEqual([
      "Standalone YAML page route is not allowed: skills/demo/augur/pages/overview.yaml",
    ]);
  });

  it("allows app surfaces and capability metadata", () => {
    const result = validateNoLegacyPages([
      "apps/dashboard/features/pages/brain/inbox/page.tsx",
      "skills/demo/SKILL.md",
      "skills/demo/augur/profile.yaml",
    ]);

    expect(result).toEqual({ ok: true, errors: [] });
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/scripts/validate-no-legacy-pages.test.ts --runInBand
```

Expected: FAIL because the validation script does not exist.

- [ ] **Step 3: Add the validator**

Create `apps/dashboard/scripts/validate-no-legacy-pages.ts`:

```ts
export interface LegacyPageValidationResult {
  ok: boolean;
  errors: string[];
}

export function validateNoLegacyPages(paths: string[]): LegacyPageValidationResult {
  const errors: string[] = [];
  for (const rawPath of paths) {
    const path = rawPath.replace(/\\/g, "/");
    if (/^skills\/[^/]+\/augur\/dashboard\//.test(path)) {
      errors.push(`Legacy dashboard page source is not allowed: ${rawPath}`);
    }
    if (/^skills\/[^/]+\/augur\/pages\/[^/]+\.ya?ml$/.test(path)) {
      errors.push(`Standalone YAML page route is not allowed: ${rawPath}`);
    }
  }
  return { ok: errors.length === 0, errors };
}

if (require.main === module) {
  const result = validateNoLegacyPages(process.argv.slice(2));
  if (!result.ok) {
    for (const error of result.errors) console.error(error);
    process.exit(1);
  }
}
```

- [ ] **Step 4: Run the validator tests**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath ../../tests/dashboard/scripts/validate-no-legacy-pages.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 5: Wire the validator into the existing check script**

If dashboard scripts live in `apps/dashboard/package.json`, add:

```json
"check:no-legacy-pages": "tsx scripts/validate-no-legacy-pages.ts $(git ls-files)"
```

If root scripts own checks, add an equivalent command in root `package.json` that runs the dashboard script through `pnpm --filter dashboard`.

- [ ] **Step 6: Run the validation command**

Run:

```bash
pnpm --filter dashboard run check:no-legacy-pages
```

Expected: initially FAIL while legacy files still exist. If existing legacy files are expected during migration, adjust the script invocation to read only newly changed files in CI and keep a separate full-report mode for the migration inventory.

- [ ] **Step 7: Commit**

```bash
git add apps/dashboard/scripts/validate-no-legacy-pages.ts tests/dashboard/scripts/validate-no-legacy-pages.test.ts apps/dashboard/package.json package.json
git commit -m "test(dashboard): block new legacy page sources"
```

---

### Task 11: Retire Legacy Discovery After Inventory Is Clean

**Files:**
- Modify: `apps/dashboard/lib/plugin-discovery/page-discovery.ts`
- Modify: `apps/dashboard/scripts/generate-tab-registry.ts`
- Modify: `src/lib/index/_scanners_structural.py`
- Modify: relevant tests from `tests/dashboard/scripts/`, `tests/dashboard/browse/`, and `skills/rag/augur/tests/`.

- [ ] **Step 1: Generate and inspect the surface inventory**

Run the inventory command added in earlier tasks or run the existing pages index:

```bash
python3 src/lib/index/unified_indexer.py --category pages
```

Expected: every current legacy page has a migration classification of `promote_app_surface`, `convert_capability_profile`, `convert_profile_section`, `move_dev_surface`, or `delete`.

- [ ] **Step 2: Stop scanning `skills/*/augur/dashboard`**

In `apps/dashboard/lib/plugin-discovery/page-discovery.ts`, remove the branch that scans skill-local `augur/dashboard/` directories. Keep scanning:

- `apps/dashboard/features/pages/**`;
- capability profile metadata;
- dev surface registry inputs.

- [ ] **Step 3: Stop treating `augur/pages/*.yaml` as standalone routes**

In `apps/dashboard/lib/plugin-discovery/page-discovery.ts`, remove the `yamlPagesDir` route-discovery branch. YAML profile metadata should be consumed by the capability profile renderer instead.

- [ ] **Step 4: Remove `autoPages` route generation**

In `apps/dashboard/scripts/generate-tab-registry.ts`, remove the generation of `autoPages` route tabs. App surfaces should come from app route files; capability profiles should be linked through skill detail routes.

- [ ] **Step 5: Update page indexing to index app/developer surfaces only**

In `src/lib/index/_scanners_structural.py`, replace `index_pages` output semantics with dashboard surface registry entries. It should include app surfaces and developer surfaces, not legacy skill page declarations.

- [ ] **Step 6: Run full dashboard generation and tests**

Run:

```bash
pnpm --filter dashboard run mount-plugins
pnpm --filter dashboard test -- tests/dashboard/browse tests/dashboard/scripts --runInBand
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -q
```

Expected: all pass.

- [ ] **Step 7: Browser verify affected routes**

Use the dashboard slash-command flow for rebuild/debug if the dev server is stale. Verify representative routes in a real browser:

- `/browse?category=skills`
- `/browse?category=dashboard-surfaces` in development mode
- `/brain/ingest/inbox`
- `/brain/knowledge/memory`

Expected: pages load to interactive state with no chunk-load boundary.

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/lib/plugin-discovery/page-discovery.ts apps/dashboard/scripts/generate-tab-registry.ts src/lib/index/_scanners_structural.py tests/dashboard skills/rag/augur/tests/test_unified_indexer.py
git commit -m "refactor(dashboard): retire legacy page discovery"
```

---

## Final Verification

Run these after all tasks in the current implementation slice:

```bash
pnpm --filter dashboard run typecheck
pnpm --filter dashboard test -- tests/dashboard/browse tests/dashboard/surfaces tests/dashboard/lib/capabilities tests/dashboard/scripts --runInBand
uv run pytest skills/rag/augur/tests/test_unified_indexer.py -q
uv run pytest skills/platform-admin/augur/tests/test_vault_migration_inventory.py -q
python3 src/lib/index/unified_indexer.py --category mcp-servers
python3 skills/platform-admin/scripts/vault_migration_inventory.py > /tmp/augur-vault-migration-inventory.md
git diff --check
```

For UI-touching tasks, also verify in a real browser because dashboard chunk manifests can drift:

- `/browse?category=skills`
- `/browse?category=extensions-bundles`
- `/browse?category=dashboard-surfaces` in development mode
- `/browse?category=mcp-servers` in development mode
- representative Brain app surfaces affected by route changes

Use `/dev-build` and `/dev-debug` rather than manual dev-server cleanup when the dashboard server is stale.
