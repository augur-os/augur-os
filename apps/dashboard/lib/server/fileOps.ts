/**
 * File Operation Utilities
 *
 * Provides consistent file operation helpers used across routes.
 * Extracted from duplicated code in skills/manager, skills/import routes.
 */
import fs from "fs/promises";
import path from "path";
import os from "os";

/**
 * Check if a file or directory exists.
 *
 * @param filePath - Path to check
 * @returns true if exists, false otherwise
 *
 * @example
 * ```typescript
 * if (await fileExists('/path/to/file')) {
 *   const content = await fs.readFile('/path/to/file', 'utf8');
 * }
 * ```
 */
export async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.stat(filePath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Ensure a directory exists, creating it if necessary.
 *
 * @param dirPath - Directory path to ensure
 *
 * @example
 * ```typescript
 * await ensureDir('/path/to/output');
 * await fs.writeFile('/path/to/output/file.txt', content);
 * ```
 */
async function ensureDir(dirPath: string): Promise<void> {
  await fs.mkdir(dirPath, { recursive: true });
}

/**
 * Remove a directory and all its contents.
 * Silent on error (directory doesn't exist, etc.)
 *
 * @param dirPath - Directory to remove
 *
 * @example
 * ```typescript
 * await cleanupDir('/tmp/my-temp-dir');
 * ```
 */
async function cleanupDir(dirPath: string): Promise<void> {
  try {
    await fs.rm(dirPath, { recursive: true, force: true });
  } catch {
    // Ignore errors - directory might not exist
  }
}

/**
 * Get a temporary directory path for a specific purpose.
 *
 * @param namespace - Unique namespace for the temp directory
 * @returns Path to temp directory (not created yet)
 *
 * @example
 * ```typescript
 * const tempDir = getTempDir('skill-import');
 * await ensureDir(tempDir);
 * ```
 */
function getTempDir(namespace: string): string {
  return path.join(os.tmpdir(), `augur-${namespace}`);
}

/**
 * Read a file's contents safely, returning null if not found.
 *
 * @param filePath - Path to file
 * @returns File contents or null
 *
 * @example
 * ```typescript
 * const content = await safeReadFile('/path/to/config.json');
 * if (content) {
 *   const config = JSON.parse(content);
 * }
 * ```
 */
export async function safeReadFile(filePath: string): Promise<string | null> {
  try {
    return await fs.readFile(filePath, "utf8");
  } catch {
    return null;
  }
}

/**
 * List directory entries with type information.
 * Returns empty array if directory doesn't exist.
 *
 * @param dirPath - Directory to list
 * @returns Array of directory entries with isDirectory/isFile methods
 *
 * @example
 * ```typescript
 * const entries = await safeReaddir('/path/to/dir');
 * const files = entries.filter(e => e.isFile());
 * ```
 */
export async function safeReaddir(
  dirPath: string,
): Promise<
  Array<{ name: string; isDirectory: () => boolean; isFile: () => boolean }>
> {
  try {
    return await fs.readdir(dirPath, { withFileTypes: true });
  } catch {
    return [];
  }
}
