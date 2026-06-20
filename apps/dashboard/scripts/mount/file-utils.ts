/**
 * Mount Plugins — File Utilities
 *
 * Low-level filesystem helpers used across the mount pipeline:
 * symlink detection, recursive file listing, directory removal,
 * and empty directory cleanup.
 *
 * Extracted from copier.ts to isolate reusable FS primitives.
 */

import fs from "fs/promises";
import path from "path";

/** Marker file to identify mounted plugin directories. */
export const MOUNT_MARKER = ".plugin-mount";

/**
 * Check if a path is a symlink.
 */
export async function isSymlink(targetPath: string): Promise<boolean> {
  try {
    const stat = await fs.lstat(targetPath);
    return stat.isSymbolicLink();
  } catch {
    return false;
  }
}

function toPosixPath(filePath: string): string {
  return filePath.replace(/\\/g, "/");
}

/**
 * Get all file paths in a directory recursively.
 * Optionally skips files with extensions in the provided set.
 */
export async function getAllFiles(
  dir: string,
  base: string = "",
  skipExts?: Set<string>,
): Promise<Set<string>> {
  // TODO_BUG(auto-memory-leak): unbounded-cache — Module-level Map/Set without MAX size guard — grows without bound
  const files = new Set<string>();
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const relativePath = base ? `${base}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        const subFiles = await getAllFiles(
          path.join(dir, entry.name),
          relativePath,
          skipExts,
        );
        subFiles.forEach((f) => files.add(f));
      } else {
        if (skipExts) {
          const ext = path.extname(entry.name).toLowerCase();
          if (skipExts.has(ext)) continue;
        }
        files.add(relativePath);
      }
    }
  } catch {
    // Directory doesn't exist
  }
  return files;
}

/**
 * Recursively remove a directory and its contents.
 */
export async function removeDir(dirPath: string): Promise<void> {
  try {
    await fs.rm(dirPath, { recursive: true, force: true });
  } catch {
    // Directory might not exist
  }
}

/**
 * Recursively remove empty directories.
 * The rootDir parameter prevents the top-level mount target from being deleted.
 */
export async function cleanEmptyDirs(
  dir: string,
  rootDir?: string,
): Promise<boolean> {
  const root = rootDir ?? dir;
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    let hasContent = false;

    for (const entry of entries) {
      if (entry.isDirectory()) {
        const subDir = path.join(dir, entry.name);
        const subHasContent = await cleanEmptyDirs(subDir, root);
        if (subHasContent) {
          hasContent = true;
        }
      } else {
        hasContent = true;
      }
    }

    // Don't delete the root target directory
    if (!hasContent && dir !== root) {
      await fs.rmdir(dir);
      return false;
    }
    return hasContent;
  } catch {
    return true; // Assume content exists if we can't read
  }
}
