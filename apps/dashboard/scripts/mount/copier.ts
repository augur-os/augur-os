/**
 * Mount Plugins — Copier
 *
 * File copy operations with warning headers, sync-based mounting
 * (to avoid Tailwind race conditions), tsconfig generation, and
 * root redirect generation.
 *
 * Sub-modules (extracted for maintainability):
 * - file-utils.ts:    Low-level FS helpers (symlink, getAllFiles, removeDir)
 * - copy-headers.ts:  Header injection during file copy
 * - cleanup.ts:       Stale mount removal (cleanPluginMounts, cleanDisabledMounts)
 * - cache.ts:         Next.js cache management (clearNextCache)
 */

import fs from "fs/promises";
import path from "path";
import { isSymlink, getAllFiles, cleanEmptyDirs, MOUNT_MARKER } from "./file-utils";
import { copyDir, SKIP_EXTENSIONS } from "./copy-headers";
import type { DiscoveredPlugin, MountResult, MountConfig } from "./types";

// ============================================================================
// Re-exports — maintain backward compatibility for index.ts barrel
// ============================================================================

export { MOUNT_MARKER } from "./file-utils";
export { cleanPluginMounts, cleanDisabledMounts } from "./cleanup";
export { clearNextCache } from "./cache";

// ============================================================================
// Mount (Sync Strategy)
// ============================================================================

/**
 * Mount a plugin by syncing files (copy + delete stale).
 *
 * We use copying instead of symlinks because:
 * 1. Turbopack/webpack can't resolve modules for files outside the project
 * 2. Copied files resolve imports from the dashboard's node_modules
 * 3. Avoids cross-repo symlink issues
 *
 * IMPORTANT: We use a SYNC approach to prevent race conditions with Tailwind CSS.
 * Previous approaches (delete-then-copy, atomic-rename) still had brief windows
 * where files didn't exist, causing ENOENT errors when Tailwind tried to stat().
 *
 * Sync approach:
 * 1. Copy all source files to target (overwriting existing files in-place)
 * 2. Delete files in target that don't exist in source
 *
 * This ensures files that exist in BOTH source and target are NEVER missing -
 * they're overwritten in-place. Only truly stale files (not in source) get deleted.
 */
async function mountSinglePlugin(
  source: string,
  target: string,
  repoRoot: string,
  mountPath?: string,
): Promise<void> {
  // Ensure parent directory exists
  const parentDir = path.dirname(target);
  await fs.mkdir(parentDir, { recursive: true });

  // Remove existing symlink if present
  if (await isSymlink(target)) {
    await fs.unlink(target);
  }

  // Get list of files in source and target.
  // Exclude SKIP_EXTENSIONS from source so that pre-existing copies in the
  // target are treated as stale and removed during sync step 3.
  const sourceFiles = await getAllFiles(source, "", SKIP_EXTENSIONS);
  const targetFiles = await getAllFiles(target);

  // Step 1: Copy all source files to target (overwrites existing)
  // This ensures files that exist in both are never "missing"
  await copyDir(source, target, repoRoot);

  // Step 1.5: Generate root redirect if source has no page.tsx but has sub-routes
  if (mountPath && !sourceFiles.has("page.tsx")) {
    await generateRootRedirect(target, mountPath);
    // Mark as source file so stale cleanup won't delete it
    sourceFiles.add("page.tsx");
  }

  // Step 2: Create/update marker file
  await fs.writeFile(
    path.join(target, MOUNT_MARKER),
    `Mounted from: ${source}\nMounted at: ${new Date().toISOString()}\n`,
  );

  // Step 3: Delete files in target that don't exist in source (stale files)
  for (const targetFile of targetFiles) {
    if (!sourceFiles.has(targetFile) && targetFile !== MOUNT_MARKER) {
      const filePath = path.join(target, targetFile);
      try {
        // Make file writable first (we set them read-only)
        await fs.chmod(filePath, 0o644);
        await fs.unlink(filePath);
      } catch {
        // File might already be deleted or inaccessible
      }
    }
  }

  // Step 4: Clean up empty directories left after file deletion
  await cleanEmptyDirs(target);
}

// ============================================================================
// tsconfig Generation
// ============================================================================

/**
 * Generate a tsconfig.json in the plugin source directory to enable
 * IDE support (path aliases, module resolution from dashboard).
 */
async function generateTsConfig(
  pluginDir: string,
  config: MountConfig,
): Promise<void> {
  const baseConfigPath = path.join(
    config.repoRoot,
    "plugins",
    "tsconfig.base.json",
  );
  const dashboardPath = path.join(config.repoRoot, "apps", "dashboard");

  // TypeScript accepts slash paths on all platforms; keep generated files stable on Windows.
  const toPortablePath = (relativePath: string) => relativePath.replace(/\\/g, "/");
  const relativeToBase = toPortablePath(path.relative(pluginDir, baseConfigPath));
  const relativeToDashboard = toPortablePath(
    path.relative(pluginDir, dashboardPath),
  );

  const tsConfig = {
    _generated:
      "AUTO-GENERATED by mount-plugins.ts - DO NOT EDIT. Run 'npm run mount-plugins' to regenerate.",
    extends: relativeToBase,
    compilerOptions: {
      baseUrl: relativeToDashboard,
    },
    include: ["."],
    exclude: ["node_modules"],
  };

  const tsConfigPath = path.join(pluginDir, "tsconfig.json");
  const nextContent = `${JSON.stringify(tsConfig, null, 2)}\n`;

  if (config.isVerbose) {
    console.log(`   Generating tsconfig.json in ${pluginDir}`);
  }

  try {
    const existing = await fs.readFile(tsConfigPath, "utf8");
    if (existing === nextContent) {
      return;
    }
  } catch {
    // File missing or unreadable — write a fresh copy below.
  }

  await fs.writeFile(tsConfigPath, nextContent, "utf8");
}

// ============================================================================
// Root Redirect Generation
// ============================================================================

/**
 * Generate a root redirect page.tsx if the skill has sub-routes but no root page.
 */
async function generateRootRedirect(
  targetPath: string,
  mountPath: string,
): Promise<void> {
  const rootPage = path.join(targetPath, "page.tsx");

  // Always regenerate (caller only invokes when source has no page.tsx).
  // Previous versions returned early when the file existed, which prevented
  // the AUTO-GENERATED header from being added to stale redirects.

  const PREFERRED = ["overview", "index", "lighting", "loops", "tools", "create", "terminal"];
  const SKIP_DIRS = new Set(["hooks", "lib", "components", "tabs", "api"]);
  let firstSub: string | null = null;

  try {
    const entries = await fs.readdir(targetPath, { withFileTypes: true });
    const dirs = entries
      .filter((e) => e.isDirectory() && !e.name.startsWith(".") && !SKIP_DIRS.has(e.name))
      .map((e) => e.name);

    for (const pref of PREFERRED) {
      if (dirs.includes(pref)) {
        const hasPage = await fs.access(path.join(targetPath, pref, "page.tsx")).then(() => true).catch(() => false);
        if (hasPage) { firstSub = pref; break; }
      }
    }

    if (!firstSub) {
      for (const dir of dirs.sort()) {
        if (dir.startsWith("[")) continue;
        const hasPage = await fs.access(path.join(targetPath, dir, "page.tsx")).then(() => true).catch(() => false);
        if (hasPage) { firstSub = dir; break; }
      }
    }
  } catch {
    return;
  }

  if (!firstSub) return;

  await fs.writeFile(
    rootPage,
    `/**
 * AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
 *
 * Root redirect page generated by mount-plugins.
 * This skill has sub-routes but no root page.tsx in the plugin source.
 *
 * Redirects to the first available sub-route.
 */

import { redirect } from 'next/navigation';
export default function Page() { redirect('/${mountPath}/${firstSub}'); }
`,
    "utf-8",
  );
}

// ============================================================================
// Mount All Plugins
// ============================================================================

/**
 * Mount all discovered plugins into the Next.js app directory.
 *
 * Custom pages mount at /app/{skill}/ (flat, no hub nesting).
 * Skills with only auto pages are skipped — the browse detail panel handles them.
 *
 * After mounting, generates root redirect pages for skills that have
 * sub-routes but no root page.tsx (e.g., /app/home-automation -> /app/home-automation/lighting).
 *
 * For each plugin, generates tsconfig for IDE support.
 * Dashboard page mounting and API route mounting were removed in earlier migrations.
 * lib/plugins/ mounting removed — skill libs are imported directly from skills/.
 */
export async function mountPlugins(
  plugins: DiscoveredPlugin[],
  config: MountConfig,
): Promise<MountResult[]> {
  const results: MountResult[] = [];

  for (const plugin of plugins) {
    // Dashboard page mounting removed — catch-all [[...slug]] routes serve
    // all hub pages via registry.ts + dynamic imports (see generate-registry.ts).
    // IDE tsconfig generation is still useful for plugin source editing.
    if (plugin.dashboardPath && !config.isDryRun) {
      await generateTsConfig(plugin.dashboardPath, config);
    }

    // API routes consolidated into catch-all proxy at api/[...proxy]/route.ts
    // Individual API route mounting is no longer needed (ADR: universal-mcp-proxy)

    // lib/plugins/ mounting removed — skill libs are imported directly from
    // their source at skills/{skill}/augur/lib/ via @/features/ alias.
  }

  return results;
}
