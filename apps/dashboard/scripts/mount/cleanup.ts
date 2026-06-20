/**
 * Mount Plugins — Cleanup
 *
 * Identifies and removes stale plugin mounts (symlinks and copied
 * directories) from the app/ and api/ trees.
 * Uses the .plugin-mount marker to distinguish mounted plugins
 * from core shell pages.
 *
 * Extracted from copier.ts to isolate cleanup/teardown logic.
 */

import fs from "fs/promises";
import path from "path";
import { MOUNT_MARKER, isSymlink, removeDir } from "./file-utils";
import { dirExists } from "./discovery";
import type { DiscoveredPlugin, MountConfig } from "./types";

/**
 * Check if a directory is a mounted plugin (has .plugin-mount marker).
 */
export async function isMountedPlugin(dirPath: string): Promise<boolean> {
  try {
    await fs.access(path.join(dirPath, MOUNT_MARKER));
    return true;
  } catch {
    return false;
  }
}

/**
 * Clean up all plugin mounts (symlinks and copied directories).
 *
 * Core shell pages are protected by the absence of a .plugin-mount marker.
 * Only directories WITH the marker are eligible for cleanup (ADR-109 Decision 6).
 */
export async function cleanPluginMounts(config: MountConfig): Promise<void> {
  // Clean hub-based mounts at /{hub}/{skill}/
  // Hub directories contain mounted skill subdirectories, so scan each
  // top-level directory for mounted plugins inside it.
  await cleanMountsInDir(config.appDir, "", config);
  try {
    const topEntries = await fs.readdir(config.appDir, { withFileTypes: true });
    for (const entry of topEntries) {
      if (!entry.isDirectory()) continue;
      if (entry.name.startsWith("(") || entry.name === "api" || entry.name.startsWith(".")) continue;
      const hubDir = path.join(config.appDir, entry.name);
      await cleanMountsInDir(hubDir, `${entry.name}/`, config);
    }
  } catch {
    // Can't read app dir
  }

  // Clean legacy flat mounts under /app/{skill}/ (from previous mount structure)
  const appSubDir = path.join(config.appDir, "app");
  if (await dirExists(appSubDir)) {
    await cleanMountsInDir(appSubDir, "app/", config);
  }

  // Clean API mounts at /api/{hub}/{skill}/
  const apiDir = path.join(config.appDir, "api");
  if (await dirExists(apiDir)) {
    await cleanMountsInDir(apiDir, "api/", config);
    try {
      const apiEntries = await fs.readdir(apiDir, { withFileTypes: true });
      for (const entry of apiEntries) {
        if (!entry.isDirectory()) continue;
        const apiHubDir = path.join(apiDir, entry.name);
        await cleanMountsInDir(apiHubDir, `api/${entry.name}/`, config);
      }
    } catch {
      // Can't read api dir
    }
  }

  // lib/plugins/ mounting removed — skill libs imported directly from skills/.
}

/**
 * Clean mounts in a specific directory. Shared logic for app/ and api/.
 */
async function cleanMountsInDir(
  dir: string,
  prefix: string,
  config: MountConfig,
): Promise<void> {
  const entries = await fs.readdir(dir, { withFileTypes: true });

  for (const entry of entries) {
    const entryPath = path.join(dir, entry.name);

    // Remove symlinks (legacy -- current strategy uses copies with marker)
    if (await isSymlink(entryPath)) {
      if (config.isDryRun) {
        console.log(`   Would remove symlink: ${prefix}${entry.name}`);
      } else {
        await fs.unlink(entryPath);
        console.log(`   Removed symlink: ${prefix}${entry.name}`);
      }
      continue;
    }

    // Remove mounted plugin directories (identified by marker).
    // Directories WITHOUT the marker are core shell pages -- always protected.
    if (entry.isDirectory() && (await isMountedPlugin(entryPath))) {
      if (config.isDryRun) {
        console.log(`   Would remove plugin: ${prefix}${entry.name}`);
      } else {
        await removeDir(entryPath);
        console.log(`   Removed plugin: ${prefix}${entry.name}`);
      }
    }
  }
}

/**
 * Clean mounts for a set of disabled plugins (ADR-095: Disable Hardening).
 *
 * Removes dashboard, api, and lib mount targets for plugins that were
 * discovered but are disabled.
 */
export async function cleanDisabledMounts(
  disabledPlugins: DiscoveredPlugin[],
  config: MountConfig,
): Promise<void> {
  if (disabledPlugins.length === 0) return;

  console.log(
    `\nCleaning mounts of ${disabledPlugins.length} disabled plugins...`,
  );

  for (const plugin of disabledPlugins) {
    // Clean dashboard mount at /{hub}/{skill}/
    const dashTarget = path.join(config.appDir, ...plugin.mountPath.split("/"));
    if (await isMountedPlugin(dashTarget)) {
      await removeDir(dashTarget);
      console.log(`   Removed disabled: ${plugin.mountPath}`);
    }

    // Clean legacy flat mount at /app/{skill}/ (from previous flat structure)
    const legacyDashTarget = path.join(config.appDir, "app", plugin.skill);
    if (await isMountedPlugin(legacyDashTarget)) {
      await removeDir(legacyDashTarget);
      console.log(`   Removed disabled (legacy flat): app/${plugin.skill}`);
    }

    // Clean API mount
    const apiTarget = path.join(
      config.appDir,
      "api",
      ...plugin.mountPath.split("/"),
    );
    if (await isMountedPlugin(apiTarget)) {
      await removeDir(apiTarget);
      console.log(`   Removed disabled: api/${plugin.mountPath}`);
    }

    // lib/plugins/ mounting removed — skill libs imported directly from skills/.
  }
}
