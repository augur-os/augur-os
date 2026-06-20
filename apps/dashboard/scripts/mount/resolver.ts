/**
 * Mount Plugins — Resolver
 *
 * Filters discovered plugins by enabled/disabled state and dev-focus
 * hub filters. Produces the final list of plugins to mount.
 *
 * Extracted from mount-plugins.ts to isolate filtering/resolution
 * logic from discovery and mounting.
 */

import { isPluginEnabled } from "../../lib/plugin-state.js";
import type { DiscoveredPlugin, MountConfig } from "./types";

/**
 * Filter discovered plugins to only those that should be mounted.
 *
 * Checks three conditions:
 * 1. Skill is enabled (per plugin-state)
 * 2. Hub is enabled (per plugin-state)
 * 3. For extensions, the parent hub is also enabled
 *
 * Returns the enabled plugins. Callers can diff against allPlugins
 * to find the disabled set.
 */
export function filterEnabledPlugins(
  allPlugins: DiscoveredPlugin[],
): DiscoveredPlugin[] {
  return allPlugins.filter((plugin) => {
    // Check by skill name (e.g., "career", "health")
    if (!isPluginEnabled(plugin.skill, "skill")) {
      return false;
    }
    // Always check hub by explicit hub mode to avoid hub/skill name collisions.
    if (!isPluginEnabled(plugin.hubId, "hub")) {
      return false;
    }
    // Extensions should also respect the owning hub's enabled state.
    if (plugin.extendsHubId && !isPluginEnabled(plugin.extendsHubId, "hub")) {
      return false;
    }
    return true;
  });
}

/**
 * Apply AUGUR_DEV_HUBS dev-focus filter.
 *
 * When AUGUR_DEV_HUBS is set, only hubs in the filter (plus shell hubs)
 * are mounted. This dramatically reduces Turbopack's page count during
 * focused development.
 *
 * Returns the filtered array. Does not mutate the input.
 */
export function applyDevHubFilter(
  plugins: DiscoveredPlugin[],
  config: MountConfig,
): DiscoveredPlugin[] {
  if (!config.devHubFilter) {
    return plugins;
  }

  const filtered = plugins.filter((plugin) => {
    return (
      config.devHubFilter!.has(plugin.hubId) ||
      (plugin.extendsHubId && config.devHubFilter!.has(plugin.extendsHubId))
    );
  });

  const skipped = plugins.length - filtered.length;
  console.log(
    `\nAUGUR_DEV_HUBS active: mounting ${filtered.length} plugins (${skipped} skipped)`,
  );
  console.log(`   Focused hubs: ${[...config.devHubFilter].join(", ")}`);

  return filtered;
}

/**
 * Detect hub.id collisions in the enabled plugin set.
 *
 * The mount-plugins Map uses hub.id as key for primary plugins.
 * When two skills declare themselves as primary for the same hub.id,
 * the last one wins silently. This function detects that scenario
 * and emits warnings.
 *
 * Note: validateOwnership() in discovery.ts throws a hard error for
 * duplicate primaries. This function catches a subtler case: two skills
 * with different ownership keys but the same effective hub.id, where
 * one could shadow the other's mount path.
 */
export function detectHubIdCollisions(
  plugins: DiscoveredPlugin[],
  warnOnly = false,
): void {
  // Group by mountPath — if two plugins resolve to the same mountPath,
  // the second copy() will overwrite the first's files.
  const byMountPath = new Map<string, DiscoveredPlugin[]>();
  for (const plugin of plugins) {
    const existing = byMountPath.get(plugin.mountPath);
    if (existing) {
      existing.push(plugin);
    } else {
      byMountPath.set(plugin.mountPath, [plugin]);
    }
  }

  for (const [mountPath, group] of byMountPath) {
    if (group.length > 1) {
      const sources = group
        .map((p) => `  - ${p.bundle}/${p.skill} (${p.configPath})`)
        .join("\n");
      const msg =
        `[mount-plugins] ${group.length} plugins resolve to mount path "/${mountPath}":\n${sources}\n` +
        `Fix by ensuring unique hub.id or unique routePrefix values.`;
      if (warnOnly || process.env.MOUNT_WARN_ONLY === "1") {
        console.warn(`WARNING: ${msg}`);
      } else {
        throw new Error(msg);
      }
    }
  }
}
