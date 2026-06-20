/**
 * Mount Plugins — Discovery validation
 *
 * Validates ownership keys and mount-path collisions across discovered
 * plugins before mounting.
 *
 * Split out of discovery.ts (WS5 decomposition) — moved verbatim.
 */

import fs from "fs/promises";
import path from "path";
import type { DiscoveredPlugin } from "./types";

// ============================================================================
// Validation
// ============================================================================

/**
 * Validate that no two plugins claim the same ownership key.
 *
 * - Two primaries for the same hub.id is a hard error.
 * - Two extensions with the same routePrefix under the same hub is a hard error.
 */
export function validateOwnership(plugins: DiscoveredPlugin[]): void {
  const primariesByHub = new Map<string, DiscoveredPlugin>();
  const extensionPrefixesByHub = new Map<
    string,
    Map<string, DiscoveredPlugin>
  >();

  for (const plugin of plugins) {
    if (plugin.role === "primary") {
      const hubId = plugin.hubId;
      const existingPrimary = primariesByHub.get(hubId);
      if (existingPrimary) {
        throw new Error(
          [
            `Hub ownership conflict for hub "${hubId}".`,
            `Duplicate primary owners:`,
            `- ${existingPrimary.configPath}`,
            `- ${plugin.configPath}`,
          ].join("\n"),
        );
      }
      primariesByHub.set(hubId, plugin);
      continue;
    }

    const extendsHubId = plugin.extendsHubId;
    const routePrefix = plugin.routePrefix;
    if (!extendsHubId || !routePrefix) {
      throw new Error(
        `Extension/contributor plugin ${plugin.configPath} is missing extends/routePrefix metadata.`,
      );
    }

    if (!extensionPrefixesByHub.has(extendsHubId)) {
      extensionPrefixesByHub.set(extendsHubId, new Map());
    }
    const prefixes = extensionPrefixesByHub.get(extendsHubId)!;
    const existing = prefixes.get(routePrefix);
    if (existing) {
      throw new Error(
        [
          `Extension/contributor routePrefix conflict for hub "${extendsHubId}".`,
          `Duplicate routePrefix "${routePrefix}" declared in:`,
          `- ${existing.configPath}`,
          `- ${plugin.configPath}`,
        ].join("\n"),
      );
    }
    prefixes.set(routePrefix, plugin);
  }

  // Contributors don't need a primary owner check — assembly auto-generates
  // hub metadata if no primary exists.
}

/**
 * Validate that no two plugins produce files at the same mounted path.
 *
 * Scans all source directories and projects their files into the mount
 * namespace. A collision means two plugins would write to the same
 * Next.js route file, which is a hard error.
 *
 * Dashboard files mount at /{hub}/{skill}/ (hub-based routing).
 * API files mount at /api/{hub}/{skill}/.
 */
export async function validateMountPathCollisions(
  plugins: DiscoveredPlugin[],
): Promise<void> {
  const mountedFiles = new Map<
    string,
    { plugin: DiscoveredPlugin; sourcePath: string }
  >();

  const registerFiles = async (
    plugin: DiscoveredPlugin,
    sourceDir: string | null,
    mountType: "dashboard" | "api",
  ): Promise<void> => {
    if (!sourceDir) return;

    const files = await getAllFilesFromDir(sourceDir);
    for (const file of files) {
      const posixFile = file.replace(/\\/g, "/");

      let mountedRelativePath: string;
      if (mountType === "api") {
        mountedRelativePath = path.posix.join(
          `api/${plugin.mountPath}`,
          posixFile,
        );
      } else {
        // Dashboard files mount at /{hub}/{skill}/
        mountedRelativePath = path.posix.join(
          plugin.mountPath,
          posixFile,
        );
      }

      const key = `${mountType}:${mountedRelativePath}`;
      const sourcePath = path.join(sourceDir, file);
      const existing = mountedFiles.get(key);
      if (existing) {
        throw new Error(
          [
            `Route collision detected for ${mountType} path "/${mountedRelativePath}".`,
            `Conflicting source files:`,
            `- ${existing.sourcePath} (${existing.plugin.configPath})`,
            `- ${sourcePath} (${plugin.configPath})`,
          ].join("\n"),
        );
      }
      mountedFiles.set(key, { plugin, sourcePath });
    }
  };

  for (const plugin of plugins) {
    await registerFiles(plugin, plugin.dashboardPath, "dashboard");
    await registerFiles(plugin, plugin.apiPath, "api");
  }
}

/**
 * Get all file paths in a directory recursively.
 * Used by collision validation to enumerate source files.
 */
async function getAllFilesFromDir(
  dir: string,
  base: string = "",
): Promise<Set<string>> {
  const files = new Set<string>();
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const relativePath = base ? `${base}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        const subFiles = await getAllFilesFromDir(
          path.join(dir, entry.name),
          relativePath,
        );
        subFiles.forEach((f) => files.add(f));
      } else {
        files.add(relativePath);
      }
    }
  } catch {
    // Directory doesn't exist
  }
  return files;
}
