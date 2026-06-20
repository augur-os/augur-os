/**
 * Mount Plugins — Feature Page Helpers
 *
 * Frontmatter parsing, declared-feature-page collection, generated-skill-page
 * import-path construction, and generated-skill dashboard copy syncing.
 * Extracted verbatim from mount-plugins.ts.
 */

import fs from "fs/promises";
import { readFileSync } from "fs";
import path from "path";
import yaml from "yaml";
import { FEATURES_DIR } from "../lib/path-utils";

// Workspace is the only dashboard surface (ADR-802). Page collection is gated
// on this single hub.
export const WORKSPACE_HUB = "workspace";

export const GENERATED_SKILL_PAGES_SEGMENT = path.posix.join(
  FEATURES_DIR,
  "generated-skill-pages",
);

/**
 * Parse YAML frontmatter from markdown content (between --- markers).
 */
export function parseFrontmatter(content: string): Record<string, unknown> {
  if (!content.startsWith("---")) return {};
  const endIdx = content.indexOf("---", 3);
  if (endIdx === -1) return {};
  try {
    return (yaml.parse(content.slice(3, endIdx)) as Record<string, unknown>) ?? {};
  } catch {
    return {};
  }
}

export function collectDeclaredFeaturePages(
  pluginConfigs: Array<{ skill: string; configPath: string }>,
): Map<string, Map<string, string>> {
  const perHub = new Map<string, Map<string, string>>();
  const routePattern = /^\/?([^/\s]+)\/([^/\s][^/]*)/;

  for (const plugin of pluginConfigs) {
    let content: string;
    try {
      content = readFileSync(plugin.configPath, "utf8");
    } catch {
      continue;
    }
    const frontmatter = parseFrontmatter(content);
    const dashboardPages = frontmatter["x-augur-dashboard-pages"];
    if (!Array.isArray(dashboardPages)) continue;

    for (const rawRoute of dashboardPages) {
      // Accept both legacy string form and enriched object form { route: string, ... }
      const routeStr =
        typeof rawRoute === "string"
          ? rawRoute
          : typeof rawRoute === "object" &&
            rawRoute !== null &&
            typeof (rawRoute as Record<string, unknown>)["route"] === "string"
          ? ((rawRoute as Record<string, unknown>)["route"] as string)
          : null;
      if (!routeStr) continue;
      const match = routeStr.match(routePattern);
      if (!match) continue;
      const [, hubId, pageSegment] = match;
      const hubMap = perHub.get(hubId) || new Map<string, string>();
      hubMap.set(pageSegment, plugin.skill);
      hubMap.set(`${hubId}/${pageSegment}`, plugin.skill);
      perHub.set(hubId, hubMap);
    }
  }

  return perHub;
}

export function buildGeneratedSkillPageImportPath(
  hubId: string,
  skill: string,
  pageSegments: string[] = [],
): string {
  return `@/${path.posix.join(
    GENERATED_SKILL_PAGES_SEGMENT,
    hubId,
    skill,
    ...pageSegments,
    "page",
  )}`;
}

export async function syncGeneratedSkillDashboardCopy(opts: {
  dashboardRoot: string;
  dashboardDir: string;
  hubId: string;
  skill: string;
}): Promise<void> {
  const targetDir = path.join(
    opts.dashboardRoot,
    GENERATED_SKILL_PAGES_SEGMENT,
    opts.hubId,
    opts.skill,
  );

  await fs.rm(targetDir, { recursive: true, force: true });
  await fs.mkdir(path.dirname(targetDir), { recursive: true });
  await fs.cp(opts.dashboardDir, targetDir, { recursive: true });
}
