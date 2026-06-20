/**
 * Mount Plugins — Cache Management
 *
 * Detects whether Next.js dev or build processes are running and
 * safely clears the .next cache when no active process would be
 * disrupted. Prevents stale Tailwind file-watcher references.
 *
 * Extracted from copier.ts to isolate cache lifecycle logic.
 */

import fs from "fs/promises";
import path from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import type { MountConfig } from "./types";

const execFileAsync = promisify(execFile);

/**
 * Check if Next.js dev server is currently running.
 * We detect this by checking for the dev lock file.
 */
async function isNextDevRunning(dashboardRoot: string): Promise<boolean> {
  const lockFile = path.join(dashboardRoot, ".next", "dev", "lock");
  try {
    await fs.access(lockFile);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if a production build is actively mutating the dashboard .next output.
 *
 * We intentionally use process detection instead of lock files here because
 * mount-plugins can be invoked outside the build-lock wrapper.
 */
async function isNextBuildRunning(): Promise<boolean> {
  try {
    const { stdout } = await execFileAsync("pgrep", ["-fl", "next"], {
      timeout: 5_000,
    });

    return stdout
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .some((line) => {
        const firstSpace = line.indexOf(" ");
        const command =
          firstSpace === -1 ? "" : line.slice(firstSpace + 1).trim();
        return command.includes("next build") && !command.includes(".next/");
      });
  } catch {
    return false;
  }
}

/**
 * Clear the Next.js cache to prevent stale file references.
 *
 * This fixes a race condition where Tailwind CSS caches file paths from
 * a previous build. When mount-plugins deletes and recreates files,
 * Tailwind may try to stat() files that no longer exist, causing ENOENT errors.
 *
 * By clearing .next before mounting, we ensure Tailwind rebuilds its
 * content list from scratch after plugins are freshly mounted.
 *
 * IMPORTANT: We only clear the cache if Next.js is NOT running. If the dev
 * server is active, clearing .next would crash it. The atomic mount strategy
 * handles the race condition during hot reload.
 */
export async function clearNextCache(config: MountConfig): Promise<void> {
  // Don't clear cache if dev server is running - it would crash Next.js
  if (await isNextDevRunning(config.dashboardRoot)) {
    if (config.isVerbose) {
      console.log("   Skipping cache clear (dev server running)");
    }
    return;
  }

  // Never clear .next while a production build is writing manifests/assets.
  // NOTE: isNextBuildRunning relies on `pgrep`, which is absent on Windows, so
  // this guard is best-effort there — the completed-build guard below is the
  // reliable protection on every platform.
  if (await isNextBuildRunning()) {
    if (config.isVerbose) {
      console.log("   Skipping cache clear (production build running)");
    }
    return;
  }

  // Never delete the production build we are about to SERVE (ADR-787).
  // `start-dev --prod` sets AUGUR_PROD_SERVE=1 before re-running this prebuild,
  // so mount-plugins must preserve the freshly-built `.next` instead of wiping
  // the prod image on :3000. We key on this explicit signal rather than the mere
  // presence of `.next/BUILD_ID`: a leftover BUILD_ID from an earlier prod build
  // must NOT block clearing when the same checkout later runs `next dev` (that
  // would mount dev on a stale prod build and reintroduce stale-chunk errors).
  // During an actual `next build` the build step does its own wipe, so clearing
  // here (no AUGUR_PROD_SERVE) is correct.
  const nextCacheDir = path.join(config.dashboardRoot, ".next");
  if (process.env.AUGUR_PROD_SERVE === "1") {
    if (config.isVerbose) {
      console.log("   Skipping cache clear (serving production build)");
    }
    return;
  }
  try {
    const stat = await fs.stat(nextCacheDir);
    if (stat.isDirectory()) {
      await fs.rm(nextCacheDir, { recursive: true, force: true });
      console.log("   Cleared .next cache (prevents stale file references)");
    }
  } catch {
    // .next doesn't exist - that's fine
  }
}
