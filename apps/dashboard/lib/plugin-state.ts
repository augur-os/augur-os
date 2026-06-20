/**
 * Plugin State Reader (ADR-129)
 *
 * Reads plugin enabled/disabled state from runtime-backed local skill state
 * for canonical root skills and legacy `.config` files only for old bundle
 * layouts. Replaces the centralized plugin_state.json approach.
 *
 * Canonical root skills: runtime `state/dashboard/skills-state.yaml`
 * Legacy plugin bundles: `.config`
 *
 * Backward-compatible API — callers of isPluginEnabled() don't need changes.
 */

import fs from "fs";
import path from "path";
import {
  discoverRepoRoot,
  getAllPluginDirs,
  getClientSkillDirs,
} from "./plugin-discovery/paths";
import { readConfigFile, clearConfigCache } from "./skill-config";

type PluginKind = "auto" | "hub" | "skill";

function isDirectory(p: string): boolean {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}

function getSkillStateInDir(
  pluginsDir: string,
  hub: string,
  skillId: string,
): boolean {
  const skillDir = path.join(pluginsDir, hub, "skills", skillId);
  if (!isDirectory(skillDir)) {
    return false;
  }
  const hubConfig = readConfigFile(path.join(pluginsDir, hub));
  if (!hubConfig.enabled) {
    return false;
  }
  const skillConfig = readConfigFile(skillDir);
  return skillConfig.enabled;
}

function isHubEnabled(hubId: string): boolean {
  // Check legacy plugins/ dirs for hub-level .config
  const pluginDirs = getAllPluginDirs();

  for (const dir of pluginDirs) {
    const hubDir = path.join(dir, hubId);
    if (isDirectory(hubDir)) {
      return readConfigFile(hubDir).enabled;
    }
  }

  // Check client skill dirs: a hub is considered enabled if any client skill
  // contributes to it. Client skills live in flat dirs (skills/{skill}/)
  // and declare their hub via x-augur-dashboard-pages in SKILL.md frontmatter
  // (ADR-802 Phase 2: x-augur-hub removed from frontmatter).
  // Since there's no hub-level .config in client dirs, default to enabled
  // if at least one skill in that hub exists.
  const clientDirs = getClientSkillDirs();
  for (const [, clientDir] of Object.entries(clientDirs)) {
    try {
      const entries = fs.readdirSync(clientDir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
        const skillMd = path.join(clientDir, entry.name, "SKILL.md");
        try {
          const content = fs.readFileSync(skillMd, "utf8");
          // Derive hub from x-augur-dashboard-pages routes: "/workspace/foo" → "workspace"
          // Matches both bare string entries ("- /workspace/foo") and object entries
          // ("  route: /workspace/foo") under x-augur-dashboard-pages.
          const pagesMatch = content.match(/^x-augur-dashboard-pages:/m);
          if (pagesMatch) {
            // Match bare string entries: "- /workspace/foo"
            const bareRoutes = content.matchAll(/^\s+-\s+["']?(\/[^\s"']+)["']?/gm);
            for (const rm of bareRoutes) {
              const segment = rm[1].replace(/^\//, "").split("/")[0];
              if (segment === hubId) return true;
            }
            // Match object entries: "- route: /workspace/foo" (YAML list item with route key)
            const objRoutes = content.matchAll(/^\s*-\s+route:\s+["']?(\/[^\s"']+)["']?/gm);
            for (const rm of objRoutes) {
              const segment = rm[1].replace(/^\//, "").split("/")[0];
              if (segment === hubId) return true;
            }
          }
        } catch {
          // No SKILL.md or unreadable — skip
        }
      }
    } catch {
      // Client dir unreadable — skip
    }
  }

  return false; // Hub not found in any plugin dir or client skill dir
}

function isSkillEnabled(skillId: string, hubId?: string): boolean {
  // Check canonical root skill dirs first; readConfigFile() maps them to
  // runtime-backed local skill state rather than repo-owned `.config`.
  const clientDirs = getClientSkillDirs();
  for (const [, clientDir] of Object.entries(clientDirs)) {
    const skillDir = path.join(clientDir, skillId);
    if (isDirectory(skillDir)) {
      const skillConfig = readConfigFile(skillDir);
      return skillConfig.enabled;
    }
  }

  // Fallback: check legacy plugins/ dirs
  const pluginDirs = getAllPluginDirs();

  if (hubId) {
    for (const dir of pluginDirs) {
      if (getSkillStateInDir(dir, hubId, skillId)) {
        return true;
      }
    }
    return false;
  }

  for (const dir of pluginDirs) {
    try {
      if (!isDirectory(dir)) continue;
      for (const hub of fs.readdirSync(dir)) {
        if (hub.startsWith(".")) continue;
        if (getSkillStateInDir(dir, hub, skillId)) {
          return true;
        }
      }
    } catch (err) {
      console.warn(
        `Failed to read legacy plugin directory ${dir} for skill enablement check:`,
        err,
      );
    }
  }

  return false;
}

/**
 * Check if a plugin/skill/hub is enabled.
 *
 * Canonical root skills resolve from runtime local skill state. Legacy plugin
 * bundle dirs still read `.config`. Missing local state defaults to enabled.
 *
 * @param nameOrId - Skill name (e.g., "career") or hub ID (e.g., "ai")
 * @param kind - Explicit lookup mode (`hub`, `skill`, or `auto`)
 * @returns true if enabled, false if disabled
 */
export function isPluginEnabled(
  nameOrId: string,
  kind: PluginKind = "auto",
): boolean {
  if (kind === "hub") {
    return isHubEnabled(nameOrId);
  }
  if (kind === "skill") {
    return isSkillEnabled(nameOrId);
  }

  // Auto mode: enabled if it's an enabled skill OR an enabled hub
  return isSkillEnabled(nameOrId) || isHubEnabled(nameOrId);
}

/**
 * Clear the plugin state cache.
 */
function clearPluginStateCache(): void {
  clearConfigCache();
}

/**
 * Get the path to the (legacy) plugin state file.
 * @deprecated Use .config files instead (ADR-129)
 */
function getPluginStateFile(): string {
  const repoRoot = discoverRepoRoot();
  return path.join(repoRoot, "config", "system", "plugin_state.json");
}

/**
 * Get user data base directory.
 */
function getUserDataBase(): string {
  const envBase = process.env.AUGUR_USER || process.env.AUGUR_ROOT;

  if (envBase && envBase.trim()) {
    const resolved = path.resolve(
      envBase.trim().replace(/^~/, process.env.HOME || ""),
    );
    if (fs.existsSync(resolved)) {
      return resolved;
    }
  }

  return discoverRepoRoot();
}
