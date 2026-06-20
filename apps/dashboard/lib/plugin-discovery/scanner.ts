/**
 * Plugin Discovery — Scanner
 *
 * Core skill config scanning from SKILL.md frontmatter.
 * A skill is admitted into discovery when it declares any dashboard
 * contribution signal: a /workspace/* page (x-augur-dashboard-pages),
 * MCP tools (x-augur-mcp-tools), or non-empty config (x-augur-config).
 * The legacy x-augur-hub/contributes_to gate is removed (ADR-802 Phase 2).
 *
 * Page discovery lives in ./page-discovery.ts.
 */

import fs from "fs/promises";
import fsSync from "fs";
import path from "path";
import yaml from "yaml";
import type { SkillConfig } from "./types";
import type { DashboardYaml } from "../plugin-schema/types";
import { getAllPluginDirs, getClientSkillDirs } from "./paths";
import {
  validateSkillConfig,
  formatValidationErrors,
} from "../plugin-schema/validation";

// Re-export from sub-modules so existing `from './scanner'` imports keep working
export {
  discoverPagesFromFilesystem,
  isRedirectStub,
  smartLabel,
} from "./page-discovery";
export type { DiscoveredPage } from "./page-discovery";

// ---------------------------------------------------------------------------
// WorkspacePage — parsed representation of x-augur-dashboard-pages entries
// ---------------------------------------------------------------------------

export interface WorkspacePage {
  route: string;     // "/workspace/memory"
  slug: string;      // "memory"
  title?: string;
  icon?: string;
  order?: number;
  keywords?: string[];
}

/**
 * Parse raw x-augur-dashboard-pages value into typed WorkspacePage[].
 * Accepts both legacy string entries ("/workspace/foo") and enriched
 * object entries ({ route, title, icon, order, keywords }).
 */
export function parseDashboardPages(raw: unknown): WorkspacePage[] {
  if (!Array.isArray(raw)) return [];
  const out: WorkspacePage[] = [];
  for (const entry of raw) {
    const route =
      typeof entry === "string" ? entry : (entry?.route as string | undefined);
    if (!route || typeof route !== "string") continue;
    const slug = route.replace(/^\/workspace\//, "").replace(/^\//, "");
    const o =
      typeof entry === "object" && entry
        ? (entry as Record<string, unknown>)
        : {};
    out.push({
      route,
      slug,
      title: o.title as string | undefined,
      icon: o.icon as string | undefined,
      order: o.order as number | undefined,
      keywords: Array.isArray(o.keywords)
        ? (o.keywords as string[])
        : undefined,
    });
  }
  return out;
}

/**
 * Returns true when at least one page declares a /workspace/* route.
 */
export function isWorkspaceContributor(pages: WorkspacePage[]): boolean {
  return pages.some((p) => p.route.startsWith("/workspace/"));
}

/**
 * Parse YAML frontmatter from a SKILL.md file.
 */
function parseFrontmatter(content: string): Record<string, unknown> {
  if (!content.startsWith("---")) return {};
  const endIdx = content.indexOf("---", 3);
  if (endIdx === -1) return {};
  try {
    return (yaml.parse(content.slice(3, endIdx)) as Record<string, unknown>) ?? {};
  } catch {
    return {};
  }
}

/**
 * Parse SKILL.md frontmatter into a DashboardYaml-compatible config.
 * Reads x-augur-config as the base fields, x-augur-mcp-tools, and the
 * declared x-augur-dashboard-pages.
 *
 * Admit condition (ADR-802 Phase 2): a skill is dashboard-relevant — and
 * thus admitted into discovery — when it declares ANY contribution signal:
 *   - a /workspace/* page (x-augur-dashboard-pages)
 *   - MCP tools (x-augur-mcp-tools, non-empty)
 *   - a non-empty x-augur-config block
 * x-augur-hub is no longer read or used for the gate; it is removed from
 * frontmatter in a later task.
 */
function parseSkillMdConfig(filePath: string): DashboardYaml | null {
  try {
    const content = fsSync.readFileSync(filePath, "utf8");
    const data = parseFrontmatter(content);
    const pages = parseDashboardPages(data["x-augur-dashboard-pages"]);

    let augurConfig = (data["x-augur-config"] ?? {}) as Record<string, unknown>;
    const configFile = data["x-augur-config-file"];
    if (configFile && typeof configFile === "string" && !data["x-augur-config"]) {
      const sidecarPath = path.join(path.dirname(filePath), configFile as string);
      try {
        const sidecarContent = fsSync.readFileSync(sidecarPath, "utf8");
        const parsed = yaml.parse(sidecarContent) as Record<string, unknown> | null;
        if (parsed && typeof parsed === "object") {
          augurConfig = parsed;
        }
      } catch {
        // Sidecar missing or invalid
      }
    }
    const dependencies = data["x-augur-dependencies"] ?? augurConfig.dependencies;
    const mcpTools = Array.isArray(data["x-augur-mcp-tools"])
      ? (data["x-augur-mcp-tools"] as string[])
      : undefined;

    if (
      !isWorkspaceContributor(pages) &&
      !(mcpTools && mcpTools.length) &&
      !(augurConfig && Object.keys(augurConfig).length)
    )
      return null;

    return {
      ...augurConfig,
      dependencies,
      ...(mcpTools ? { mcp_tools: mcpTools } : {}),
      ...(pages.length > 0 ? { dashboard_pages: pages } : {}),
    } as DashboardYaml;
  } catch {
    return null;
  }
}

/**
 * Load a skill config from a skill directory.
 * Exported for use by page-discovery.ts.
 */
function loadSkillConfig(
  skillDir: string,
): { configPath: string; config: DashboardYaml } | null {
  const skillMdPath = path.join(skillDir, "SKILL.md");
  if (!fsSync.existsSync(skillMdPath)) {
    return null;
  }
  const config = parseSkillMdConfig(skillMdPath);
  if (!config) {
    return null;
  }
  return { configPath: skillMdPath, config };
}

/**
 * Marker in SKILL.md header that identifies adapted copies.
 * Adapted copies are generated from master skills and should not be
 * re-discovered as independent skills.
 */
const ADAPTED_COPY_MARKER = "AUGUR-ADAPTED-COPY";
const ADAPTED_COPY_MARKER_PATTERN = /AUGUR-ADAPTED-COPY/;

/**
 * Discover bundle directories under a plugins dir (sync).
 * Reads hub directories, filtering hidden dirs.
 */
export function discoverBundles(pluginsDir: string): string[] {
  try {
    return fsSync
      .readdirSync(pluginsDir, { withFileTypes: true })
      .flatMap((e) => (e.isDirectory() && !e.name.startsWith(".") ? [e.name] : []))
      .sort();
  } catch {
    return [];
  }
}

/**
 * Discover bundle directories under a plugins dir (async).
 */
export async function discoverBundlesAsync(
  pluginsDir: string,
): Promise<string[]> {
  try {
    const entries = await fs.readdir(pluginsDir, { withFileTypes: true });
    return entries
      .flatMap((e) => (e.isDirectory() && !e.name.startsWith(".") ? [e.name] : []))
      .sort();
  } catch {
    return [];
  }
}

/**
 * Resolve hub role from skill config metadata.
 *
 * ADR-187: Primary = has hub: block with id AND (owner: true or owner field absent for backwards compat).
 * A skill with hub.id but owner: false is treated as an extension.
 */
export function resolveHubRole(config: {
  hub?: { id?: string; owner?: boolean };
  contributes_to?: string;
}): "primary" | "extension" {
  if (!config?.hub?.id) return "extension";
  // Explicit owner: false means this skill has a hub block but is not the owner
  if (config.hub.owner === false) return "extension";
  return "primary";
}

/**
 * Scan all plugins for skill configs and return SkillConfig[].
 *
 * This is THE core discovery function. Replaces duplicate scan loops
 * in build scripts, lib modules, and API routes.
 *
 * A skill is admitted when parseSkillMdConfig accepts it — i.e. it declares
 * a dashboard contribution signal (a /workspace/* page, MCP tools, or a
 * non-empty x-augur-config). User plugins override core plugins with the
 * same skill name. Does NOT filter by enabled/disabled state — consumers
 * handle that.
 */
export function scanSkillConfigs(opts?: {
  startDir?: string;
}): SkillConfig[] {
  const pluginDirs = getAllPluginDirs(opts?.startDir);
  const configs: SkillConfig[] = [];
  // TODO_BUG(auto-memory-leak): unbounded-cache — Module-level Map/Set without MAX size guard — grows without bound
  const seenSkills = new Map<string, number>();

  for (const pluginsDir of pluginDirs) {
    for (const bundle of discoverBundles(pluginsDir)) {
      const skillsDir = path.join(pluginsDir, bundle, "skills");

      let skills: fsSync.Dirent[];
      try {
        skills = fsSync.readdirSync(skillsDir, { withFileTypes: true });
      } catch {
        continue;
      }

      // Sort skills alphabetically for deterministic discovery order.
      // readdir order is filesystem-dependent (APFS, ext4, etc.) and
      // can vary between runs — sorting eliminates this source of churn
      // in downstream generated files.
      skills.sort((a, b) => a.name.localeCompare(b.name));

      for (const entry of skills) {
        if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
        const skill = entry.name;
        const loaded = loadSkillConfig(path.join(skillsDir, skill));
        if (!loaded) {
          continue;
        }
        const { configPath, config } = loaded;

        try {
          // ADR-187: Validate tab-related fields at scan time
          const validationErrors = validateSkillConfig(config, configPath);
          if (validationErrors) {
            console.warn(
              `WARNING: skill config validation errors in ${bundle}/${skill}:\n${formatValidationErrors(validationErrors)}`,
            );
          }

          const augurDir = path.join(skillsDir, skill, "augur");
          const apiDir = path.join(augurDir, "api");
          const libDir = path.join(augurDir, "lib");

          const skillConfig: SkillConfig = {
            bundle,
            skill,
            config,
            path: configPath,
            hasApi:
              fsSync.existsSync(apiDir) &&
              fsSync.statSync(apiDir).isDirectory(),
            hasLib:
              fsSync.existsSync(libDir) &&
              fsSync.statSync(libDir).isDirectory(),
          };

          // Dedup by skill name so later/higher-priority roots replace earlier
          // copies even when promotion changes hub metadata.
          const dedupeKey = skill;
          const existingIdx = seenSkills.get(dedupeKey);
          if (existingIdx !== undefined) {
            configs[existingIdx] = skillConfig;
          } else {
            seenSkills.set(dedupeKey, configs.length);
            configs.push(skillConfig);
          }
        } catch {
          // Skip invalid YAML
        }
      }
    }
  }

  // Scan client skill directories (flat structure, no bundles)
  const clientDirs = getClientSkillDirs(opts?.startDir);
  for (const [clientId, clientDir] of Object.entries(clientDirs)) {
    let skills: fsSync.Dirent[];
    try {
      skills = fsSync.readdirSync(clientDir, { withFileTypes: true });
    } catch {
      continue;
    }

    skills.sort((a, b) => a.name.localeCompare(b.name));

    for (const entry of skills) {
      if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
      const skill = entry.name;
      const skillDir = path.join(clientDir, skill);

      // Skip adapted copies: check for marker anywhere in SKILL.md
      // The marker appears as an HTML comment after the YAML frontmatter
      // closing ---, so its line number varies with frontmatter length.
      const skillMdPath = path.join(skillDir, "SKILL.md");
      try {
        const skillMdContent = fsSync.readFileSync(skillMdPath, "utf8");
        if (ADAPTED_COPY_MARKER_PATTERN.test(skillMdContent)) continue;
      } catch {
        // No SKILL.md — not an adapted copy, continue checking
      }

      const loaded = loadSkillConfig(skillDir);
      if (!loaded) {
        continue;
      }
      const { configPath, config } = loaded;

      try {
        // ADR-187: Validate tab-related fields at scan time
        const validationErrors = validateSkillConfig(config, configPath);
        if (validationErrors) {
          console.warn(
            `WARNING: skill config validation errors in ${clientId}/${skill}:\n${formatValidationErrors(validationErrors)}`,
          );
        }

        // Client skills have no bundle dir; use the skill name as the bundle.
        const bundle = skill;

        const augurDir = path.join(skillDir, "augur");
        const apiDir = path.join(augurDir, "api");
        const libDir = path.join(augurDir, "lib");

        const skillConfig: SkillConfig = {
          bundle,
          skill,
          config,
          path: configPath,
          hasApi:
            fsSync.existsSync(apiDir) &&
            fsSync.statSync(apiDir).isDirectory(),
          hasLib:
            fsSync.existsSync(libDir) &&
            fsSync.statSync(libDir).isDirectory(),
        };

        // Client skills override core/user by skill name (last-writer-wins).
        const dedupeKey = skill;
        const existingIdx = seenSkills.get(dedupeKey);
        if (existingIdx !== undefined) {
          configs[existingIdx] = skillConfig;
        } else {
          seenSkills.set(dedupeKey, configs.length);
          configs.push(skillConfig);
        }
      } catch {
        // Skip invalid YAML
      }
    }
  }

  return configs;
}
