/**
 * Plugin Discovery — Page Discovery
 *
 * Filesystem-based page discovery (ADR-218). Walks skill directories
 * to find page.tsx files and config-driven YAML pages, producing
 * DiscoveredPage[] for tab registry generation.
 */

import fsSync from "fs";
import path from "path";
import yaml from "yaml";
import type { DashboardYaml } from "../plugin-schema/types";
import { buildDefaultPageConfig } from "../blocks/build-default-page-config";
import { discoverRepoRoot, getClientSkillDirs } from "./paths";
import {
  resolveHubRole,
  scanSkillConfigs,
} from "./scanner";

interface GeneratedPageConfig {
  title: string;
  icon: string;
  hub: string;
  route: string;
  order?: number;
  blocks: Array<Record<string, unknown>>;
}

// dashboard_pages is now WorkspacePage[] on DashboardYaml — no string[] override needed
type DiscoveryConfig = DashboardYaml & {
  mcp_tools?: string[];
};

/**
 * Resolve the surface (hub) id a skill contributes to from its declared
 * dashboard pages. ADR-802 Phase 2: replaces the removed contributes_to
 * field. The surface id is the first segment of a declared route
 * (e.g. /workspace/rag -> "workspace"). Returns "" when the skill declares
 * no dashboard page.
 */
function resolveSurfaceId(config: DashboardYaml): string {
  const pages = Array.isArray(config.dashboard_pages)
    ? config.dashboard_pages
    : [];
  for (const page of pages) {
    const route = page?.route;
    if (typeof route !== "string") continue;
    const segment = route.trim().replace(/^\/+|\/+$/g, "").split("/")[0];
    if (segment) return segment;
  }
  return "";
}

// =============================================================================
// Filesystem-Based Page Discovery (ADR-218)
// =============================================================================

/** Directories under augur/dashboard/ that are NOT pages */
const SKIP_DIRS = new Set(["components", "tabs", "lib", "hooks", "api"]);

/** Regex matching `import { redirect } from 'next/navigation'` variants. */
const REDIRECT_IMPORT_RE =
  /import\s.*redirect.*from\s+['"]next\/navigation['"]/;

function canonicalPath(entry: string): string {
  try {
    return fsSync.realpathSync(entry);
  } catch {
    return path.resolve(entry);
  }
}

function isWithinDir(candidate: string, root: string): boolean {
  const candidatePath = canonicalPath(candidate);
  const rootPath = canonicalPath(root);
  const relative = path.relative(rootPath, candidatePath);
  return (
    relative === "" ||
    (!!relative && !relative.startsWith("..") && !path.isAbsolute(relative))
  );
}

function isClientSkillSource(skillDir: string, clientSkillRoots: string[]): boolean {
  return clientSkillRoots.some((root) =>
    isWithinDir(skillDir, root),
  );
}

/**
 * Detect whether a page source is a redirect-only stub (ADR-235).
 *
 * A redirect stub imports `redirect()` from next/navigation and contains
 * no JSX return — its only purpose is to redirect elsewhere.
 * These should not appear as tabs in the hub tab bar.
 */
export function isRedirectStub(src: string): boolean {
  if (!REDIRECT_IMPORT_RE.test(src)) return false;
  // A real page returns JSX via `return (` or `return <`.
  // Redirect stubs only call `redirect(...)` with no JSX return.
  return !/return\s*[\s(]*</.test(src);
}

/** Well-known acronyms that should be uppercased in labels */
const ACRONYMS = new Set(["mcp", "ocr", "rag", "api", "cli", "gtm", "ai"]);

/**
 * Convert a kebab-case page ID to a human-readable label.
 * Uppercases known acronyms (MCP, OCR, RAG, etc.).
 */
export function smartLabel(id: string): string {
  return id
    .split(/[-_]/)
    .map((word) =>
      ACRONYMS.has(word.toLowerCase())
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

/** A page discovered from the filesystem */
export interface DiscoveredPage {
  /** Page identifier used for tab IDs/labels (e.g., "loops", "file-manager") */
  pageId: string;
  /** Full route path for the discovered page */
  routePath: string;
  /** Skill directory name */
  skill: string;
  /** Bundle directory name */
  bundle: string;
  /** Hub ID from skill metadata contributes_to */
  hubId: string;
  /** Whether this skill is the hub owner */
  isOwner: boolean;
  /** Optional overrides from contributions.pages in skill metadata */
  overrides: {
    label?: string;
    icon?: string;
    order?: number;
    devOnly?: boolean;
    visible?: boolean;
    page_type?: "custom" | "auto";
  };
  /** True for pages from legacy custom-page mounts — always enabled */
  uiPlugin?: boolean;
  /** Absolute path to .yaml source file (config-driven page) */
  yamlConfig?: string;
  /** Inline generated config for synthetic ConfigPage wrappers */
  generatedConfig?: GeneratedPageConfig;
  /** Absolute path to the owning skill directory when known */
  sourceSkillDir?: string;
  /** Absolute path to the owning source config, usually SKILL.md */
  sourceConfigPath?: string;
}

function normalizeGeneratedBlock(
  rawBlock: Record<string, unknown>,
  skill: string,
): Record<string, unknown> {
  const block = { ...rawBlock };
  const dataSource = block.data_source as Record<string, unknown> | undefined;

  if (block.mcp_tool == null && typeof dataSource?.mcp_tool === "string") {
    block.mcp_tool = dataSource.mcp_tool;
  }

  if (block.skill_id == null && block.scope !== "hub") {
    block.skill_id = skill;
  }

  if (typeof block.search === "boolean") {
    block.search = { enabled: block.search };
  } else if (
    block.search &&
    typeof block.search === "object" &&
    (block.search as Record<string, unknown>).enabled == null
  ) {
    block.search = {
      enabled: true,
      ...(block.search as Record<string, unknown>),
    };
  }

  if (Array.isArray(block.row_actions)) {
    block.row_actions = block.row_actions.map((rawAction) => {
      const action = rawAction as Record<string, unknown>;
      return {
        id: action.id,
        icon: action.icon,
        label: action.label,
        dispatch: action.dispatch,
        ...(action.mcp_tool != null ? { mcp_tool: action.mcp_tool } : {}),
        ...(action.payload_fields != null ? { payload_fields: action.payload_fields } : {}),
        ...(action.static_args != null ? { static_args: action.static_args } : {}),
        ...(action.confirm != null ? { confirm: action.confirm } : {}),
        ...(action.confirm_message != null
          ? { confirm_message: action.confirm_message }
          : {}),
        ...(action.href_template != null
          ? { href_template: action.href_template }
          : {}),
        ...(action.fields != null ? { fields: action.fields } : {}),
        ...(action.refetch != null ? { refetch: action.refetch } : {}),
        ...(action.confirmText != null ? { confirmText: action.confirmText } : {}),
      };
    });
  }

  delete block.data_source;
  return block;
}

function pickSyntheticRootOverrides(
  skill: string,
  config: DiscoveryConfig,
  overrideMap: Map<string, DiscoveredPage["overrides"]>,
): DiscoveredPage["overrides"] {
  const direct = overrideMap.get(skill);
  if (direct) return direct;

  const rawPages = config.contributions?.pages;
  if (!Array.isArray(rawPages) || rawPages.length === 0) return {};

  const match = rawPages.find((page) => {
    const p = page as unknown as Record<string, unknown>;
    return p.id === skill;
  }) as unknown as Record<string, unknown> | undefined;
  const fallback = match || (rawPages[0] as unknown as Record<string, unknown> | undefined);
  if (!fallback) return {};

  return {
    label: fallback.title as string | undefined,
    icon: fallback.icon as string | undefined,
    order: fallback.order as number | undefined,
    page_type: (fallback.page_type as "custom" | "auto") || "custom",
  };
}

function buildSyntheticRootConfig(opts: {
  skill: string;
  hubId: string;
  config: DiscoveryConfig;
  overrides: DiscoveredPage["overrides"];
}): GeneratedPageConfig | null {
  const { skill, hubId, config, overrides } = opts;
  const contributions = config.contributions;
  const rawBlocks = Array.isArray(contributions?.blocks)
    ? (contributions.blocks as unknown as Array<Record<string, unknown>>)
    : [];
  const rawActions = Array.isArray(contributions?.actions)
    ? (contributions.actions as unknown as Array<Record<string, unknown>>)
    : [];
  const dashboardPages = Array.isArray(config.dashboard_pages)
    ? config.dashboard_pages
    : [];
  const hasDashboardPageDeclarations = Object.prototype.hasOwnProperty.call(
    config,
    "dashboard_pages",
  );
  const rootRoutePath = `/${hubId}/${skill}`;

  if (
    hasDashboardPageDeclarations &&
    !dashboardPages.some((p) => p.route === rootRoutePath)
  ) {
    return null;
  }

  if (
    rawBlocks.length === 0 &&
    rawActions.length === 0 &&
    dashboardPages.length === 0 &&
    !contributions?.pages
  ) {
    return null;
  }

  if (rawBlocks.length === 0 && rawActions.length === 0) {
    return buildDefaultPageConfig(skill, {
      title: overrides.label || config.hub?.title || smartLabel(skill),
      icon: overrides.icon || config.hub?.icon || "LayoutDashboard",
      hub: hubId,
      mcpTools: config.mcp_tools,
    }) as unknown as GeneratedPageConfig;
  }

  const blocks = rawBlocks.map((block) => normalizeGeneratedBlock(block, skill));
  const hasActionBar = blocks.some((block) => block.type === "action-bar");
  if (!hasActionBar && rawActions.length > 0) {
    blocks.push({
      type: "action-bar",
      mcp_tool: "list-skill-actions",
      skill_id: skill,
    });
  }

  if (blocks.length === 0) {
    return null;
  }

  return {
    title: overrides.label || config.hub?.title || smartLabel(skill),
    icon: overrides.icon || config.hub?.icon || "LayoutDashboard",
    hub: hubId,
    route: skill,
    ...(overrides.order != null ? { order: overrides.order } : {}),
    blocks,
  };
}

/**
 * Build an override map from contributions.pages (supports both array and map formats).
 */
function buildOverrideMap(
  rawPages: unknown,
): Map<string, DiscoveredPage["overrides"]> {
  const overrideMap = new Map<string, DiscoveredPage["overrides"]>();

  if (!rawPages) return overrideMap;

  if (Array.isArray(rawPages)) {
    // Old array format: [{id: "loops", label: "Loops", icon: "Activity", order: 10}]
    for (const p of rawPages) {
      const pageOverrides: DiscoveredPage["overrides"] = {};
      if (p.title) pageOverrides.label = p.title;
      if (p.icon) pageOverrides.icon = p.icon;
      if (p.order != null) pageOverrides.order = p.order;
      const pAny = p as unknown as Record<string, unknown>;
      if (pAny.devOnly != null)
        pageOverrides.devOnly = pAny.devOnly as boolean;
      if (pAny.visible != null)
        pageOverrides.visible = pAny.visible as boolean;
      if (pAny.page_type != null)
        pageOverrides.page_type = pAny.page_type as "custom" | "auto";
      overrideMap.set(p.id, pageOverrides);
    }
  } else if (typeof rawPages === "object") {
    // New map format: {loops: {icon: "Activity", order: 10}}
    for (const [pageId, overrides] of Object.entries(
      rawPages as Record<string, Record<string, unknown>>,
    )) {
      const pageOverrides: DiscoveredPage["overrides"] = {};
      if (overrides.label)
        pageOverrides.label = overrides.label as string;
      if (overrides.icon) pageOverrides.icon = overrides.icon as string;
      if (overrides.order != null)
        pageOverrides.order = overrides.order as number;
      if (overrides.devOnly != null)
        pageOverrides.devOnly = overrides.devOnly as boolean;
      if (overrides.visible != null)
        pageOverrides.visible = overrides.visible as boolean;
      if (overrides.page_type != null)
        pageOverrides.page_type = overrides.page_type as "custom" | "auto";
      overrideMap.set(pageId, pageOverrides);
    }
  }

  return overrideMap;
}

/**
 * Discover pages from a skill's augur/dashboard/ directory.
 * Finds root page.tsx, nested page subdirs, and augur/pages/*.yaml configs.
 */
function discoverSkillPages(opts: {
  skill: string;
  skillDir: string;
  bundle: string;
  hubId: string;
  isOwner: boolean;
  config: DashboardYaml;
  configPath: string;
  pages: DiscoveredPage[];
  isClientSkill?: boolean;
}): void {
  const { skill, skillDir, bundle, hubId, isOwner, config, configPath, pages } = opts;

  const overrideMap = buildOverrideMap(config.contributions?.pages);

  // Include skill root page at augur/dashboard/page.tsx when present.
  const dashboardDir = path.join(skillDir, "augur", "dashboard");
  const rootPageTsx = path.join(dashboardDir, "page.tsx");
  if (fsSync.existsSync(rootPageTsx)) {
    try {
      const pageSrc = fsSync.readFileSync(rootPageTsx, "utf8");
      if (!isRedirectStub(pageSrc)) {
        const overrides = overrideMap.get(skill) || {};
        pages.push({
          pageId: skill,
          routePath: `/${hubId}/${skill}`,
          skill,
          bundle,
          hubId,
          isOwner,
          overrides,
          sourceSkillDir: skillDir,
          sourceConfigPath: configPath,
        });
      }
    } catch {
      // If we can't read the root page, include it anyway.
      const overrides = overrideMap.get(skill) || {};
      pages.push({
        pageId: skill,
        routePath: `/${hubId}/${skill}`,
        skill,
        bundle,
        hubId,
        isOwner,
        overrides,
        sourceSkillDir: skillDir,
        sourceConfigPath: configPath,
      });
    }
  }

  // Walk augur/dashboard/*/page.tsx
  let dashboardEntries: fsSync.Dirent[];
  try {
    dashboardEntries = fsSync.readdirSync(dashboardDir, {
      withFileTypes: true,
    });
  } catch {
    dashboardEntries = [];
  }

  dashboardEntries.sort((a, b) => a.name.localeCompare(b.name));

  for (const dirEntry of dashboardEntries) {
    if (!dirEntry.isDirectory()) continue;
    if (dirEntry.name.startsWith(".")) continue;
    if (SKIP_DIRS.has(dirEntry.name)) continue;
    // Skip Next.js dynamic route dirs (e.g. [quadrant]) — these are
    // implementation details, not standalone pages for tab navigation.
    if (dirEntry.name.startsWith("[") && dirEntry.name.endsWith("]")) continue;

    const pageId = dirEntry.name;
    const pageTsx = path.join(dashboardDir, pageId, "page.tsx");
    if (!fsSync.existsSync(pageTsx)) continue;

    // Skip subdir matching skill name when root page.tsx exists —
    // both would collapse to the same route /{hub}/{skill}
    if (pageId === skill) {
      const rootPage = path.join(dashboardDir, "page.tsx");
      if (fsSync.existsSync(rootPage)) continue;
    }

    // ADR-235: Skip redirect-only stub pages — they create phantom tabs.
    try {
      const pageSrc = fsSync.readFileSync(pageTsx, "utf8");
      if (isRedirectStub(pageSrc)) continue;
    } catch {
      // If we can't read the file, include it anyway
    }

    const overrides = overrideMap.get(pageId) || {};

    pages.push({
      pageId,
      routePath: pageId === skill
        ? `/${hubId}/${skill}`
        : (skill === hubId ? `/${hubId}/${pageId}` : `/${hubId}/${skill}/${pageId}`),
      skill,
      bundle,
      hubId,
      isOwner,
      overrides,
      sourceSkillDir: skillDir,
      sourceConfigPath: configPath,
    });
  }

  // Scan augur/pages/*.yaml for config-driven pages (client skills only)
  if (opts.isClientSkill) {
    const yamlPagesDir = path.join(skillDir, "augur", "pages");
    const routePathsWithPages = new Set(pages.map((page) => page.routePath));
    let yamlFiles: fsSync.Dirent[];
    try {
      yamlFiles = fsSync.readdirSync(yamlPagesDir, { withFileTypes: true });
    } catch {
      yamlFiles = [];
    }

    for (const yf of yamlFiles) {
      if (!yf.isFile() || !yf.name.endsWith(".yaml")) continue;
      const yamlPath = path.join(yamlPagesDir, yf.name);
      let parsed: Record<string, unknown> | null = null;
      try {
        parsed = yaml.parse(fsSync.readFileSync(yamlPath, "utf8")) as Record<string, unknown> | null;
      } catch {
        continue;
      }
      if (!parsed?.hub || !parsed?.route) continue;
      const routePath = `/${parsed.hub}/${parsed.route}`;
      // Skip if a TSX page already exists for this route
      if (routePathsWithPages.has(routePath)) continue;
      const yamlPage: DiscoveredPage = {
        pageId: (parsed.route as string).replace(/\//g, "-"),
        routePath,
        skill,
        bundle: parsed.hub as string,
        hubId: parsed.hub as string,
        isOwner: false,
        overrides: {
          label: parsed.title as string | undefined,
          icon: parsed.icon as string | undefined,
          order: parsed.order as number | undefined,
          page_type: (parsed.page_type as "custom" | "auto") || "custom",
        },
        yamlConfig: yamlPath,
        sourceSkillDir: skillDir,
        sourceConfigPath: yamlPath,
      };
      pages.push(yamlPage);
      routePathsWithPages.add(routePath);
    }
  }

  const rootRoutePath = `/${hubId}/${skill}`;
  const hasRootRoute = pages.some(
    (page) => page.skill === skill && page.routePath === rootRoutePath,
  );
  if (!hasRootRoute) {
    const syntheticOverrides = pickSyntheticRootOverrides(skill, config, overrideMap);
    const generatedConfig = buildSyntheticRootConfig({
      skill,
      hubId,
      config,
      overrides: syntheticOverrides,
    });
    if (generatedConfig) {
      pages.push({
        pageId: skill,
        routePath: rootRoutePath,
        skill,
        bundle,
        hubId,
        isOwner,
        overrides: syntheticOverrides,
        generatedConfig,
        sourceSkillDir: skillDir,
        sourceConfigPath: configPath,
      });
    }
  }
}

/**
 * Discover pages from the filesystem by walking the skill root page
 * at augur/dashboard/page.tsx and nested pages beneath augur/dashboard/.
 *
 * ADR-218: The filesystem is the source of truth for what pages exist.
 * Skill config contributions.pages is used only as an override map for
 * label, icon, order, devOnly, visible.
 *
 * Handles both old array format and new map format for contributions.pages.
 */
export function discoverPagesFromFilesystem(opts?: {
  startDir?: string;
  enabledSkills?: Set<string>;
}): DiscoveredPage[] {
  const pages: DiscoveredPage[] = [];
  const allConfigsForUi = scanSkillConfigs({ startDir: opts?.startDir });
  const clientSkillRoots = Object.values(getClientSkillDirs(opts?.startDir));

  for (const sc of allConfigsForUi) {
    if (opts?.enabledSkills && !opts.enabledSkills.has(sc.skill)) {
      continue;
    }

    // ADR-802 Phase 2: derive the hub/surface id from the skill's declared
    // dashboard pages (route's first segment, e.g. /workspace/rag -> workspace)
    // instead of the removed contributes_to field.
    const hubId = resolveSurfaceId(sc.config);
    if (!hubId) continue;
    const skillDir = path.dirname(sc.path);
    const isOwner = resolveHubRole(sc.config) === "primary";

    discoverSkillPages({
      skill: sc.skill,
      skillDir,
      bundle: sc.bundle,
      hubId,
      isOwner,
      config: sc.config,
      configPath: sc.path,
      pages,
      isClientSkill: isClientSkillSource(skillDir, clientSkillRoots),
    });
  }

  // ==========================================================================
  // ADR-450 / ADR-526: Scan custom TSX pages from the consolidated features root
  // ==========================================================================
  // ADR-526: Custom pages consolidated into apps/dashboard/features/pages/
  const repoRoot = discoverRepoRoot(opts?.startDir);
  const uiPagesDir = path.join(repoRoot, "apps", "dashboard", "features", "pages");

  // Build a lookup: surface/slug -> declaring skill config (for overrides).
  // ADR-802 Phase 2: keyed solely off declared dashboard_pages routes; the
  // legacy contributes_to-keyed direct lookup is removed.
  const featurePageOwnerLookup = new Map<
    string,
    { skill: string; config: DashboardYaml; configPath: string; sourceSkillDir: string }
  >();
  for (const sc of allConfigsForUi) {
    if (opts?.enabledSkills && !opts.enabledSkills.has(sc.skill)) {
      continue;
    }

    const dashboardPages = sc.config.dashboard_pages;
    if (!Array.isArray(dashboardPages)) {
      continue;
    }
    for (const page of dashboardPages) {
      const rawRoute = page.route;
      if (typeof rawRoute !== "string") continue;
      const normalized = rawRoute.trim().replace(/^\/+|\/+$/g, "");
      const parts = normalized.split("/");
      if (parts.length < 2) continue;
      const hubId = parts[0];
      const featureSlug = parts[1];
      if (!hubId || !featureSlug) continue;
      const key = `${hubId}/${featureSlug}`;
      if (!featurePageOwnerLookup.has(key)) {
        featurePageOwnerLookup.set(key, {
          skill: sc.skill,
          config: sc.config,
          configPath: sc.path,
          sourceSkillDir: path.dirname(sc.path),
        });
      }
    }
  }

  if (fsSync.existsSync(uiPagesDir)) {
    const pageByRoutePath = new Map(pages.map((page) => [page.routePath, page]));
    let hubDirs: fsSync.Dirent[];
    try {
      hubDirs = fsSync.readdirSync(uiPagesDir, { withFileTypes: true });
    } catch {
      hubDirs = [];
    }

    for (const hubEntry of hubDirs) {
      if (!hubEntry.isDirectory() || hubEntry.name.startsWith(".")) continue;
      const hubId = hubEntry.name;
      const hubDir = path.join(uiPagesDir, hubId);

      let skillDirs: fsSync.Dirent[];
      try {
        skillDirs = fsSync.readdirSync(hubDir, { withFileTypes: true });
      } catch {
        continue;
      }

      skillDirs.sort((a, b) => a.name.localeCompare(b.name));

      for (const skillEntry of skillDirs) {
        if (!skillEntry.isDirectory() || skillEntry.name.startsWith(".")) continue;
        const featureSlug = skillEntry.name;
        const skillDir = path.join(hubDir, featureSlug);

        // Look up the declaring skill's config for the override map.
        const ownerInfo = featurePageOwnerLookup.get(`${hubId}/${featureSlug}`);
        // Ignore future-release feature pages whose owning skill is staged rather
        // than live under skills/. They can stay in the repo, but they must not
        // mount in the MVP-only main tree.
        if (!ownerInfo) continue;
        const config = ownerInfo.config;
        const isOwner = resolveHubRole(config) === "primary";
        const owningSkill = ownerInfo.skill || featureSlug;

        const overrideMap = buildOverrideMap(config?.contributions?.pages);

        // Check for root page.tsx
        const rootPageTsx = path.join(skillDir, "page.tsx");
        if (fsSync.existsSync(rootPageTsx)) {
          try {
            const pageSrc = fsSync.readFileSync(rootPageTsx, "utf8");
            if (!isRedirectStub(pageSrc)) {
              const overrides = overrideMap.get(featureSlug) || {};
              // Don't add if already discovered from plugin/client dirs
              const routePath = `/${hubId}/${featureSlug}`;
              const existing = pageByRoutePath.get(routePath);
              if (existing) {
                existing.uiPlugin = true; // Mark as UI plugin page
                existing.overrides = overrides;
                existing.skill = owningSkill;
                existing.isOwner = isOwner;
                existing.sourceSkillDir = ownerInfo.sourceSkillDir;
                existing.sourceConfigPath = ownerInfo.configPath;
              } else {
                const discoveredPage: DiscoveredPage = {
                  pageId: featureSlug,
                  routePath,
                  skill: owningSkill,
                  bundle: hubId,
                  hubId,
                  isOwner,
                  overrides,
                  uiPlugin: true,
                  sourceSkillDir: ownerInfo.sourceSkillDir,
                  sourceConfigPath: ownerInfo.configPath,
                };
                pages.push(discoveredPage);
                pageByRoutePath.set(routePath, discoveredPage);
              }
            }
          } catch {
            // fallthrough
          }
        }

        // Walk subdirectories for nested pages
        let subEntries: fsSync.Dirent[];
        try {
          subEntries = fsSync.readdirSync(skillDir, { withFileTypes: true });
        } catch {
          continue;
        }

        subEntries.sort((a, b) => a.name.localeCompare(b.name));

        for (const dirEntry of subEntries) {
          if (!dirEntry.isDirectory()) continue;
          if (dirEntry.name.startsWith(".")) continue;
          if (SKIP_DIRS.has(dirEntry.name)) continue;
          if (dirEntry.name.startsWith("[") && dirEntry.name.endsWith("]")) continue;

          const pageId = dirEntry.name;
          const pageTsx = path.join(skillDir, pageId, "page.tsx");
          if (!fsSync.existsSync(pageTsx)) continue;

          // Skip subdir matching skill name when root page.tsx exists
          if (pageId === featureSlug && fsSync.existsSync(rootPageTsx)) continue;

          let pageSrc = "";
          try {
            pageSrc = fsSync.readFileSync(pageTsx, "utf8");
            if (isRedirectStub(pageSrc)) continue;
          } catch {
            // Include anyway
          }

          const overrides = overrideMap.get(pageId) || {};
          const routePath = pageId === featureSlug
            ? `/${hubId}/${featureSlug}`
            : (featureSlug === hubId
              ? `/${hubId}/${pageId}`
              : `/${hubId}/${featureSlug}/${pageId}`);
          const existingSub = pageByRoutePath.get(routePath);
          if (existingSub) {
            existingSub.uiPlugin = true;
            existingSub.overrides = overrides;
            existingSub.skill = owningSkill;
            existingSub.isOwner = isOwner;
            existingSub.sourceSkillDir = ownerInfo.sourceSkillDir;
            existingSub.sourceConfigPath = ownerInfo.configPath;
          } else {
            const discoveredPage: DiscoveredPage = {
              pageId,
              routePath,
              skill: owningSkill,
              bundle: hubId,
              hubId,
              isOwner,
              overrides,
              uiPlugin: true,
              sourceSkillDir: ownerInfo.sourceSkillDir,
              sourceConfigPath: ownerInfo.configPath,
            };
            pages.push(discoveredPage);
            pageByRoutePath.set(routePath, discoveredPage);
          }
        }
      }
    }
  }

  return pages;
}
