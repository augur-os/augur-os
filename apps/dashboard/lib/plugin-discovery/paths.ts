/**
 * Plugin Discovery — Path Resolution
 *
 * Centralized path resolution for plugin discovery across build scripts,
 * lib modules, and API routes. Eliminates ~6 duplicated implementations.
 */

import fsSync from "fs";
import path from "path";
import { execFileSync } from "child_process";

/**
 * Discover the repository root by walking up from startDir.
 *
 * Checks for config/system/ first (unique to project root — per MEMORY.md,
 * src/config/ has no system/ subdir so it won't false-match at src/ level),
 * then .git as fallback.
 *
 * @param startDir - Starting directory (defaults to process.cwd())
 */
export function discoverRepoRoot(startDir?: string): string {
  let current = path.resolve(startDir ?? process.cwd());
  while (current !== path.parse(current).root) {
    if (
      fsSync.existsSync(path.join(current, "config", "system")) ||
      fsSync.existsSync(path.join(current, ".git"))
    ) {
      return current;
    }
    current = path.dirname(current);
  }
  return path.resolve(startDir ?? process.cwd());
}

/**
 * Get the legacy core plugins directory.
 *
 * Resolution order:
 * 1. AUGUR_CORE env var + /plugins
 * 2. discoverRepoRoot(startDir) + /plugins
 */
export function getCorePluginsDir(startDir?: string): string {
  const repoRoot = discoverRepoRoot(startDir);
  const repoPlugins = path.join(repoRoot, "plugins");
  const coreRepo = process.env.AUGUR_CORE;
  if (coreRepo) {
    const envRoot = path.resolve(coreRepo);
    if (envRoot === path.resolve(repoRoot) || !fsSync.existsSync(repoPlugins)) {
      return path.join(envRoot, "plugins");
    }
    return repoPlugins;
  }
  return repoPlugins;
}

/**
 * Get the legacy user plugins directory.
 *
 * Resolution order:
 * 1. AUGUR_USER_PLUGINS env var (direct path)
 * 2. AUGUR_USER or AUGUR_ROOT env var + /plugins
 * 3. Monorepo: check discoverRepoRoot(startDir)/plugins
 * 4. null if nothing found
 */
export function getUserPluginsDir(startDir?: string): string | null {
  if (process.env.AUGUR_USER_PLUGINS) {
    return process.env.AUGUR_USER_PLUGINS;
  }

  // Explicit user override takes top priority.
  if (process.env.AUGUR_USER) {
    const userPlugins = path.join(
      path.resolve(process.env.AUGUR_USER),
      "plugins",
    );
    return fsSync.existsSync(userPlugins) ? userPlugins : null;
  }

  // Prefer the current repo/worktree legacy plugins directory over AUGUR_ROOT.
  // This prevents worktree-local compatibility data from being shadowed by the
  // main repo when AUGUR_ROOT still points at the primary checkout.
  const repoRoot = discoverRepoRoot(startDir);
  const monorepoPlugins = path.join(repoRoot, "plugins");
  if (fsSync.existsSync(monorepoPlugins)) {
    return monorepoPlugins;
  }

  // Fallback for environments that only expose AUGUR_ROOT.
  if (process.env.AUGUR_ROOT) {
    const rootPlugins = path.join(
      path.resolve(process.env.AUGUR_ROOT),
      "plugins",
    );
    return fsSync.existsSync(rootPlugins) ? rootPlugins : null;
  }

  return null;
}

/**
 * Get all plugin directories to scan, deduped.
 * Returns core first, then user (user overrides core).
 */
export function getAllPluginDirs(startDir?: string): string[] {
  const core = getCorePluginsDir(startDir);
  const user = getUserPluginsDir(startDir);
  if (user && path.resolve(user) !== path.resolve(core)) {
    return [core, user];
  }
  return [core];
}

/**
 * Return the canonical repo-local shared/team skill root.
 */
export function getProjectBrainSkillsRoot(repoRoot: string): string {
  return path.join(repoRoot, "project-brain", "capabilities", "skills");
}

/**
 * @deprecated ADR-770 moved shared/team skills to project-brain/capabilities/skills.
 */
function getSharedVaultSkillsRoot(repoRoot: string): string {
  return getProjectBrainSkillsRoot(repoRoot);
}

/**
 * Skill directories: canonical project-brain/capabilities/skills at project root.
 */
const CLIENT_SKILL_DIRS: Record<string, string> = {
  augur: "project-brain/capabilities/skills",
};

function parsePathList(raw: string | undefined): string[] | null {
  if (!raw || !raw.trim()) return null;
  const paths = raw
    .split(path.delimiter)
    .flatMap((entry) => {
      const trimmed = entry.trim();
      return trimmed ? [trimmed] : [];
    })
    .map((entry) => path.resolve(entry));
  return paths.length > 0 ? paths : null;
}

function readManagedSkillDirsFromPython(repoRoot: string): string[] | null {
  const python = process.env.AUGUR_PYTHON || "python3";
  const script = [
    "import json, os, sys",
    "from pathlib import Path",
    "root = Path(sys.argv[1]).resolve()",
    "sys.path.insert(0, str(root))",
    "from src.config.paths import get_managed_skill_source_dirs",
    "print(json.dumps([str(p) for p in get_managed_skill_source_dirs(root)]))",
  ].join("; ");

  try {
    // TODO_CLEANUP: rule-11 — this spawns Python to resolve managed-skill source dirs.
    // Migratable to the get-path-config MCP tool (or a dedicated path tool). Pre-existing,
    // outside ADR-817's pragmatic scope; logged as a follow-up, not yet migrated. See ADR-817.
    const output = execFileSync(python, ["-c", script, repoRoot], {
      cwd: repoRoot,
      encoding: "utf8",
      env: {
        ...process.env,
        AUGUR_ROOT: repoRoot,
      },
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 5000,
    });
    const parsed = JSON.parse(output) as unknown;
    if (!Array.isArray(parsed)) return null;
    return parsed
      .filter((entry): entry is string => typeof entry === "string")
      .map((entry) => path.resolve(entry));
  } catch {
    return null;
  }
}

function shouldIncludeLocalSkillDirs(): boolean {
  const raw =
    process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS ??
    process.env.AUGUR_INCLUDE_LOCAL_SKILLS ??
    "";
  return ["1", "true", "yes", "on"].includes(raw.trim().toLowerCase());
}

function canonicalExistingPath(entry: string): string {
  try {
    return fsSync.realpathSync(entry);
  } catch {
    return path.resolve(entry);
  }
}

function isProjectBrainSkillRoot(entry: string): boolean {
  const parts = path.resolve(entry).split(path.sep);
  return (
    parts.at(-1) === "skills" &&
    parts.at(-2) === "capabilities" &&
    parts.at(-3) === "project-brain"
  );
}

function clientIdForManagedSkillDir(
  skillDir: string,
  projectSkillsDir: string,
  usedIds: Set<string>,
): string {
  const canonicalSkillDir = canonicalExistingPath(skillDir);
  const baseId = canonicalSkillDir === canonicalExistingPath(projectSkillsDir)
    ? "augur"
    : "augur-vault";
  let candidate = baseId;
  let suffix = 2;
  while (usedIds.has(candidate)) {
    candidate = `${baseId}-${suffix}`;
    suffix += 1;
  }
  usedIds.add(candidate);
  return candidate;
}

/**
 * Return managed canonical skill roots in scan order.
 *
 * Python path helpers return priority order (project first, then vault). The
 * dashboard scanners use last-writer-wins for duplicate skill names, so this
 * returns the roots reversed: lower priority first, project priority last.
 *
 * Release generation defaults to project-brain skills only. Vault-local skills
 * are local user content; include them only via the explicit env opt-in or an
 * explicit AUGUR_MANAGED_SKILL_DIRS override.
 */
export function getManagedSkillDirs(startDir?: string): Record<string, string> {
  const repoRoot = discoverRepoRoot(startDir);
  const projectSkillsDir = getProjectBrainSkillsRoot(repoRoot);
  const overrideDirs = parsePathList(process.env.AUGUR_MANAGED_SKILL_DIRS);
  const repoOnlyDirs = fsSync.existsSync(projectSkillsDir) ? [projectSkillsDir] : [];
  const configuredPriorityDirs = shouldIncludeLocalSkillDirs()
    ? readManagedSkillDirsFromPython(repoRoot) || repoOnlyDirs
    : repoOnlyDirs;
  const priorityDirs = overrideDirs || configuredPriorityDirs;
  const canonicalProjectSkillsDir = fsSync.existsSync(projectSkillsDir)
    ? canonicalExistingPath(projectSkillsDir)
    : path.resolve(projectSkillsDir);

  const seenScanDirs = new Set<string>();
  const scanDirs = [...priorityDirs].flatMap((entry) => {
    const resolved = path.resolve(entry);
    if (!fsSync.existsSync(resolved)) return [];
    const canonical = canonicalExistingPath(resolved);
    if (
      isProjectBrainSkillRoot(canonical) &&
      canonical !== canonicalProjectSkillsDir
    ) {
      return [];
    }
    if (seenScanDirs.has(canonical)) return [];
    seenScanDirs.add(canonical);
    return [resolved];
  }).reverse();

  const dirs: Record<string, string> = {};
  const usedIds = new Set<string>();
  for (const dir of scanDirs) {
    const clientId = clientIdForManagedSkillDir(
      dir,
      projectSkillsDir,
      usedIds,
    );
    dirs[clientId] = dir;
  }
  return dirs;
}

/**
 * Get client skill directories that exist on disk.
 * Returns a map of client-id to absolute path.
 */
export function getClientSkillDirs(startDir?: string): Record<string, string> {
  return getManagedSkillDirs(startDir);
}
