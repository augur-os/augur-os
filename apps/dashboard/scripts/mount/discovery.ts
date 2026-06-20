/**
 * Mount Plugins — Discovery
 *
 * Finds plugins on disk, parses SKILL.md frontmatter, resolves ownership,
 * and validates for collisions before mounting.
 *
 * Extracted from mount-plugins.ts to isolate the discovery phase
 * from the copy/mount phase.
 *
 * WS5 decomposition: this file is now a thin re-export barrel over the
 * cohesive discovery.* sub-modules. The public surface is unchanged —
 * every importer of "./discovery" keeps working.
 */

export { dirExists, discoverPlugins } from "./discovery.scan";
export { resolveOwnership } from "./discovery.ownership";
export {
  validateOwnership,
  validateMountPathCollisions,
} from "./discovery.validation";
