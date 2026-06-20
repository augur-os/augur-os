/**
 * Mount Plugins — Runtime Path Resolution
 *
 * Root/dir helpers extracted from mount-plugins.ts. These depend on the
 * ENTRY script's __dirname (the directory of the running mount-plugins module),
 * which differs from this module's own __dirname. The entry threads its
 * __dirname in as `scriptDir`.
 */

import path from "path";
import { getDashboardRoot as getDashboardRootFromDir } from "../lib/path-utils";

/**
 * Resolve the dashboard root directory.
 *
 * When bundled:  scriptDir = scripts/dist/ -> up 2 levels = dashboard root
 * When run via tsx: scriptDir = scripts/  -> up 1 level  = dashboard root
 *
 * We detect which case we're in by checking if scriptDir ends with
 * scripts/dist (bundled) or just scripts (source).
 */
export function getDashboardRoot(scriptDir: string): string {
  return getDashboardRootFromDir(scriptDir);
}

export function getScriptsRoot(scriptDir: string): string {
  const basename = path.basename(scriptDir);
  if (
    basename === "dist" &&
    path.basename(path.dirname(scriptDir)) === "scripts"
  ) {
    return path.dirname(scriptDir);
  }
  return scriptDir;
}

export function getDistScriptsDir(scriptDir: string): string {
  const basename = path.basename(scriptDir);
  if (
    basename === "dist" &&
    path.basename(path.dirname(scriptDir)) === "scripts"
  ) {
    return scriptDir;
  }
  return path.join(scriptDir, "dist");
}

export function getAppDir(scriptDir: string): string {
  return path.join(getDashboardRoot(scriptDir), "app");
}
