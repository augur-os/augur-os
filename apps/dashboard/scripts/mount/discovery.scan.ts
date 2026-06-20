/**
 * Mount Plugins — Discovery filesystem scanning
 *
 * Scans plugin/bundle directories, flat client skill directories, the
 * Claude Code plugin cache, and the canonical skill manifest to discover
 * mountable plugins.
 *
 * Split out of discovery.ts (WS5 decomposition) — moved verbatim.
 */

import fs from "fs/promises";
import fsSync from "fs";
import path from "path";
import { isDisabledByConfig } from "../../lib/skill-config";
import { discoverBundlesAsync } from "../../lib/plugin-discovery";
import type { DiscoveredPlugin, MountConfig } from "./types";
import {
  normalizeRouteSegment,
  isManagedSkillDirAllowed,
  hasLocalSkillRoots,
  removeExistingClientSkillByName,
} from "./discovery.shared";
import { resolveOwnership } from "./discovery.ownership";
import { resolveSkillPaths, parseSkillMdConfig } from "./discovery.config";

// ============================================================================
// Helpers
// ============================================================================

/**
 * Check if a directory exists.
 */
export async function dirExists(dirPath: string | null): Promise<boolean> {
  if (!dirPath) return false;
  try {
    const stat = await fs.stat(dirPath);
    return stat.isDirectory();
  } catch {
    return false;
  }
}

// ============================================================================
// Plugin Directory Scanning
// ============================================================================

/**
 * Scan a plugin directory for skills with SKILL.md frontmatter.
 *
 * Iterates bundles and skills, checks disabled state, reads SKILL.md,
 * resolves ownership, and collects into the provided Map keyed by ownershipKey.
 */
async function scanPluginDir(
  pluginsDir: string,
  source: "core" | "user",
  plugins: Map<string, DiscoveredPlugin>,
  isVerbose: boolean,
): Promise<void> {
  const bundles = await discoverBundlesAsync(pluginsDir);
  for (const bundle of bundles) {
    const bundleDir = path.join(pluginsDir, bundle);

    // Skip entire bundle if disabled via .config (ADR-129)
    if (await isDisabledByConfig(bundleDir)) {
      if (isVerbose) {
        console.log(`   Skipping disabled bundle: ${bundle} (.config)`);
      }
      continue;
    }

    const skillsDir = path.join(bundleDir, "skills");

    try {
      const entries = await fs.readdir(skillsDir, { withFileTypes: true });
      const skills = entries
        .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
        .map((entry) => entry.name);

      for (const skill of skills) {
        const skillDir = path.join(skillsDir, skill);

        // Skip skill if disabled via .config (ADR-129)
        if (await isDisabledByConfig(skillDir)) {
          if (isVerbose) {
            console.log(
              `   Skipping disabled skill: ${bundle}/${skill} (.config)`,
            );
          }
          continue;
        }

        // Resolve config and web directory paths (SKILL.md frontmatter — ADR-432)
        const resolved = await resolveSkillPaths(skillDir);
        if (!resolved) continue; // No SKILL.md with x-augur-config found

        const { configPath, dashboardDir, apiDir, libDir } = resolved;

        try {
          const content = await fs.readFile(configPath, "utf8");
          const config = parseSkillMdConfig(configPath, content);

          if (!config?.contributes_to) {
            if (isVerbose) {
              console.log(
                `   Skipping ${bundle}/${skill}: no dashboard contribution signal in SKILL.md`,
              );
            }
            continue;
          }

          const ownership = resolveOwnership(config, configPath, bundle, skill);
          const hubId = normalizeRouteSegment(config.contributes_to);

          if (plugins.has(ownership.ownershipKey)) {
            const existing = plugins.get(ownership.ownershipKey)!;
            throw new Error(
              [
                `Duplicate ownership key "${ownership.ownershipKey}" in ${source} plugins.`,
                `- ${existing.configPath}`,
                `- ${configPath}`,
              ].join("\n"),
            );
          }

          const plugin: DiscoveredPlugin = {
            bundle,
            skill,
            hubId,
            role: ownership.role,
            extendsHubId: ownership.extendsHubId,
            routePrefix: ownership.routePrefix,
            mountPath: ownership.mountPath,
            ownershipKey: ownership.ownershipKey,
            dashboardPath: (await dirExists(dashboardDir))
              ? dashboardDir
              : null,
            apiPath: (await dirExists(apiDir)) ? apiDir : null,
            libPath: (await dirExists(libDir)) ? libDir : null,
            configPath,
            source,
            dependencies: {
              required: config.dependencies?.required ?? [],
              optional: config.dependencies?.optional ?? [],
            },
          };

          plugins.set(ownership.ownershipKey, plugin);

          if (isVerbose) {
            const roleSuffix =
              plugin.role === "extension"
                ? ` [extension of /${plugin.extendsHubId}]`
                : " [primary]";
            console.log(
              `   Found: ${bundle}/${skill} -> /${plugin.mountPath} (${source})${roleSuffix}`,
            );
            console.log(
              `     Dashboard: ${plugin.dashboardPath ? "yes" : "no"}`,
            );
            console.log(`     API: ${plugin.apiPath ? "yes" : "no"}`);
            console.log(`     Lib: ${plugin.libPath ? "yes" : "no"}`);
          }
        } catch (err) {
          // Invalid YAML/ownership should fail fast. ENOENT shouldn't happen
          // since resolveSkillPaths already checked existence, but be safe.
          if ((err as NodeJS.ErrnoException)?.code === "ENOENT") {
            continue;
          }
          throw err;
        }
      }
    } catch (err) {
      // Missing bundles are expected; parse/validation errors must fail.
      if ((err as NodeJS.ErrnoException)?.code === "ENOENT") {
        continue;
      }
      throw err;
    }
  }
}

// ============================================================================
// Client Skill Directory Scanning
// ============================================================================

/**
 * Marker in SKILL.md header that identifies auto-generated stubs.
 * These should not be re-discovered as independent skills.
 */
const ADAPTED_COPY_MARKER = "AUGUR-GENERATED";

/**
 * Scan a flat client skill directory for skills with SKILL.md frontmatter.
 *
 * Unlike scanPluginDir() which expects {bundle}/skills/{skill}/ hierarchy,
 * client dirs are flat: {clientDir}/{skill}/SKILL.md.
 *
 * Skills without SKILL.md (or without x-augur-config) are instruction-only and skipped.
 * Adapted copies (SKILL.md with AUGUR-ADAPTED-COPY marker) are skipped.
 * The bundle is set to the hub value (contributes_to) so ADR-235 passes.
 */
async function scanClientSkillDir(
  clientDir: string,
  clientId: string,
  plugins: Map<string, DiscoveredPlugin>,
  isVerbose: boolean,
): Promise<void> {
  let entries;
  try {
    entries = await fs.readdir(clientDir, { withFileTypes: true });
  } catch {
    return; // Directory unreadable — skip
  }

  const skills = entries
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
    .map((entry) => entry.name);

  for (const skill of skills) {
    const skillDir = path.join(clientDir, skill);

    // Skip adapted copies: check for marker anywhere in SKILL.md
    // The marker appears as an HTML comment after the YAML frontmatter
    // closing ---, so its line number varies with frontmatter length.
    const skillMdPath = path.join(skillDir, "SKILL.md");
    try {
      const skillMdContent = await fs.readFile(skillMdPath, "utf8");
      if (skillMdContent.includes(ADAPTED_COPY_MARKER)) {
        if (isVerbose) {
          console.log(
            `   Skipping adapted copy: ${clientId}/${skill}`,
          );
        }
        continue;
      }
    } catch {
      // No SKILL.md — not an adapted copy, continue checking
    }

    // Instruction-only skills (no SKILL.md with x-augur-config) are not mountable
    const resolved = await resolveSkillPaths(skillDir);
    if (!resolved) {
      if (isVerbose) {
        console.log(
          `   Skipping instruction-only: ${clientId}/${skill} (no SKILL.md with x-augur-config)`,
        );
      }
      continue;
    }

    const { configPath, dashboardDir, apiDir, libDir } = resolved;

    try {
      const content = await fs.readFile(configPath, "utf8");
      const config = parseSkillMdConfig(configPath, content);

      if (!config?.contributes_to) {
        if (isVerbose) {
          console.log(
            `   Skipping ${clientId}/${skill}: no dashboard contribution signal in SKILL.md`,
          );
        }
        continue;
      }

      const hubId = normalizeRouteSegment(config.contributes_to);
      // Set bundle = hubId so ADR-235 hub alignment check (bundle === hubId) passes
      const bundle = hubId;
      const ownership = resolveOwnership(config, configPath, bundle, skill);

      // Client skills override core/user by ownership key (last-writer-wins)
      if (plugins.has(ownership.ownershipKey) && isVerbose) {
        const existing = plugins.get(ownership.ownershipKey)!;
        console.log(
          `   Client override: ${clientId}/${skill} overrides ${existing.source}/${existing.bundle}/${existing.skill}`,
        );
      }
      removeExistingClientSkillByName(plugins, skill);

      const plugin: DiscoveredPlugin = {
        bundle,
        skill,
        hubId,
        role: ownership.role,
        extendsHubId: ownership.extendsHubId,
        routePrefix: ownership.routePrefix,
        mountPath: ownership.mountPath,
        ownershipKey: ownership.ownershipKey,
        dashboardPath: (await dirExists(dashboardDir)) ? dashboardDir : null,
        apiPath: (await dirExists(apiDir)) ? apiDir : null,
        libPath: (await dirExists(libDir)) ? libDir : null,
        configPath,
        source: "client",
        dependencies: {
          required: config.dependencies?.required ?? [],
          optional: config.dependencies?.optional ?? [],
        },
      };

      plugins.set(ownership.ownershipKey, plugin);

      if (isVerbose) {
        const roleSuffix =
          plugin.role === "extension"
            ? ` [extension of /${plugin.extendsHubId}]`
            : " [primary]";
        console.log(
          `   Found: ${clientId}/${skill} -> /${plugin.mountPath} (client)${roleSuffix}`,
        );
        console.log(
          `     Dashboard: ${plugin.dashboardPath ? "yes" : "no"}`,
        );
        console.log(`     API: ${plugin.apiPath ? "yes" : "no"}`);
        console.log(`     Lib: ${plugin.libPath ? "yes" : "no"}`);
      }
    } catch (err) {
      if ((err as NodeJS.ErrnoException)?.code === "ENOENT") {
        continue;
      }
      throw err;
    }
  }
}

// ============================================================================
// Claude Code Plugin Cache Scanning (ADR-430 gap 5)
// ============================================================================

/**
 * Parse a version directory name into a numeric tuple for proper comparison.
 * "1.2.3" → [1, 2, 3]. Non-numeric names get [0].
 * Mirrors _version_key() in src/config/paths.py.
 */
function versionKey(name: string): number[] {
  try {
    return name.split(".").map((x) => {
      const n = parseInt(x, 10);
      return Number.isNaN(n) ? 0 : n;
    });
  } catch {
    return [0];
  }
}

/**
 * Compare two version tuples. Returns positive if a > b, negative if a < b.
 */
function compareVersions(a: number[], b: number[]): number {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const diff = (a[i] ?? 0) - (b[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

/**
 * Scan the Claude Code plugin cache for installed plugin skills.
 *
 * Structure: {cacheDir}/{publisher}/{plugin}/{version}/skills/{skill}/
 *
 * For each publisher/plugin pair, selects the highest version that contains
 * a skills/ directory, then scans skills within it using scanClientSkillDir().
 *
 * Plugin cache skills are scanned first so that managed local client skills
 * (project-brain/capabilities/skills by default) can override them via the ownership-key Map.
 */
async function scanPluginCacheDir(
  cacheDir: string,
  plugins: Map<string, DiscoveredPlugin>,
  isVerbose: boolean,
): Promise<void> {
  let publishers;
  try {
    publishers = await fs.readdir(cacheDir, { withFileTypes: true });
  } catch {
    return; // Cache directory unreadable or missing
  }

  for (const pubEntry of publishers) {
    if (!pubEntry.isDirectory() || pubEntry.name.startsWith(".")) continue;
    const pubDir = path.join(cacheDir, pubEntry.name);

    let pluginEntries;
    try {
      pluginEntries = await fs.readdir(pubDir, { withFileTypes: true });
    } catch {
      continue;
    }

    for (const plugEntry of pluginEntries) {
      if (!plugEntry.isDirectory() || plugEntry.name.startsWith(".")) continue;
      const plugDir = path.join(pubDir, plugEntry.name);

      let versionEntries;
      try {
        versionEntries = await fs.readdir(plugDir, { withFileTypes: true });
      } catch {
        continue;
      }

      // Find versions that contain a skills/ subdirectory
      const versionsWithSkills: { name: string; key: number[] }[] = [];
      for (const vEntry of versionEntries) {
        if (!vEntry.isDirectory()) continue;
        const skillsPath = path.join(plugDir, vEntry.name, "skills");
        if (await dirExists(skillsPath)) {
          versionsWithSkills.push({
            name: vEntry.name,
            key: versionKey(vEntry.name),
          });
        }
      }

      if (versionsWithSkills.length === 0) continue;

      // Select highest version (numeric comparison, mirrors Python _version_key)
      versionsWithSkills.sort((a, b) => compareVersions(b.key, a.key));
      const bestVersion = versionsWithSkills[0].name;
      const skillsDir = path.join(plugDir, bestVersion, "skills");
      const clientId = `plugin:${pubEntry.name}/${plugEntry.name}`;

      if (isVerbose) {
        console.log(
          `   Plugin cache: ${clientId} v${bestVersion} -> ${skillsDir}`,
        );
      }

      await scanClientSkillDir(skillsDir, clientId, plugins, isVerbose);
    }
  }
}

// ============================================================================
// Manifest-based Discovery (Phase 4b)
// ============================================================================

/**
 * Path to the canonical skill manifest generated by skill_discovery.
 * When present and fresh, this avoids a full filesystem scan.
 */
const SKILL_MANIFEST_FILENAME = "skill-manifest.json";

/**
 * Try to load plugins from the canonical skill manifest.
 *
 * The manifest is generated by `scripts/generate-skill-manifest.py` and
 * contains all discovered skills with their paths and metadata.  Each
 * entry is converted to a DiscoveredPlugin by resolving dashboard/api
 * dirs relative to the skill path.
 *
 * Returns null if the manifest is missing, stale, or unparseable —
 * callers should fall back to filesystem scanning.
 */
async function tryLoadFromManifest(
  config: MountConfig,
  isVerbose: boolean,
): Promise<DiscoveredPlugin[] | null> {
  if (hasLocalSkillRoots(config)) {
    if (isVerbose) {
      console.log("   Local skill roots enabled — falling back to live skill scan");
    }
    return null;
  }

  const manifestPath = path.join(
    config.repoRoot,
    "docs",
    "generated",
    SKILL_MANIFEST_FILENAME,
  );

  let raw: string;
  try {
    raw = await fs.readFile(manifestPath, "utf8");
  } catch {
    return null; // Manifest not found — fall back to scan
  }

  let manifest: {
    skills?: Array<{
      id: string;
      path: string;
      display_name?: string;
      hub?: string;
      master?: string;
      plugin?: string;
    }>;
    generated_at?: string;
  };
  try {
    manifest = JSON.parse(raw);
  } catch {
    if (isVerbose) {
      console.log("   Manifest exists but is not valid JSON — falling back to scan");
    }
    return null;
  }

  if (!manifest.skills || !Array.isArray(manifest.skills)) {
    return null;
  }

  // Check staleness: if manifest is older than 10 minutes, prefer live scan
  if (manifest.generated_at) {
    const age = Date.now() - new Date(manifest.generated_at).getTime();
    const MAX_AGE_MS = 10 * 60 * 1000;
    if (age > MAX_AGE_MS) {
      if (isVerbose) {
        console.log(`   Manifest is ${Math.round(age / 1000)}s old — falling back to scan`);
      }
      return null;
    }
  }

  const merged = new Map<string, DiscoveredPlugin>();

  for (const entry of manifest.skills) {
    const skillDir = path.isAbsolute(entry.path)
      ? entry.path
      : path.join(config.repoRoot, entry.path);
    if (!isManagedSkillDirAllowed(config, skillDir)) {
      if (isVerbose) {
        console.log(`   Skipping manifest skill outside managed dashboard roots: ${entry.path}`);
      }
      continue;
    }
    const skillName = path.basename(skillDir);
    const augurSubdir = path.join(skillDir, "augur");
    const dashboardDir = path.join(augurSubdir, "dashboard");
    const apiDir = path.join(augurSubdir, "api");
    const libDir = path.join(augurSubdir, "lib");

    // Need SKILL.md with x-augur-config to be mountable
    const skillMd = path.join(skillDir, "SKILL.md");
    let skillMdContent: string;
    try {
      skillMdContent = fsSync.readFileSync(skillMd, "utf8");
    } catch {
      continue; // No SKILL.md — skip
    }
    const skillConfig = parseSkillMdConfig(skillMd, skillMdContent);
    if (!skillConfig?.contributes_to) {
      continue;
    }

    const hubId = normalizeRouteSegment(skillConfig.contributes_to);
    const bundle = hubId;
    const ownership = resolveOwnership(skillConfig, skillMd, bundle, skillName);

    const plugin: DiscoveredPlugin = {
      bundle,
      skill: skillName,
      hubId,
      role: ownership.role,
      extendsHubId: ownership.extendsHubId,
      routePrefix: ownership.routePrefix,
      mountPath: ownership.mountPath,
      ownershipKey: ownership.ownershipKey,
      dashboardPath: fsSync.existsSync(dashboardDir) ? dashboardDir : null,
      apiPath: fsSync.existsSync(apiDir) ? apiDir : null,
      libPath: fsSync.existsSync(libDir) ? libDir : null,
      configPath: skillMd,
      source: "client",
      dependencies: {
        required: skillConfig.dependencies?.required ?? [],
        optional: skillConfig.dependencies?.optional ?? [],
      },
    };

    merged.set(ownership.ownershipKey, plugin);
  }

  if (isVerbose) {
    console.log(`   Loaded ${merged.size} plugins from manifest`);
  }

  return Array.from(merged.values());
}

// ============================================================================
// Public API
// ============================================================================

/**
 * Discover all plugins with SKILL.md frontmatter configs.
 *
 * Scans the managed dashboard skill roots, including canonical
 * project-brain/capabilities/skills and any enabled private-vault roots.
 */
export async function discoverPlugins(
  config: MountConfig,
): Promise<DiscoveredPlugin[]> {
  // Try manifest-based discovery first (fast path)
  const fromManifest = await tryLoadFromManifest(config, config.isVerbose);
  if (fromManifest !== null && fromManifest.length > 0) {
    return fromManifest;
  }

  // Fallback: full filesystem scan
  const merged = new Map<string, DiscoveredPlugin>();

  // Phase 1: Plugin cache skills (lowest priority)
  if (config.pluginCacheDir) {
    await scanPluginCacheDir(config.pluginCacheDir, merged, config.isVerbose);
  }

  // Phase 2: Managed local skill roots (highest priority)
  for (const [clientId, clientDir] of Object.entries(config.clientSkillDirs)) {
    await scanClientSkillDir(clientDir, clientId, merged, config.isVerbose);
  }

  return Array.from(merged.values());
}
