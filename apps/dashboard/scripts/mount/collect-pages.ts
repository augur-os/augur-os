/**
 * Mount Plugins — Registry Page Collection (Phase 4b)
 *
 * Collects UI plugin page entries for the catch-all registry (ADR-450).
 * Pages are NO LONGER copied to app/{hub}/ — the catch-all [[...slug]] route
 * uses dynamic imports to render them directly from plugin source dirs.
 *
 * Extracted verbatim from mount-plugins.ts main(); the statement sequence is
 * byte-identical to the original. The shared locals it needs are threaded in
 * (config, plugins, enabledSkillIds, scriptDir) and it returns the
 * collected registryEntries for the next phase.
 */

import fs from "fs/promises";
import { existsSync } from "fs";
import path from "path";
import {
  getProjectBrainSkillsRoot,
  discoverPagesFromFilesystem,
} from "../../lib/plugin-discovery";
import { FEATURES_DIR } from "../lib/path-utils";
import {
  collectConventionPages,
} from "./generate-registry";
import type { RegistryPageEntry } from "./generate-registry";
import type { DiscoveredPlugin, MountConfig } from "./types";
import {
  WORKSPACE_HUB,
  GENERATED_SKILL_PAGES_SEGMENT,
  collectDeclaredFeaturePages,
  buildGeneratedSkillPageImportPath,
  syncGeneratedSkillDashboardCopy,
} from "./feature-pages";

export async function collectRegistryPageEntries(opts: {
  config: MountConfig;
  plugins: DiscoveredPlugin[];
  enabledSkillIds: Set<string>;
  scriptDir: string;
}): Promise<RegistryPageEntry[]> {
  const { config, plugins, enabledSkillIds, scriptDir } = opts;

  // Phase 4b: Collect UI plugin page entries for catch-all registry (ADR-450)
  // Pages are NO LONGER copied to app/{hub}/ — the catch-all [[...slug]] route
  // uses dynamic imports to render them directly from plugin source dirs.
  console.log(`\nCollecting UI plugin pages for registry (ADR-450)...`);
  const uiPagesDir = path.join(config.dashboardRoot, FEATURES_DIR, "pages");
  const generatedSkillPagesDir = path.join(
    config.dashboardRoot,
    GENERATED_SKILL_PAGES_SEGMENT,
  );

  if (!config.isDryRun) {
    await fs.rm(generatedSkillPagesDir, { recursive: true, force: true });
  }

  // Collect registry entries (for catch-all route generation)
  const registryEntries: RegistryPageEntry[] = [];
  const copiedSkillDashboards = new Set<string>();
  const liveSkillIdsByHub = new Map<string, Set<string>>();

  for (const plugin of plugins) {
    const liveSkills = liveSkillIdsByHub.get(plugin.hubId) || new Set<string>();
    liveSkills.add(plugin.skill);
    liveSkillIdsByHub.set(plugin.hubId, liveSkills);
  }

  const declaredFeaturePagesByHub = collectDeclaredFeaturePages(plugins);

  if (existsSync(uiPagesDir)) {
    // Convention-based {hub}/{skill}/ directories only — no manifest
    try {
      const hubDirs = await fs.readdir(uiPagesDir, { withFileTypes: true });
      for (const hubEntry of hubDirs) {
        if (!hubEntry.isDirectory()) continue;
        const hubName = hubEntry.name;
        if (hubName !== WORKSPACE_HUB) continue;
        const liveSkills = liveSkillIdsByHub.get(hubName);
        if (!liveSkills || liveSkills.size === 0) continue;
        const hubDir = path.join(uiPagesDir, hubName);
        const declaredFeaturePages = declaredFeaturePagesByHub.get(hubName);

        const hubRegistryEntries = await collectConventionPages(
          hubDir,
          hubName,
          new Set<string>(), // No manifest dirs to exclude
          liveSkills,
          declaredFeaturePages,
        );
        registryEntries.push(...hubRegistryEntries);
      }
    } catch {
      // No hub directories — fine
    }
  }

  // Also scan project-brain/capabilities/skills/*/augur/dashboard/ for pages not yet in features/pages/
  const collectedSlugs = new Set(registryEntries.map(e => `${e.hubId}/${e.slug}`));
  for (const plugin of plugins) {
    if (plugin.hubId !== WORKSPACE_HUB) continue;
    if (!plugin.dashboardPath) continue;
    const dashboardDir = plugin.dashboardPath;
    const dashboardCopyKey = `${plugin.hubId}/${plugin.skill}`;

    const ensureDashboardCopy = async (): Promise<void> => {
      if (config.isDryRun || copiedSkillDashboards.has(dashboardCopyKey)) {
        return;
      }

      await syncGeneratedSkillDashboardCopy({
        dashboardRoot: config.dashboardRoot,
        dashboardDir,
        hubId: plugin.hubId,
        skill: plugin.skill,
      });
      copiedSkillDashboards.add(dashboardCopyKey);
    };

    let dashEntryNames: string[];
    try {
      dashEntryNames = await fs.readdir(dashboardDir);
    } catch {
      continue;
    }

    // Check root page.tsx
    const hasRootPage = dashEntryNames.includes("page.tsx");
    if (hasRootPage) {
      const slug = plugin.skill;
      const dedupKey = `${plugin.hubId}/${slug}`;
      if (!collectedSlugs.has(dedupKey)) {
        await ensureDashboardCopy();
        registryEntries.push({
          hubId: plugin.hubId,
          slug,
          sourceDir: dashboardDir,
          importPathOverride: buildGeneratedSkillPageImportPath(
            plugin.hubId,
            plugin.skill,
          ),
        });
        collectedSlugs.add(dedupKey);
      }
    }

    // Check subdirectory pages
    for (const name of dashEntryNames) {
      if (name.startsWith(".") || name.startsWith("[")) continue;
      if (["components", "tabs", "lib", "hooks", "api"].includes(name)) continue;
      const subDir = path.join(dashboardDir, name);
      // Skip files (only check directories)
      try {
        const stat = await fs.stat(subDir);
        if (!stat.isDirectory()) continue;
      } catch { continue; }
      const pageTsx = path.join(subDir, "page.tsx");
      if (!existsSync(pageTsx)) continue;

      // Skip subdir matching skill name when root page exists (same route)
      if (name === plugin.skill && hasRootPage) continue;

      // When subdir matches skill name, slug is just the skill name
      // (same as page-discovery's pageId === skill case: route = /{hub}/{skill})
      const slug = (name === plugin.skill)
        ? plugin.skill
        : (plugin.skill === plugin.hubId ? name : `${plugin.skill}/${name}`);
      const dedupKey = `${plugin.hubId}/${slug}`;
      // Also skip if a features/ page already covers the base skill slug
      // (avoids double-path like growth/growth when features/pages/workspace/growth/ exists)
      const baseSlug = `${plugin.hubId}/${plugin.skill}`;
      if (collectedSlugs.has(baseSlug) && name === plugin.skill) continue;
      if (!collectedSlugs.has(dedupKey)) {
        await ensureDashboardCopy();
        registryEntries.push({
          hubId: plugin.hubId,
          slug,
          sourceDir: subDir,
          importPathOverride: buildGeneratedSkillPageImportPath(
            plugin.hubId,
            plugin.skill,
            [name],
          ),
        });
        collectedSlugs.add(dedupKey);
      }
    }
  }

  // If a skill-owned TSX page was discovered from the filesystem but missed by
  // plugin scanning, synthesize a registry entry so catch-all registries and
  // tab validation stay aligned. This happens during skill-id migrations when
  // the source page moves before the older ownership path fully catches up.
  const discoveredUiPages = discoverPagesFromFilesystem({
    startDir: scriptDir,
    enabledSkills: enabledSkillIds,
  }).filter((page) => page.hubId === WORKSPACE_HUB);
  for (const page of discoveredUiPages) {
    const slug = page.routePath.replace(`/${page.hubId}/`, "");
    const dedupKey = `${page.hubId}/${slug}`;
    if (!slug || collectedSlugs.has(dedupKey)) {
      continue;
    }

    const dashboardDir = path.join(
      page.sourceSkillDir ||
        path.join(getProjectBrainSkillsRoot(config.repoRoot), page.skill),
      "augur",
      "dashboard",
    );
    const dashboardCopyKey = `${page.hubId}/${page.skill}`;
    if (!existsSync(dashboardDir)) {
      continue;
    }

    const nestedDir = path.join(dashboardDir, page.pageId);
    const rootPageTsx = path.join(dashboardDir, "page.tsx");
    const nestedPageTsx = path.join(nestedDir, "page.tsx");

    let sourceDir: string | null = null;
    let pageSegments: string[] = [];
    if (page.pageId === page.skill && existsSync(rootPageTsx)) {
      sourceDir = dashboardDir;
    } else if (existsSync(nestedPageTsx)) {
      sourceDir = nestedDir;
      pageSegments = [page.pageId];
    } else if (page.pageId === page.skill && existsSync(nestedPageTsx)) {
      sourceDir = nestedDir;
      pageSegments = [page.pageId];
    }

    if (!sourceDir) {
      continue;
    }

    if (!config.isDryRun && !copiedSkillDashboards.has(dashboardCopyKey)) {
      await syncGeneratedSkillDashboardCopy({
        dashboardRoot: config.dashboardRoot,
        dashboardDir,
        hubId: page.hubId,
        skill: page.skill,
      });
      copiedSkillDashboards.add(dashboardCopyKey);
    }

    registryEntries.push({
      hubId: page.hubId,
      slug,
      sourceDir,
      importPathOverride: buildGeneratedSkillPageImportPath(
        page.hubId,
        page.skill,
        pageSegments,
      ),
    });
    collectedSlugs.add(dedupKey);
  }

  console.log(`   Collected ${registryEntries.length} page entries`);

  return registryEntries;
}
