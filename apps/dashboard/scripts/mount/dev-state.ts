/**
 * Mount Plugins — Dev-State Helpers
 *
 * TypeScript incremental-state clearing, Next.js dev-lock detection, and the
 * tab-registry subprocess regeneration. Extracted verbatim from
 * mount-plugins.ts (helpers that need the entry's scriptDir thread it in).
 */

import fs from "fs/promises";
import { existsSync } from "fs";
import path from "path";
import { execFileSync } from "child_process";
import {
  getDashboardRoot,
  getDistScriptsDir,
  getScriptsRoot,
} from "./runtime-paths";

export async function clearDashboardTypeScriptIncrementalState(
  dashboardRoot: string,
): Promise<void> {
  const buildInfoPath = path.join(dashboardRoot, "tsconfig.tsbuildinfo");
  const removablePaths = new Set<string>();

  try {
    const realPath = await fs.realpath(buildInfoPath);
    removablePaths.add(realPath);
  } catch {
    // Path may not exist yet, or may not be a symlink. Fall back to the local path.
  }

  removablePaths.add(buildInfoPath);

  for (const candidate of removablePaths) {
    try {
      await fs.rm(candidate, { force: true });
    } catch {
      // Best-effort cleanup only. TypeScript will recreate the file on next run.
    }
  }
}

export function hasNextDevLock(dashboardRoot: string): boolean {
  return existsSync(path.join(dashboardRoot, ".next", "dev", "lock"));
}

/**
 * Run the tab registry generator as a subprocess.
 * Uses the compiled .mjs if available, falls back to tsx.
 */
export function regenerateTabRegistry(scriptDir: string): void {
  const distScript = path.join(
    getDistScriptsDir(scriptDir),
    "generate-tab-registry.mjs",
  );
  const srcScript = path.join(getScriptsRoot(scriptDir), "generate-tab-registry.ts");

  try {
    // Prefer compiled version (same as start-dev.sh)
    const script = existsSync(distScript) ? distScript : null;
    if (script) {
      execFileSync("node", [script], {
        cwd: getDashboardRoot(scriptDir),
        stdio: "inherit",
      });
    } else {
      // Fallback to tsx for source mode
      execFileSync("npx", ["tsx", srcScript], {
        cwd: getDashboardRoot(scriptDir),
        stdio: "inherit",
      });
    }
  } catch (err) {
    console.error("Tab registry regeneration failed:", err);
    process.exit(1);
  }
}
