import path from "path";

/** Relative path from dashboard root to feature code (components, hooks, pages) */
export const FEATURES_DIR = "features";

/**
 * Resolve the dashboard root directory, accounting for compiled dist/ location.
 *
 * When scripts run from source (tsx), __dirname is `scripts/` — go up 1 level.
 * When bundled to dist/, __dirname is `scripts/dist/` — go up 2 levels.
 */
export function getDashboardRoot(dirname: string): string {
  return dirname.endsWith("dist")
    ? path.resolve(dirname, "..", "..")
    : path.resolve(dirname, "..");
}
