/**
 * Mount Plugins — Orchestration & Watch
 *
 * Houses buildConfig, the main() orchestrator (split into phase blocks), and
 * watch mode. Extracted from mount-plugins.ts. The entry script builds a
 * MountRuntimeContext (scriptDir + repoRoot + CLI flags) and passes it in so
 * these functions can resolve paths and honour flags exactly as before.
 */

import fs from "fs/promises";
import { existsSync, watch as fsWatch, readFileSync, type FSWatcher } from "fs";
import path from "path";
import yaml from "yaml";
import {
  getClientSkillDirs,
  getCorePluginsDir,
  getUserPluginsDir,
  discoverPagesFromFilesystem,
} from "../../lib/plugin-discovery";
import { isPluginEnabled } from "../../lib/plugin-state.js";
import type { ContributionBlock } from "../../lib/plugin-schema/types";
import { FEATURES_DIR } from "../lib/path-utils";
import {
  discoverPlugins,
  validateOwnership,
  validateMountPathCollisions,
  filterEnabledPlugins,
  applyDevHubFilter,
  detectHubIdCollisions,
  mountPlugins,
  cleanPluginMounts,
  cleanDisabledMounts,
  clearNextCache,
} from "./index";
import type { MountConfig } from "./index";
import { assembleAndWriteToolConfig } from "./tool-assembly";
import { assertValidAssembledToolContracts } from "./tool-contract-validation";
import { generateYamlPageWrappers } from "../yaml-page-gen";
import {
  buildHubRegistries,
  generateRegistries,
} from "./generate-registry";
import type { RegistryPageEntry } from "./generate-registry";
import {
  getAppDir,
  getDashboardRoot,
} from "./runtime-paths";
import {
  WORKSPACE_HUB,
  parseFrontmatter,
} from "./feature-pages";
import { collectRegistryPageEntries } from "./collect-pages";
import {
  clearDashboardTypeScriptIncrementalState,
  hasNextDevLock,
  regenerateTabRegistry,
} from "./dev-state";

/**
 * Runtime context for the mount pipeline — resolved by the entry script from
 * import.meta.url (scriptDir), repo discovery (repoRoot), and CLI flags.
 */
export interface MountRuntimeContext {
  scriptDir: string;
  repoRoot: string;
  isDryRun: boolean;
  isClean: boolean;
  isVerbose: boolean;
  isWarnOnly: boolean;
}

// ============================================================================
// Configuration
// ============================================================================

/**
 * Build the MountConfig from resolved paths and CLI flags.
 */
export function buildConfig(ctx: MountRuntimeContext): MountConfig {
  const clientSkillDirs = getClientSkillDirs(ctx.scriptDir);

  // Claude Code plugin cache dir (ADR-430 gap 5) — discovery.ts handles scanning
  const pluginCacheBase = process.env.AUGUR_CLAUDE_PLUGIN_CACHE ||
    path.join(process.env.HOME || "", ".claude", "plugins", "cache");
  const pluginCacheDir = existsSync(pluginCacheBase) ? pluginCacheBase : null;

  return {
    repoRoot: ctx.repoRoot,
    dashboardRoot: getDashboardRoot(ctx.scriptDir),
    appDir: getAppDir(ctx.scriptDir),
    corePluginsDir: getCorePluginsDir(ctx.scriptDir),
    userPluginsDir: getUserPluginsDir(ctx.scriptDir),
    clientSkillDirs,
    pluginCacheDir,
    isDryRun: ctx.isDryRun,
    isClean: ctx.isClean,
    isVerbose: ctx.isVerbose,
    // ADR-802: dev-hub focus filtering retired — workspace is the only surface.
    devHubFilter: null,
  };
}

// ============================================================================
// Main
// ============================================================================

export async function main(ctx: MountRuntimeContext): Promise<void> {
  const config = buildConfig(ctx);
  const { scriptDir, isVerbose, isWarnOnly } = ctx;

  console.log("Augur Plugin Mounter");
  console.log("=".repeat(50));

  if (config.isDryRun) {
    console.log("   Mode: DRY RUN (no changes will be made)");
  }
  if (config.isClean) {
    console.log("   Mode: CLEAN (removing plugin mounts)");
  }

  // Clear Next.js cache FIRST to prevent Tailwind stale file race condition
  if (!config.isDryRun) {
    await clearNextCache(config);
  }

  console.log(`\nPaths:`);
  console.log(`   Core repo: ${config.repoRoot}`);
  console.log(`   Core plugins: ${config.corePluginsDir}`);
  console.log(`   User plugins: ${config.userPluginsDir ?? "(none)"}`);
  const clientDirCount = Object.keys(config.clientSkillDirs).length;
  if (clientDirCount > 0) {
    console.log(`   Client skill dirs: ${clientDirCount}`);
    for (const [clientId, dirPath] of Object.entries(config.clientSkillDirs)) {
      console.log(`     ${clientId}: ${dirPath}`);
    }
  }
  console.log(`   Plugin cache: ${config.pluginCacheDir ?? "(none)"}`);
  console.log(`   App directory: ${config.appDir}`);

  // Clean mode
  if (config.isClean) {
    console.log(`\nCleaning plugin mounts...`);
    await cleanPluginMounts(config);
    console.log("Clean complete");
    return;
  }

  // Phase 1: Discovery
  console.log(`\nDiscovering plugins...`);
  const allPlugins = await discoverPlugins(config);

  if (allPlugins.length === 0) {
    console.log("   No plugins with SKILL.md found.");
    return;
  }

  // Phase 2: Resolution — filter by enabled state
  let plugins = filterEnabledPlugins(allPlugins);

  // Phase 2b: Dev-focus filtering
  plugins = applyDevHubFilter(plugins, config);

  const skippedCount = allPlugins.length - plugins.length;

  console.log(
    `   Found ${allPlugins.length} plugins (${skippedCount} disabled):`,
  );
  for (const plugin of allPlugins) {
    const hasUI = plugin.dashboardPath ? "UI" : "  ";
    const hasAPI = plugin.apiPath ? "API" : "   ";
    const hasLib = plugin.libPath ? "LIB" : "   ";
    const pluginIsDisabled =
      !isPluginEnabled(plugin.skill, "skill") ||
      !isPluginEnabled(plugin.hubId, "hub") ||
      (plugin.extendsHubId
        ? !isPluginEnabled(plugin.extendsHubId, "hub")
        : false);
    const status = pluginIsDisabled ? " [DISABLED]" : "";
    const roleLabel =
      plugin.role === "primary"
        ? "primary"
        : `extension->${plugin.extendsHubId}`;
    console.log(
      `   ${hasUI} ${hasAPI} ${hasLib} ${plugin.bundle}/${plugin.skill} -> /${plugin.mountPath} [${roleLabel}] (${plugin.source})${status}`,
    );
  }

  if (skippedCount > 0) {
    console.log(`\n   Skipping ${skippedCount} disabled plugins`);
  }

  // Phase 3: Validation
  validateOwnership(plugins);
  await validateMountPathCollisions(plugins);
  detectHubIdCollisions(plugins, isWarnOnly);

  // Phase 4: Clean disabled mounts + mount enabled plugins
  const disabledPlugins = allPlugins.filter((p) => !plugins.includes(p));
  if (!config.isDryRun) {
    await cleanDisabledMounts(disabledPlugins, config);
  }

  console.log(`\nMounting ${plugins.length} enabled plugins...`);
  const results = await mountPlugins(plugins, config);

  // Phase 4b: Collect UI plugin page entries for catch-all registry (ADR-450)
  const enabledSkillIds = new Set(plugins.map((plugin) => plugin.skill));
  const registryEntries = await collectRegistryPageEntries({
    config,
    plugins,
    enabledSkillIds,
    scriptDir,
  });

  // Phase 5: Hub Assembly (ADR-128) — collapsed to a single fixed surface (ADR-802).
  // Workspace is the only hub and always has pages, so the assembled hub set is constant.
  const assembledHubIds = ["workspace"];

  // Phase 5b: Tool Config Assembly (ADR-260)
  console.log(`\nAssembling tool config (ADR-260)...`);
  const assembledToolConfig = await assembleAndWriteToolConfig(config);
  assertValidAssembledToolContracts({
    repoRoot: config.repoRoot,
    assembled: assembledToolConfig,
  });
  console.log(`   Tool contracts validated`);

  // Phase 5c: Page file validation (ADR-177)
  // (renumbered from 5b after ADR-260 tool assembly insertion)
  // Verify that every contributions.pages entry has a corresponding dashboard file
  console.log(`\nValidating page contributions (ADR-177)...`);
  let autoGenerateCount = 0;
  for (const plugin of plugins) {
    try {
      const configContent = await fs.readFile(plugin.configPath, "utf8");
      const frontmatter = parseFrontmatter(configContent);
      // Support x-augur-config-file sidecar
      let augurConfig = (frontmatter["x-augur-config"] ?? {}) as {
        contributions?: ContributionBlock;
      };
      const cfgFile = frontmatter["x-augur-config-file"];
      if (cfgFile && typeof cfgFile === "string" && !frontmatter["x-augur-config"]) {
        const sidecar = path.join(path.dirname(plugin.configPath), cfgFile as string);
        try {
          const cfgContent = readFileSync(sidecar, "utf8");
          const parsed = yaml.parse(cfgContent);
          if (parsed && typeof parsed === "object") {
            augurConfig = parsed as { contributions?: ContributionBlock };
          }
        } catch { /* sidecar unavailable */ }
      }
      const rawPages = augurConfig?.contributions?.pages;
      if (!rawPages) continue;

      const pages = Array.isArray(rawPages)
        ? rawPages
        : Object.entries(rawPages).map(([id, page]) => ({
            id,
            ...((page as Record<string, unknown> | null) ?? {}),
          }));
      if (pages.length === 0) continue;

      // Dashboard files live under {skill}/augur/dashboard/
      // configPath is now SKILL.md at the skill root
      const skillDir = path.dirname(plugin.configPath);
      const dashboardDir = path.join(skillDir, "augur", "dashboard");

      for (const page of pages) {
        if (!page.id) continue;
        const pageDir = path.join(dashboardDir, page.id);
        const pageFile = path.join(pageDir, "page.tsx");
        try {
          await fs.stat(pageFile);
        } catch {
          // page.tsx doesn't exist in subdir — for sub-skills where page.id
          // matches the skill name, the root dashboard/page.tsx IS the page
          // (mount-plugins mounts it at /{hub}/{skill}/)
          const rootPageFile = path.join(dashboardDir, "page.tsx");
          let rootPageExists = false;
          if (page.id === plugin.skill) {
            try {
              await fs.stat(rootPageFile);
              rootPageExists = true;
            } catch {
              /* not found */
            }
          }
          if (!rootPageExists) {
            // ADR-272: Pages without a custom page.tsx will get an
            // auto-generated ConfigPage wrapper at mount time.
            // Count instead of printing each one — summary printed below.
            autoGenerateCount++;
            if (isVerbose) {
              try {
                await fs.stat(pageDir);
                console.log(
                  `   INFO: Skill ${plugin.skill} page "${page.id}" has no page.tsx — will auto-generate (ADR-272)`,
                );
              } catch {
                console.log(
                  `   INFO: Skill ${plugin.skill} page "${page.id}" has no dashboard dir — will auto-generate (ADR-272)`,
                );
              }
            }
          }
        }
      }
    } catch {
      // Could not read SKILL.md — skip (already validated in discovery)
    }
  }

  if (autoGenerateCount > 0) {
    console.log(`   ${autoGenerateCount} pages will be auto-generated (ADR-272) — use --verbose for details`);
  }
  console.log(`   All declared pages have corresponding dashboard files`);

  // Phase 5c: Detect unmanaged page files in app/ (agent protection)
  // Files created directly in apps/dashboard/app/ instead of the plugin source
  // will be overwritten on next mount. Warn loudly so agents notice.
  // Bounded by design — static literal of known shell page names
  const SHELL_PAGES = new Set([
    "page.tsx",
    "activity",
    "app",
    "artifact",
    "files",
    "skills",
    "login",
    "settings",
    "setup",
  ]);
  const AUTO_GENERATED_MARKER = "AUTO-GENERATED FILE";
  console.log(`\nChecking for unmanaged pages in app/...`);
  let unmanagedCount = 0;

  async function scanForUnmanaged(dir: string, depth = 0): Promise<void> {
    if (depth > 4) return;
    // Skip root page.tsx (shell page)
    if (depth === 0) {
      try {
        await fs.stat(path.join(dir, "page.tsx"));
      } catch {
        /* no root page — fine */
      }
    }
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const rel = path.relative(config.appDir, path.join(dir, entry.name));
      const topLevel = rel.split(path.sep)[0];
      const isRouteGroup =
        entry.name.startsWith("(") && entry.name.endsWith(")");
      if (SHELL_PAGES.has(topLevel)) continue;
      // Skip components/ and other non-route dirs
      if (entry.name === "components" || entry.name === "api") continue;
      // Skip catch-all directories (generated by registry generator)
      if (entry.name === "[[...slug]]") continue;
      // Top-level route groups are framework-owned routes, not mounted plugin pages.
      if (depth === 0 && isRouteGroup) continue;

      const pagePath = path.join(dir, entry.name, "page.tsx");
      try {
        const content = await fs.readFile(pagePath, "utf8");
        if (!content.includes(AUTO_GENERATED_MARKER)) {
          console.warn(
            `WARNING: Unmanaged page.tsx at app/${rel}/page.tsx — edit the plugin source instead`,
          );
          unmanagedCount++;
        }
      } catch {
        // No page.tsx — fine
      }
      await scanForUnmanaged(path.join(dir, entry.name), depth + 1);
    }
  }

  await scanForUnmanaged(config.appDir);
  if (unmanagedCount > 0) {
    console.warn(
      `\n${unmanagedCount} unmanaged page(s) found in app/ — these will be overwritten on next mount.`,
    );
    console.warn(`See apps/dashboard/app/README.md for the correct workflow.`);
  } else {
    console.log(`   All pages properly managed`);
  }

  // Summary
  const successful = results.filter((r) => r.success);
  const failed = results.filter((r) => !r.success);

  console.log(`\nResults:`);
  console.log(`   Mounted: ${successful.length}`);
  for (const r of successful) {
    const typeLabel = r.type === "dashboard" ? "UI " : "API";
    const routePath = r.mountPath;
    console.log(`   [${typeLabel}] /${routePath}`);
  }

  if (failed.length > 0) {
    console.log(`\nFailed: ${failed.length}`);
    for (const r of failed) {
      const routePath = r.mountPath;
      console.log(`   /${routePath}: ${r.error}`);
    }
    process.exit(1);
  }

  // Phase 5b: Generate YAML page wrappers BEFORE registry collection.
  // Discovers YAML page configs from project-brain/capabilities/skills/{skill}/augur/pages/*.yaml,
  // generates ConfigPage wrapper TSX files in lib/configs/.
  // Must run before Phase 6a so the wrappers exist when collected.
  if (!config.isDryRun) {
    const discoveredPages = discoverPagesFromFilesystem({
      startDir: scriptDir,
      enabledSkills: enabledSkillIds,
    }).filter((page) => page.hubId === WORKSPACE_HUB);
    const yamlWrapperCount = await generateYamlPageWrappers(discoveredPages, scriptDir);
    if (yamlWrapperCount > 0) {
      console.log(`   Generated ${yamlWrapperCount} YAML page wrapper(s)`);
    }

    // Phase 6a: Collect generated YAML page wrappers from lib/configs/
    // Add them as registry entries so the catch-all route can resolve them.
    const configsDir = path.join(config.dashboardRoot, "lib", "configs");
    let yamlPageCount = 0;
    try {
      const configFiles = await fs.readdir(configsDir);
      for (const f of configFiles) {
        if (!f.endsWith(".tsx")) continue;
        // Read route from JSON sidecar (authoritative), fall back to filename parsing
        const stem = f.replace(/\.tsx$/, "");
        const jsonSidecar = path.join(configsDir, `${stem}.json`);
        let hubId: string;
        let slug: string;
        try {
          const jsonContent = JSON.parse(await fs.readFile(jsonSidecar, "utf-8"));
          hubId = jsonContent.hub;
          slug = jsonContent.route;
        } catch {
          // Fallback: derive from filename (legacy, loses hyphens)
          const dashIdx = stem.indexOf("-");
          if (dashIdx === -1) continue;
          hubId = stem.slice(0, dashIdx);
          slug = stem.slice(dashIdx + 1).replace(/-/g, "/");
        }
        if (hubId !== WORKSPACE_HUB) continue;
        // Replace any conventional page entry for the same hub+slug
        // so the YAML config page takes precedence (no duplicate keys).
        const existingIdx = registryEntries.findIndex(
          (e) => e.hubId === hubId && e.slug === slug,
        );
        const yamlEntry: RegistryPageEntry = {
          hubId,
          slug,
          sourceDir: configsDir,
          importPathOverride: `@/lib/configs/${stem}`,
        };
        if (existingIdx !== -1) {
          registryEntries[existingIdx] = yamlEntry;
        } else {
          registryEntries.push(yamlEntry);
        }
        yamlPageCount++;
      }
    } catch {
      // No configs dir — no YAML pages generated
    }
    if (yamlPageCount > 0) {
      console.log(`   Collected ${yamlPageCount} YAML config page wrapper(s)`);
    }

    // Phase 6b: Catch-All Registry Generation
    // Generate registry.ts + page.tsx for each hub that has UI pages, plus
    // overview routes for assembled hubs with zero pages.
    // The catch-all route is the SOLE page renderer for hub sub-routes.
    console.log(`\nGenerating catch-all registries...`);

    // Hub default redirect paths — hubs that redirect bare /{hub} to a specific sub-page.
    // Explicit overrides for hubs where the first page isn't the desired default.
    const hubDefaultOverrides: Record<string, string> = {
      workspace: "/workspace/memory",
    };

    // Auto-compute defaults: for each hub, use the explicit override if set,
    // otherwise default to the first registered page entry.
    const entriesByHub = new Map<string, RegistryPageEntry[]>();
    for (const entry of registryEntries) {
      const list = entriesByHub.get(entry.hubId) || [];
      list.push(entry);
      entriesByHub.set(entry.hubId, list);
    }

    const hubDefaults: Record<string, string> = {};
    for (const [hubId, entries] of entriesByHub) {
      if (hubDefaultOverrides[hubId]) {
        hubDefaults[hubId] = hubDefaultOverrides[hubId];
      } else if (entries.length > 0) {
        // Sort by slug for determinism, pick first
        const sorted = [...entries].sort((a, b) => a.slug.localeCompare(b.slug));
        hubDefaults[hubId] = `/${hubId}/${sorted[0].slug}`;
      }
    }

    const hubRegistries = buildHubRegistries(
      registryEntries,
      hubDefaults,
      config.appDir,
      config.repoRoot,
    );
    await generateRegistries(config.appDir, hubRegistries, assembledHubIds);
    await clearDashboardTypeScriptIncrementalState(config.dashboardRoot);

    const totalPages = hubRegistries.reduce((sum, h) => sum + h.entries.length, 0);
    console.log(
      `   Generated ${new Set([...hubRegistries.map((h) => h.hubId), ...assembledHubIds]).size} hub registries (${totalPages} total pages)`,
    );
  }

  // Phase 7: Tab Registry Regeneration — MUST run after catch-all generation
  // so the validator can find [[...slug]]/registry.ts files on disk
  if (!config.isDryRun) {
    console.log(`\nRegenerating tab registry...`);
    regenerateTabRegistry(scriptDir);
  } else {
    console.log(`\nSkipping generated registries in dry-run mode`);
  }

  console.log(
    `\nPlugin mounting complete! (${assembledHubIds.length} assembled hubs)`,
  );
}

// ============================================================================
// Watch Mode
// ============================================================================

/**
 * Watch plugin dashboard directories for changes and re-run mount + tab generation.
 *
 * Uses fs.watch (Node built-in) on each plugin's augur/dashboard/ directory.
 * Debounces rapid changes to avoid thrashing during multi-file operations.
 */
export async function startWatchMode(ctx: MountRuntimeContext): Promise<void> {
  // Skip initial mount — prebuild in start-dev.sh already ran it.
  // The watcher only reacts to subsequent changes.

  const config = buildConfig(ctx);

  // Collect all skill dashboard directories to watch from managed skill roots.
  const watchPaths: string[] = [];
  for (const skillsDir of Object.values(config.clientSkillDirs)) {
    try {
      const skills = await fs.readdir(skillsDir, { withFileTypes: true });
      for (const entry of skills) {
        if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
        const augurDir = path.join(skillsDir, entry.name, "augur");
        const dashDir = path.join(augurDir, "dashboard");
        try {
          const stat = await fs.stat(dashDir);
          if (stat.isDirectory()) {
            watchPaths.push(dashDir);
          }
        } catch {
          // No dashboard directory — skip
        }
      }
    } catch {
      // skills root not readable — skip
    }
  }

  // Also watch features/pages/ for custom page changes
  const featurePagesDir = path.join(config.dashboardRoot, FEATURES_DIR, "pages");
  watchPaths.push(featurePagesDir);

  console.log(
    `\n[watch] Watching ${watchPaths.length} plugin dashboard directories`,
  );
  console.log(`[watch] Changes will trigger re-mount + tab regeneration\n`);

  const watcherHandles: FSWatcher[] = [];
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let devHealthTimer: ReturnType<typeof setInterval> | null = null;
  let isRunning = false;
  let isStopping = false;
  let hasObservedDevLock = false;
  const startupDeadline = Date.now() + 30_000;

  const stopWatchMode = (reason: string): void => {
    if (isStopping) return;
    isStopping = true;

    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    if (devHealthTimer) {
      clearInterval(devHealthTimer);
      devHealthTimer = null;
    }
    for (const watcher of watcherHandles) {
      watcher.close();
    }

    console.log(`\n[watch] ${reason}`);
    process.exit(0);
  };

  const checkDevServerHealth = (): boolean => {
    const devLockPresent = hasNextDevLock(config.dashboardRoot);
    if (devLockPresent) {
      hasObservedDevLock = true;
      return true;
    }

    if (hasObservedDevLock || Date.now() >= startupDeadline) {
      stopWatchMode(
        "Next.js dev server is not active. Exiting plugin watch mode.",
      );
    }

    return false;
  };

  const rebuild = async () => {
    if (isRunning || isStopping) return;
    if (!checkDevServerHealth()) return;

    isRunning = true;
    try {
      console.log(`\n[watch] Change detected — rebuilding...`);
      await main(ctx);
      console.log(`[watch] Rebuild complete\n`);
    } catch (err) {
      console.error(`[watch] Rebuild failed:`, err);
    } finally {
      isRunning = false;
    }
  };

  const onChange = () => {
    if (isStopping) return;
    if (debounceTimer) clearTimeout(debounceTimer);
    // Cleanup: stopWatchMode() clears debounceTimer on SIGINT/SIGTERM (line 757)
    debounceTimer = setTimeout(rebuild, 500);
  };

  // Watch each directory recursively
  for (const watchPath of watchPaths) {
    try {
      watcherHandles.push(fsWatch(watchPath, { recursive: true }, onChange));
    } catch {
      // Some directories may not support recursive watch — skip
    }
  }

  // Also watch SKILL.md files for page contribution changes.
  for (const skillsDir of Object.values(config.clientSkillDirs)) {
    try {
      const skillEntries = await fs.readdir(skillsDir, { withFileTypes: true });
      for (const entry of skillEntries) {
        if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
        const skillMd = path.join(skillsDir, entry.name, "SKILL.md");
        try {
          await fs.stat(skillMd);
          watcherHandles.push(fsWatch(skillMd, onChange));
        } catch {
          // No SKILL.md — skip
        }
      }
    } catch {
      // skills root not readable — skip
    }
  }

  checkDevServerHealth();
  devHealthTimer = setInterval(checkDevServerHealth, 1_000);

  // Keep process alive
  process.on("SIGINT", () => {
    stopWatchMode("Stopping...");
  });
  process.on("SIGTERM", () => {
    stopWatchMode("Stopping...");
  });
}
