/**
 * Mount Plugins — Copy with Headers
 *
 * Recursively copies plugin source directories into mount targets,
 * injecting warning headers into code files so AI agents and
 * developers know not to edit the mounted copy.
 *
 * Extracted from copier.ts to isolate the header-injection logic.
 */

import fs from "fs/promises";
import path from "path";

// ============================================================================
// Constants
// ============================================================================

/**
 * Header comment added to mounted plugin files to warn agents not to edit them.
 * This prevents AI agents from accidentally editing the temporary copy instead of the source.
 */
const MOUNTED_FILE_HEADER = `/**
 * AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
 *
 * This file is a temporary copy mounted from a plugin source.
 * Any changes made here will be OVERWRITTEN on next build.
 *
 * To make changes, edit the SOURCE file at:
 * SOURCE_PATH_PLACEHOLDER
 *
 * Then run: npm run build (or npm run mount-plugins)
 */

`;

/** Extensions that should receive the warning header comment. */
const HEADER_EXTENSIONS = new Set([
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".mjs",
  ".cjs",
]);

/** File extensions to skip during plugin mount (non-web metadata files). */
export const SKIP_EXTENSIONS = new Set([".yaml", ".yml"]);

// ============================================================================
// Copy with Headers
// ============================================================================

/**
 * Recursively copy a directory, adding warning headers to code files.
 *
 * Code files (.ts, .tsx, .js, .jsx, .mjs, .cjs) receive a header
 * comment warning AI agents and developers not to edit the mounted copy.
 * The header preserves 'use client'/'use server' directives at the top.
 */
export async function copyDir(
  source: string,
  target: string,
  repoRoot: string,
): Promise<void> {
  await fs.mkdir(target, { recursive: true });
  const entries = await fs.readdir(source, { withFileTypes: true });

  for (const entry of entries) {
    const sourcePath = path.join(source, entry.name);
    const targetPath = path.join(target, entry.name);

    if (entry.isDirectory()) {
      await copyDir(sourcePath, targetPath, repoRoot);
    } else {
      const ext = path.extname(entry.name).toLowerCase();

      // Skip non-web metadata files (symbols.yaml, etc.) — they add file watcher
      // overhead without being used by the dashboard build.
      if (SKIP_EXTENSIONS.has(ext)) {
        continue;
      }

      if (HEADER_EXTENSIONS.has(ext)) {
        // Add warning header to code files
        const content = await fs.readFile(sourcePath, "utf8");

        // Skip if file already has the header (shouldn't happen, but be safe)
        if (content.includes("AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY")) {
          await fs.copyFile(sourcePath, targetPath);
        } else {
          // Check if file starts with 'use client' or 'use server' directive
          const useDirectiveMatch = content.match(
            /^(['"]use (client|server)['"];?\s*\n)/,
          );

          // Compute relative path from project root.
          // When running in a worktree, AUGUR_ROOT env var can cause
          // getUserPluginsDir() to resolve plugins from the main repo
          // while repoRoot points to the worktree. This produces paths
          // like "../Augur/plugins/..." instead of "plugins/...".
          // Normalize by extracting the plugins-relative portion when
          // the path escapes the project root.
          let relativeSourcePath = path.relative(repoRoot, sourcePath);
          if (relativeSourcePath.startsWith("..")) {
            const sep = path.sep;
            const marker = `${sep}plugins${sep}`;
            const idx = sourcePath.lastIndexOf(marker);
            if (idx >= 0) {
              relativeSourcePath = sourcePath.slice(idx + 1);
            }
          }

          let newContent: string;
          if (useDirectiveMatch) {
            // Preserve the 'use client'/'use server' directive at the top
            const directive = useDirectiveMatch[1];
            const restOfContent = content.slice(directive.length);
            const header = MOUNTED_FILE_HEADER.replace(
              "SOURCE_PATH_PLACEHOLDER",
              relativeSourcePath,
            );
            newContent = directive + header + restOfContent;
          } else {
            const header = MOUNTED_FILE_HEADER.replace(
              "SOURCE_PATH_PLACEHOLDER",
              relativeSourcePath,
            );
            newContent = header + content;
          }

          await fs.writeFile(targetPath, newContent, "utf8");
        }
        // Note: Removed read-only chmod (0o444) - it caused Turbopack panics
        // The warning header in files is sufficient to prevent accidental editing
      } else {
        // Copy non-code files as-is
        await fs.copyFile(sourcePath, targetPath);
      }
    }
  }
}
