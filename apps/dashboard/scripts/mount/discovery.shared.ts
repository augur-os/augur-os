/**
 * Mount Plugins — Discovery shared helpers
 *
 * Internal utilities shared across the discovery sub-modules (frontmatter
 * parsing, route/path normalization, managed-root checks, plugin-map edits).
 *
 * Split out of discovery.ts (WS5 decomposition) — moved verbatim.
 */

import fsSync from "fs";
import path from "path";
import yaml from "yaml";
import type { DiscoveredPlugin, MountConfig } from "./types";

// ============================================================================
// Helpers
// ============================================================================

/**
 * Parse YAML frontmatter from markdown content (between --- markers).
 * Returns the parsed data object, or empty object if no frontmatter found.
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

export function normalizeRouteSegment(segment: string): string {
  return segment.trim().replace(/^\/+|\/+$/g, "");
}

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
  return relative === "" || (!!relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

export function isManagedSkillDirAllowed(config: MountConfig, skillDir: string): boolean {
  return Object.values(config.clientSkillDirs).some((root) => isWithinDir(skillDir, root));
}

export function hasLocalSkillRoots(config: MountConfig): boolean {
  const roots = Object.values(config.clientSkillDirs).map(canonicalPath);
  return new Set(roots).size > 1 || Object.keys(config.clientSkillDirs).some((id) => id !== "augur");
}

export function removeExistingClientSkillByName(
  plugins: Map<string, DiscoveredPlugin>,
  skill: string,
): void {
  for (const [key, plugin] of plugins.entries()) {
    if (plugin.source === "client" && plugin.skill === skill) {
      plugins.delete(key);
    }
  }
}
