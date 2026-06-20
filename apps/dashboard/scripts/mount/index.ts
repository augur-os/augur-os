/**
 * Mount Plugins — Orchestrator
 *
 * Coordinates the full mount-plugins pipeline:
 * 1. Discovery (find plugins on disk, parse SKILL.md metadata)
 * 2. Resolution (filter by enabled state, dev-focus, detect collisions)
 * 3. Validation (ownership conflicts, mount path collisions)
 * 4. Mounting (copy files with headers, sync strategy)
 * 5. Assembly (hub assembly, overview pages, nested layouts)
 *
 * This module replaces the monolithic main() function from mount-plugins.ts.
 * Each phase is handled by a focused module:
 * - discovery.ts: plugin scanning and ownership resolution
 * - resolver.ts:  filtering and collision detection
 * - copier.ts:    file operations, cleanup, cache, assembly
 * - types.ts:     shared type definitions
 */

export {
  discoverPlugins,
  validateOwnership,
  validateMountPathCollisions,
  dirExists,
} from "./discovery";
export {
  filterEnabledPlugins,
  applyDevHubFilter,
  detectHubIdCollisions,
} from "./resolver";
export {
  mountPlugins,
  cleanPluginMounts,
  cleanDisabledMounts,
  clearNextCache,
  MOUNT_MARKER,
} from "./copier";
export type { DiscoveredPlugin, MountResult, MountConfig } from "./types";
