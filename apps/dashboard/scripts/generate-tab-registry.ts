// Compiled to scripts/dist/generate-tab-registry.mjs by build-scripts.mjs
/**
 * Generate the Workspace tab registry from skill metadata (ADR-802 Phase 2).
 *
 * The dashboard has exactly one navigable surface — Workspace (`/workspace`).
 * Its tabs are derived from the enriched page contract: skills declare
 * `x-augur-dashboard-pages` as a list of objects ({ route, title, icon, order,
 * keywords }), parsed by the scanner into `config.dashboard_pages`
 * (WorkspacePage[]). There is no hub concept any more — the legacy
 * assembleHubs() + multi-hub filesystem walk has been removed.
 *
 * Determinism guarantees:
 * - The single hub is keyed "workspace"
 * - Tabs sorted by order (numeric, undefined last) then label
 * - No timestamp in output (eliminates daily churn)
 * - Idempotent: identical inputs produce byte-identical output
 *
 * Output:
 *   lib/tabs/generated-registry.ts
 *
 * Sub-modules:
 *   yaml-page-gen.ts — YAML config-driven page wrapper generation
 *   block-registry-gen.ts — custom block component registry generation
 */

import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import {
  scanSkillConfigs,
  discoverPagesFromFilesystem,
  smartLabel,
} from "../lib/plugin-discovery";
import {
  isWorkspaceContributor,
  type WorkspacePage,
} from "../lib/plugin-discovery/scanner";
import type { DiscoveredPage } from "../lib/plugin-discovery";
import type { HubConfig, TabItem } from "../lib/tabs/types";
import { generateYamlPageWrappers } from "./yaml-page-gen";
import { generateCustomBlockRegistry } from "./block-registry-gen";
import { getDashboardRoot } from "./lib/path-utils";

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---------------------------------------------------------------------------
// Workspace surface constants (ADR-802 Phase 2)
//
// Workspace is the single fixed navigable surface. Its identity is hardcoded
// here rather than assembled from hub metadata. These values replicate what the
// prior assembleHubs()-based pipeline produced for the workspace hub.
// ---------------------------------------------------------------------------
const WORKSPACE_HUB_ID = "workspace";
const WORKSPACE_BASE_PATH = "/workspace";
const WORKSPACE_TITLE = "Workspace";
const WORKSPACE_SUBTITLE = "Where you act on your second brain";
const WORKSPACE_ICON = "Brain";
const WORKSPACE_CATEGORY = "personal";
const WORKSPACE_NAV_ORDER = 10;

interface PluginNavSubItemOutput {
  skillId: string;
  label: string;
  icon: string;
  href: string;
  pageCount: number;
}

interface PluginNavItemOutput {
  hubId: string;
  title: string;
  subtitle: string;
  icon: string;
  category: string;
  mode?: string;
  navLabel?: string;
  navRoute?: string;
  navHidden?: boolean;
  navOrder?: number;
  children?: PluginNavSubItemOutput[];
}

/**
 * Validate that a generated tab has all required fields.
 * Returns an error message if invalid, null if valid.
 */
function validateTab(tab: TabItem, hubId: string): string | null {
  if (!tab.id || typeof tab.id !== "string") {
    return `Hub "${hubId}": tab missing required "id" field`;
  }
  if (!tab.label || typeof tab.label !== "string") {
    return `Hub "${hubId}": tab "${tab.id}" missing required "label" field`;
  }
  if (!tab.href || typeof tab.href !== "string") {
    return `Hub "${hubId}": tab "${tab.id}" missing required "href" field`;
  }
  return null;
}

/**
 * Validate a hub config has required fields.
 * Returns an error message if invalid, null if valid.
 */
function validateHubConfig(hubId: string, config: HubConfig): string | null {
  if (!config.title || typeof config.title !== "string") {
    return `Hub "${hubId}": missing required "title" field`;
  }
  if (!config.basePath || typeof config.basePath !== "string") {
    return `Hub "${hubId}": missing required "basePath" field`;
  }
  const hasContent =
    (Array.isArray(config.tabs) && config.tabs.length > 0) ||
    (Array.isArray(config.configPages) && config.configPages.length > 0) ||
    (Array.isArray(config.blocks) && config.blocks.length > 0) ||
    (Array.isArray(config.autoPages) && config.autoPages.length > 0);
  if (!hasContent) {
    return `Hub "${hubId}": no tabs, blocks, or autoPages found`;
  }
  return null;
}

/**
 * Sort tabs by order (numeric ascending, undefined last) then by label.
 * Matches the prior content-tab ordering used by the assembleHubs pipeline.
 */
function compareTabs(a: TabItem, b: TabItem): number {
  if (a.order != null && b.order != null) {
    if (a.order !== b.order) return a.order - b.order;
    return a.label.localeCompare(b.label);
  }
  if (a.order != null) return -1;
  if (b.order != null) return 1;
  return a.label.localeCompare(b.label);
}

/**
 * Generate the Workspace tab registry from skill metadata (ADR-802 Phase 2).
 *
 * Collects skills that declare at least one `/workspace/*` page via
 * `x-augur-dashboard-pages` (attached by the scanner as
 * `config.dashboard_pages`), flattens those pages, and builds a single
 * `workspace` HubConfig whose tabs are the synthetic Overview tab plus one tab
 * per declared page.
 *
 * Exported for reuse from API routes (e.g., POST /api/tabs/customize)
 * without spawning a child process.
 */
export async function generateTabRegistryData(): Promise<{
  registry: Record<string, HubConfig>;
  navItems: PluginNavItemOutput[];
  enabledHubCount: number;
  validationErrors: string[];
  discoveredPages: DiscoveredPage[];
}> {
  console.log("Discovering workspace page metadata...");

  const allConfigs = scanSkillConfigs({ startDir: __dirname });

  // Collect skills that contribute at least one /workspace/* page via the
  // enriched x-augur-dashboard-pages contract (attached by the scanner as
  // config.dashboard_pages). This replaces the legacy assembleHubs() pipeline.
  const workspaceConfigs = allConfigs.filter((sc) =>
    isWorkspaceContributor(sc.config.dashboard_pages ?? []),
  );

  // Flatten the declared pages from every contributing skill.
  const pages: WorkspacePage[] = workspaceConfigs.flatMap(
    (sc) => sc.config.dashboard_pages ?? [],
  );

  console.log(
    `   Workspace contributors: ${workspaceConfigs
      .map((sc) => sc.skill)
      .sort()
      .join(", ")} -> ${pages.length} pages`,
  );

  const validationErrors: string[] = [];

  // Synthetic Overview tab — the workspace root at /workspace.
  const overviewTab: TabItem = {
    id: "overview",
    label: "Overview",
    icon: "LayoutDashboard",
    href: WORKSPACE_BASE_PATH,
  };

  // One tab per declared page. Deduplicate by route (slug) in case two skills
  // declare the same /workspace/* route — first declaration wins.
  const seenRoutes = new Set<string>();
  const pageTabs: TabItem[] = [];
  for (const page of pages) {
    if (page.route === `${WORKSPACE_BASE_PATH}/overview`) continue;
    if (seenRoutes.has(page.route)) continue;
    seenRoutes.add(page.route);

    const tab: TabItem = {
      id: page.slug,
      label: page.title ?? smartLabel(page.slug),
      icon: page.icon ?? "FileText",
      href: page.route,
    };
    if (page.order != null) {
      tab.order = page.order;
    }

    const tabError = validateTab(tab, WORKSPACE_HUB_ID);
    if (tabError) {
      validationErrors.push(tabError);
    }

    pageTabs.push(tab);
  }

  pageTabs.sort(compareTabs);

  const tabs: TabItem[] = [overviewTab, ...pageTabs];

  const hubConfig: HubConfig = {
    title: WORKSPACE_TITLE,
    subtitle: WORKSPACE_SUBTITLE,
    basePath: WORKSPACE_BASE_PATH,
    tabs,
    source: "plugin",
  };

  const hubError = validateHubConfig(WORKSPACE_HUB_ID, hubConfig);
  if (hubError) {
    validationErrors.push(hubError);
  }

  const registry: Record<string, HubConfig> = {
    [WORKSPACE_HUB_ID]: hubConfig,
  };

  // Single nav item for the Workspace surface. Consumed by LayoutConfigModal
  // to map a sidebar section label back to its hub id when persisting nav order.
  const navItems: PluginNavItemOutput[] = [
    {
      hubId: WORKSPACE_HUB_ID,
      title: WORKSPACE_TITLE,
      subtitle: WORKSPACE_SUBTITLE,
      icon: WORKSPACE_ICON,
      category: WORKSPACE_CATEGORY,
      navOrder: WORKSPACE_NAV_ORDER,
    },
  ];

  // Discover filesystem pages (augur/pages/*.yaml configs and custom blocks)
  // purely to feed the YAML page wrapper + custom block generators below.
  // This is NOT used for tab assembly.
  const enabledSkills = new Set(allConfigs.map((sc) => sc.skill));
  const discoveredPages = discoverPagesFromFilesystem({
    startDir: __dirname,
    enabledSkills,
  });

  console.log(`   ${pageTabs.length} workspace page tabs (+ overview)`);

  return {
    registry,
    navItems,
    enabledHubCount: 1,
    validationErrors,
    discoveredPages,
  };
}

/**
 * Write registry data to generated TypeScript files.
 *
 * Writes:
 * - lib/tabs/generated-registry.ts (tab registry, managed hub list, nav items)
 * - lib/tabs/generated-skill-nav.ts (standalone skill nav items)
 *
 * Exported for reuse from API routes.
 */
export async function writeRegistryFiles(
  registry: Record<string, HubConfig>,
  navItems: PluginNavItemOutput[],
  enabledHubCount?: number,
): Promise<void> {
  // Build output with sorted registry keys for deterministic JSON output.
  const sortedRegistryKeys = Object.keys(registry).sort();
  const sortedRegistry: Record<string, HubConfig> = {};
  for (const key of sortedRegistryKeys) {
    sortedRegistry[key] = registry[key];
  }

  const hubCountLabel = enabledHubCount ?? sortedRegistryKeys.length;

  const output = `/**
 * AUTO-GENERATED - DO NOT EDIT
 *
 * Generated by: scripts/generate-tab-registry.ts
 * ADR-802 Phase 2: Workspace tabs from x-augur-dashboard-pages
 *
 * This file contains the tab registry for the single Workspace surface
 * (${hubCountLabel} hub). To update, run: npm run generate-tabs
 */

import type { TabRegistry, PluginNavItem } from './types';

/**
 * Workspace tab registry.
 *
 * ADR-802: Tabs derived from skills' x-augur-dashboard-pages declarations.
 */
export const pluginTabRegistry: TabRegistry = ${JSON.stringify(sortedRegistry, null, 2)};

/**
 * List of plugin-managed hub IDs.
 *
 * ${hubCountLabel} hub (the Workspace surface).
 */
export const pluginManagedHubs: string[] = ${JSON.stringify(
    sortedRegistryKeys,
    null,
    2,
  )};

/**
 * Plugin nav items for the Workspace surface.
 * Consumed by LayoutConfigModal to map sidebar sections to hub ids.
 */
export const pluginNavItems: PluginNavItem[] = ${JSON.stringify(navItems, null, 2)};
`;

  // Write to lib/tabs/generated-registry.ts
  const dashboardRoot = getDashboardRoot(__dirname);
  const outputPath = path.resolve(
    dashboardRoot,
    "lib",
    "tabs",
    "generated-registry.ts",
  );
  await fs.mkdir(path.dirname(outputPath), { recursive: true });

  // Safety: don't overwrite a populated registry with an empty one
  const hubCount = Object.keys(sortedRegistry).length;
  if (hubCount === 0) {
    try {
      const existing = await fs.readFile(outputPath, "utf8");
      if (
        existing.includes("pluginTabRegistry: TabRegistry = {") &&
        !existing.includes("pluginTabRegistry: TabRegistry = {}")
      ) {
        console.log(
          `\n   Skipping write: generated 0 hubs but existing file has entries.`,
        );
        console.log(
          `   This usually means .config files couldn't be read from the current working directory.`,
        );
        console.log(
          `   Run manually from apps/dashboard/: node scripts/dist/generate-tab-registry.mjs`,
        );
        return;
      }
    } catch {
      // File doesn't exist yet, write the empty one
    }
  }

  // Idempotency: skip write if output is identical to existing file
  let registryChanged = true;
  try {
    const existing = await fs.readFile(outputPath, "utf8");
    if (existing === output) {
      console.log(
        `\n   No changes: lib/tabs/generated-registry.ts is already up to date`,
      );
      console.log(`   ${hubCount} workspace hub config (unchanged)`);
      registryChanged = false;
    }
  } catch {
    // File doesn't exist yet, proceed with write
  }

  if (registryChanged) {
    // ADR-187 Phase 4: Atomic write — generate into temp file, then rename.
    const tmpPath = outputPath + ".tmp";
    await fs.writeFile(tmpPath, output, "utf8");
    await fs.rename(tmpPath, outputPath);
    console.log(`\n   Generated: lib/tabs/generated-registry.ts`);
    console.log(`   ${hubCount} workspace hub config written`);
  }

  // --- ADR-177: Tab-to-page validation ---
  // Verify every registered tab href resolves to a real page entry.
  // When a catch-all registry exists, parse its PAGES map to verify the
  // specific slug is registered — not just that the catch-all file exists.
  const appDir = path.resolve(dashboardRoot, "app");
  let tabsRegistered = 0;
  let tabsVerified = 0;
  let tabsOrphan = 0;
  const orphanDetails: string[] = [];

  // Cache parsed catch-all registry PAGES keys per hub
  const catchAllPagesCache = new Map<string, Set<string>>();
  async function getCatchAllPages(hubId: string): Promise<Set<string> | null> {
    if (catchAllPagesCache.has(hubId)) return catchAllPagesCache.get(hubId)!;
    const registryPath = path.join(appDir, hubId, "[[...slug]]", "registry.ts");
    try {
      const content = await fs.readFile(registryPath, "utf8");
      const slugs = new Set<string>();
      // Parse 'slug': () => import(...) entries from PAGES map
      const slugRegex = /^\s+'([^']+)'\s*:\s*\(\)/gm;
      let m;
      while ((m = slugRegex.exec(content)) !== null) {
        slugs.add(m[1]);
      }
      catchAllPagesCache.set(hubId, slugs);
      return slugs;
    } catch {
      catchAllPagesCache.set(hubId, new Set());
      return null; // No catch-all registry
    }
  }

  for (const [hubId, hubConfig] of Object.entries(sortedRegistry)) {
    const allTabs = [...hubConfig.tabs, ...(hubConfig.overflow || []), ...(hubConfig.configPages || [])].flatMap(
      (tab: any) => ('children' in tab && Array.isArray(tab.children)) ? [tab, ...tab.children] : [tab]
    );
    for (const tab of allTabs) {
      tabsRegistered++;

      // For the overview tab (href = basePath), always verified
      if (tab.id === "overview") {
        tabsVerified++;
        continue;
      }

      // Tab href is like /career/pipeline — resolve to src/app/career/pipeline/page.tsx
      const hrefPath = tab.href.replace(/^\//, "");
      const pageTsxPath = path.join(appDir, hrefPath, "page.tsx");
      let verified = false;

      // Check 1: Direct page.tsx exists
      try {
        await fs.stat(pageTsxPath);
        verified = true;
      } catch {
        // Not found — check catch-all registry
      }

      // Check 2: Slug exists in catch-all registry PAGES map
      if (!verified) {
        const catchAllPages = await getCatchAllPages(hubId);
        if (catchAllPages) {
          // Extract slug from href: /career/pipeline -> pipeline
          const slug = hrefPath.replace(`${hubId}/`, "");
          if (catchAllPages.has(slug)) {
            verified = true;
          }
        }
      }

      if (verified) {
        tabsVerified++;
      } else {
        tabsOrphan++;
        orphanDetails.push(
          `   WARNING: Tab "${tab.id}" in hub "${hubId}" -> ${tab.href} has no page entry`,
        );
      }
    }
  }

  if (orphanDetails.length > 0) {
    console.error(`\n   ADR-177 tab-to-page validation:`);
    for (const detail of orphanDetails) {
      console.error(detail);
    }
    console.error(
      `\n   Tab registry: ${tabsRegistered} tabs registered, ${tabsVerified} verified, ${tabsOrphan} orphans`,
    );
    console.error(
      `\n   Build failed: ${tabsOrphan} tab(s) have no corresponding page.tsx. Fix the page_type or remove the tab.`,
    );
    process.exit(1);
  }
  console.log(
    `\n   Tab registry: ${tabsRegistered} tabs registered, ${tabsVerified} verified, 0 orphans`,
  );

  // --- ADR-165: Generate standalone skill nav items ---
  // ADR-802 Phase 2: standalone skill nav (the sidebar "Extensions" section)
  // is no longer assembled from hub metadata. No skill currently opts in, so
  // this is always empty — preserved as a stable empty registry so
  // DynamicSkillsNav renders nothing.
  const skillNavItems: never[] = [];

  const skillNavOutput = `/**
 * AUTO-GENERATED - DO NOT EDIT
 *
 * Generated by: scripts/generate-tab-registry.ts
 * ADR-165: Decentralized Skill Navigation Discovery
 *
 * Standalone skill nav items for the sidebar "Extensions" section.
 * Skills opt in via \`nav: { visible: true }\` in their skill config.
 * To update, run: npm run generate-tabs
 */

import type { SkillNavItem } from './types';

/**
 * Skills that opted into standalone sidebar presence via skill config nav section.
 * Empty array means no skills have opted in — the "Extensions" section won't render.
 */
export const skillNavItems: SkillNavItem[] = ${JSON.stringify(skillNavItems, null, 2)};
`;

  const skillNavOutputPath = path.resolve(
    dashboardRoot,
    "lib",
    "tabs",
    "generated-skill-nav.ts",
  );

  // Idempotency: skip write if output is identical
  try {
    const existingSkillNav = await fs.readFile(skillNavOutputPath, "utf8");
    if (existingSkillNav === skillNavOutput) {
      console.log(
        `   No changes: lib/tabs/generated-skill-nav.ts is already up to date`,
      );
    } else {
      // ADR-187 Phase 4: Atomic write
      const skillNavTmpPath = skillNavOutputPath + ".tmp";
      await fs.writeFile(skillNavTmpPath, skillNavOutput, "utf8");
      await fs.rename(skillNavTmpPath, skillNavOutputPath);
      console.log(
        `   Generated: lib/tabs/generated-skill-nav.ts (${skillNavItems.length} skill nav items)`,
      );
    }
  } catch {
    // File doesn't exist yet — atomic write
    const skillNavTmpPath = skillNavOutputPath + ".tmp";
    await fs.writeFile(skillNavTmpPath, skillNavOutput, "utf8");
    await fs.rename(skillNavTmpPath, skillNavOutputPath);
    console.log(
      `   Generated: lib/tabs/generated-skill-nav.ts (${skillNavItems.length} skill nav items)`,
    );
  }
}

async function main() {
  const { registry, navItems, enabledHubCount, validationErrors, discoveredPages } =
    await generateTabRegistryData();

  if (validationErrors.length > 0) {
    console.warn(
      `\n   WARNING: ${validationErrors.length} validation issue(s) found:`,
    );
    for (const err of validationErrors) {
      console.warn(`   - ${err}`);
    }
  }

  await writeRegistryFiles(registry, navItems, enabledHubCount);

  // Generate wrapper TSX files for YAML config-driven pages
  await generateYamlPageWrappers(discoveredPages, __dirname);

  // Generate custom block component registry
  await generateCustomBlockRegistry(discoveredPages, __dirname);
}

main().catch(console.error);
