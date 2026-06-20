// Compiled to scripts/dist/mount-plugins.mjs by build-scripts.mjs
/**
 * Mount Plugins - Build-time Plugin Discovery and Mounting
 *
 * Discovers plugins from core and user repositories, then creates symlinks
 * (or copies on Windows) for dashboard/ and api/ folders into the Next.js app.
 *
 * This enables fully independent plugin plugins per ADR-012:
 * - Each plugin contains its own UI (dashboard/) and API (api/) routes
 * - Build-time mounting integrates plugins into the Next.js app directory
 * - User plugins override core plugins with the same hub ID
 *
 * Usage:
 *   npm run mount-plugins [-- --dry-run] [-- --clean] [-- --watch]
 *
 * Environment Variables:
 *   AUGUR_CORE  - Path to core framework (default: auto-detected from cwd)
 *   AUGUR_USER  - Path to user repository (default: ~/Projects/augur)
 *   AUGUR_ROOT  - Project root (fallback for AUGUR_USER)
 *
 * Output:
 *   Creates symlinks in apps/dashboard/app/ for plugin UI and API routes
 *
 * Part of ADR-012: Community Package Extraction
 *
 * This file is the thin ENTRY: it resolves runtime context (scriptDir, repo
 * root, CLI flags) and dispatches to the mount pipeline. Implementation is
 * decomposed into focused modules in ./mount/:
 * - types.ts:         shared type definitions
 * - discovery.ts:     plugin scanning, ownership resolution, validation
 * - resolver.ts:      filtering by enabled state, dev-focus, collision detection
 * - copier.ts:        file copy, cleanup, cache management, hub assembly
 * - index.ts:         barrel exports
 * - runtime-paths.ts: dashboard/scripts/dist/app dir resolution
 * - feature-pages.ts: frontmatter + generated-skill-page helpers
 * - collect-pages.ts: registry page collection (Phase 4b)
 * - dev-state.ts:     TS incremental-state + tab registry regeneration
 * - run.ts:           buildConfig, main() orchestrator, watch mode
 */

import path from "path";
import { fileURLToPath } from "url";
import { discoverRepoRoot } from "../lib/plugin-discovery";
import { main, startWatchMode, type MountRuntimeContext } from "./mount/run";

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Configuration
// ============================================================================

const REPO_ROOT = discoverRepoRoot(__dirname);

// CLI flags
const isDryRun = process.argv.includes("--dry-run");
const isClean = process.argv.includes("--clean");
const isWatch = process.argv.includes("--watch");
const isVerbose =
  process.argv.includes("--verbose") || process.argv.includes("-v");
const isWarnOnly =
  process.argv.includes("--warn-only") || process.env.MOUNT_WARN_ONLY === "1";

const ctx: MountRuntimeContext = {
  scriptDir: __dirname,
  repoRoot: REPO_ROOT,
  isDryRun,
  isClean,
  isVerbose,
  isWarnOnly,
};

if (isWatch) {
  startWatchMode(ctx).catch((err) => {
    console.error("Fatal error:", err);
    process.exit(1);
  });
} else {
  main(ctx).catch((err) => {
    console.error("Fatal error:", err);
    process.exit(1);
  });
}
