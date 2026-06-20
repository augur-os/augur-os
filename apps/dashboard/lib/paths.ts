import fsSync from "fs";
import path from "path";
import os from "os";
import {
  discoverBundles,
} from "./plugin-discovery/scanner";
import {
  discoverRepoRoot,
  getAllPluginDirs as discoverPluginDirs,
  getClientSkillDirs,
} from "./plugin-discovery/paths";

/**
 * Server-side self-heal event emitter (ADR-084).
 * Writes directly to JSONL since this file runs server-side only.
 * Must never throw — called from error/startup paths.
 */
function emitServerHealEvent(params: {
  source: string;
  category: string;
  severity: string;
  message: string;
  context?: Record<string, unknown>;
}): void {
  try {
    const stateDir = resolveStateDir();
    fsSync.mkdirSync(stateDir, { recursive: true });
    const event = {
      timestamp: new Date().toISOString(),
      source: params.source,
      category: params.category,
      severity: params.severity,
      message: params.message,
      context: params.context ?? {},
      host: os.hostname(),
      pid: process.pid,
    };
    fsSync.appendFileSync(
      path.join(stateDir, "self_heal_events.jsonl"),
      JSON.stringify(event) + "\n",
    );
  } catch {
    // intentionally empty — must never throw
  }
}

export const USER_HOME = os.homedir();
const DASHBOARD_MARKER = `${path.sep}src${path.sep}dashboard`;

function expandTilde(p: string) {
  if (!p.startsWith("~")) return p;
  if (p === "~") return USER_HOME;
  if (p.startsWith("~/") || p.startsWith("~\\")) return path.join(USER_HOME, p.slice(2));
  return p;
}

function envPath(...names: string[]): string | null {
  for (const name of names) {
    const value = process.env[name];
    if (value && value.trim()) {
      return path.resolve(expandTilde(value.trim()));
    }
  }
  return null;
}

function isMacOS(): boolean {
  return process.platform === "darwin";
}

function isWindows(): boolean {
  return process.platform === "win32";
}

function windowsRoamingDir(): string {
  return path.resolve(
    process.env.APPDATA || path.join(USER_HOME, "AppData", "Roaming"),
  );
}

function windowsLocalDir(): string {
  return path.resolve(
    process.env.LOCALAPPDATA || path.join(USER_HOME, "AppData", "Local"),
  );
}

function xdgDataHome(): string {
  return path.resolve(
    expandTilde(process.env.XDG_DATA_HOME || "~/.local/share"),
  );
}

function xdgStateHome(): string {
  return path.resolve(
    expandTilde(process.env.XDG_STATE_HOME || "~/.local/state"),
  );
}

function xdgCacheHome(): string {
  return path.resolve(expandTilde(process.env.XDG_CACHE_HOME || "~/.cache"));
}

/**
 * Discover the repository root by looking for config/, src/, or .git/
 */
function stripDashboardSuffix(candidate: string): string {
  if (!candidate) return candidate;
  const normalized = path.normalize(candidate);
  const idx = normalized.lastIndexOf(DASHBOARD_MARKER);
  if (idx > 0) {
    return normalized.slice(0, idx);
  }
  return normalized;
}

function isRepoRoot(candidate: string): boolean {
  return (
    fsSync.existsSync(path.join(candidate, "config", "system")) ||
    fsSync.existsSync(path.join(candidate, ".git"))
  );
}

function resolveRepoRoot(): string {
  const startDirs = [
    process.env.PWD,
    process.env.INIT_CWD,
    process.cwd(),
  ].filter((value): value is string => Boolean(value?.trim()));

  for (const startDir of startDirs) {
    const discovered = path.normalize(
      discoverRepoRoot(stripDashboardSuffix(expandTilde(startDir.trim()))),
    );
    if (isRepoRoot(discovered)) {
      return discovered;
    }
  }

  const cwdRoot = path.normalize(
    discoverRepoRoot(stripDashboardSuffix(process.cwd())),
  );
  if (isRepoRoot(cwdRoot)) {
    const envRoot =
      process.env.AUGUR_ROOT ||
      process.env.AUGUR_CORE ||
      process.env.AUGUR_REPO;
    if (envRoot && path.normalize(expandTilde(envRoot.trim())) !== cwdRoot) {
      emitServerHealEvent({
        source: "paths.ts/resolveRepoRoot",
        category: "env_drift",
        severity: "medium",
        message: `Ignoring inherited AUGUR_ROOT drift in favor of cwd root ${cwdRoot}`,
        context: { inheritedRoot: envRoot, cwdRoot },
      });
    }
    return cwdRoot;
  }

  const envRoot =
    process.env.AUGUR_ROOT || process.env.AUGUR_CORE || process.env.AUGUR_REPO;
  if (envRoot && envRoot.trim()) {
    const normalized = path.normalize(expandTilde(envRoot.trim()));
    if (isRepoRoot(normalized)) {
      return normalized;
    }
  }

  const pwd = process.env.PWD || process.env.INIT_CWD;
  if (pwd && pwd.trim()) {
    return stripDashboardSuffix(expandTilde(pwd.trim()));
  }

  return stripDashboardSuffix(process.cwd());
}

function resolveRuntimeBase() {
  const runtimeDir = resolveStateDir();
  try {
    fsSync.mkdirSync(runtimeDir, { recursive: true });
    return runtimeDir;
  } catch (error) {
    // In tests, return the expected runtime path without hard-failing.
    if (process.env.NODE_ENV === "test" || typeof jest !== "undefined") {
      return runtimeDir;
    }

    const repoRoot = resolveRepoRoot();
    emitServerHealEvent({
      source: "paths.ts/resolveRuntimeBase",
      category: "path_missing",
      severity: "high",
      message: `Runtime directory not writable: ${runtimeDir}`,
      context: { repoRoot, runtimeDir, error: String(error) },
    });
    throw new Error(
      `[paths] Runtime state directory not available at ${runtimeDir}. ` +
        `Set AUGUR_STATE/AUGUR_RUNTIME or ensure the state directory is writable.`,
    );
  }
}

function resolveAppSupportDir(): string {
  return (
    envPath("AUGUR_APP_SUPPORT") ||
    (isMacOS()
      ? path.join(USER_HOME, "Library", "Application Support", "Augur")
      : isWindows()
        ? path.join(windowsRoamingDir(), "Augur")
      : path.join(xdgDataHome(), "augur"))
  );
}

function resolveStateEnvOverride(): string | null {
  const repoRoot = resolveRepoRoot();
  const legacyRuntimeDir = path.join(repoRoot, "runtime");

  for (const name of ["AUGUR_STATE", "AUGUR_RUNTIME", "AUGUR_RUNTIME_DIR"]) {
    const candidate = envPath(name);
    if (!candidate) {
      continue;
    }

    if (
      candidate === legacyRuntimeDir ||
      candidate.startsWith(`${legacyRuntimeDir}${path.sep}`)
    ) {
      continue;
    }

    return candidate;
  }

  return null;
}

function resolveStateDir(): string {
  return (
    resolveStateEnvOverride() ||
    (isMacOS()
      ? path.join(resolveAppSupportDir(), "state")
      : isWindows()
        ? path.join(windowsLocalDir(), "Augur", "state")
      : path.join(xdgStateHome(), "augur"))
  );
}

function resolveLogsDir(): string {
  return (
    envPath("AUGUR_LOGS") ||
    (isMacOS()
      ? path.join(USER_HOME, "Library", "Logs", "Augur")
      : isWindows()
        ? path.join(windowsLocalDir(), "Augur", "logs")
      : path.join(xdgStateHome(), "augur", "logs"))
  );
}

function resolveCacheDir(): string {
  return (
    envPath("AUGUR_CACHE_DIR", "AUGUR_CACHE_PATH") ||
    (isMacOS()
      ? path.join(USER_HOME, "Library", "Caches", "Augur")
      : isWindows()
        ? path.join(windowsLocalDir(), "Augur", "cache")
      : path.join(xdgCacheHome(), "augur"))
  );
}

type DiscoverablePathType = "vault" | "documents";

const DISCOVERY_MARKERS: Record<DiscoverablePathType, string> = {
  vault: ".augur-vault",
  documents: ".augur-docs",
};

const DISCOVERY_SKIP_DIRS = new Set([
  "Library",
  "Applications",
  "Music",
  "Movies",
  "Pictures",
  "Photos",
  "node_modules",
  ".Trash",
  "go",
  ".cargo",
  ".rustup",
]);

function pushUniquePath(paths: string[], candidate: string): void {
  const normalized = path.resolve(candidate);
  if (!paths.includes(normalized)) {
    paths.push(normalized);
  }
}

function defaultDiscoveryRoots(configured: string): string[] {
  const roots: string[] = [];
  const parent = path.dirname(configured);
  if (fsSync.existsSync(parent)) {
    pushUniquePath(roots, parent);
  }
  pushUniquePath(roots, USER_HOME);
  const documents = path.join(USER_HOME, "Documents");
  if (fsSync.existsSync(documents)) {
    pushUniquePath(roots, documents);
  }
  const desktop = path.join(USER_HOME, "Desktop");
  if (fsSync.existsSync(desktop)) {
    pushUniquePath(roots, desktop);
  }
  return roots;
}

function collectDiscoveryCandidates(roots: string[]): string[] {
  const candidates: string[] = [];
  let checked = 0;
  const start = Date.now();
  const maxCandidates = 100;
  const timeoutMs = 5000;

  for (const root of roots) {
    if (!fsSync.existsSync(root)) continue;
    let children: fsSync.Dirent[];
    try {
      children = fsSync.readdirSync(root, { withFileTypes: true });
    } catch {
      continue;
    }

    for (const child of children.sort((a, b) => a.name.localeCompare(b.name))) {
      if (!child.isDirectory() || child.name.startsWith(".")) continue;
      checked += 1;
      if (checked > maxCandidates || Date.now() - start > timeoutMs) {
        return candidates;
      }
      const childPath = path.join(root, child.name);
      candidates.push(childPath);
      if (DISCOVERY_SKIP_DIRS.has(child.name)) continue;

      let grandchildren: fsSync.Dirent[];
      try {
        grandchildren = fsSync.readdirSync(childPath, { withFileTypes: true });
      } catch {
        continue;
      }
      for (const grandchild of grandchildren.sort((a, b) => a.name.localeCompare(b.name))) {
        if (!grandchild.isDirectory() || grandchild.name.startsWith(".")) continue;
        checked += 1;
        if (checked > maxCandidates || Date.now() - start > timeoutMs) {
          return candidates;
        }
        candidates.push(path.join(childPath, grandchild.name));
      }
    }
  }

  return candidates;
}

function discoverMarkedPath(
  pathType: DiscoverablePathType,
  configured: string,
): string | null {
  const marker = DISCOVERY_MARKERS[pathType];
  for (const candidate of collectDiscoveryCandidates(defaultDiscoveryRoots(configured))) {
    if (fsSync.existsSync(path.join(candidate, marker))) {
      return candidate;
    }
  }
  return null;
}

function resolvePathWithDiscovery(
  pathType: DiscoverablePathType,
  configured: string,
): string {
  if (fsSync.existsSync(configured)) {
    return configured;
  }

  const discovered = discoverMarkedPath(pathType, configured);
  if (discovered) {
    emitServerHealEvent({
      source: `paths.ts/resolve${pathType[0].toUpperCase()}${pathType.slice(1)}Dir`,
      category: "path_discovery",
      severity: "medium",
      message: `${pathType} not at configured ${configured}; using discovered ${discovered}`,
      context: { pathType, configured, discovered },
    });
    return discovered;
  }

  return configured;
}

/**
 * Read paths from project.yaml (same source as Python's paths.py).
 * Returns the resolved path for the given key, or null if not found.
 */
function readProjectYamlPath(key: string): string | null {
  try {
    const projectYaml = path.join(resolveRepoRoot(), "project.yaml");
    if (!fsSync.existsSync(projectYaml)) return null;
    const content = fsSync.readFileSync(projectYaml, "utf-8");
    // Simple YAML parse for "paths:" section — avoid importing yaml here
    const pathsMatch = content.match(
      new RegExp(`^\\s+${key}:\\s*(.+)$`, "m"),
    );
    if (!pathsMatch?.[1]) return null;
    return path.resolve(expandTilde(pathsMatch[1].trim()));
  } catch {
    return null;
  }
}

function resolveVaultDir(): string {
  const configured =
    envPath("AUGUR_VAULT") ||
    readProjectYamlPath("vault") ||
    path.join(USER_HOME, "Vault", "Augur");
  return resolvePathWithDiscovery("vault", configured);
}

function resolveDocumentsDir(): string {
  const configured =
    envPath("AUGUR_DOCUMENTS") ||
    readProjectYamlPath("documents") ||
    path.join(USER_HOME, "Documents", "Augur");
  return resolvePathWithDiscovery("documents", configured);
}

function resolveRagDir(): string {
  return envPath("AUGUR_RAG") || path.join(resolveAppSupportDir(), "rag");
}

function resolvePythonPath() {
  if (process.env.AUGUR_PYTHON) return process.env.AUGUR_PYTHON;

  // During static analysis/build, return system python to avoid Turbopack symlink issues
  // The .venv path contains symlinks that point outside the project root
  const repoRoot = resolveRepoRoot();

  // Build the venv path dynamically to avoid Turbopack static analysis
  // (Turbopack follows string literal paths during bundling)
  const venvDir = ["", "venv"].join("."); // '.venv'
  const venvPython =
    process.platform === "win32"
      ? path.join(repoRoot, venvDir, "Scripts", "python.exe")
      : path.join(repoRoot, venvDir, "bin", "python3");

  // Use lstatSync to check if path exists without following symlinks
  try {
    fsSync.lstatSync(venvPython);
    return venvPython;
  } catch {
    // ADR-084: emit event instead of silent fallback to system python
    emitServerHealEvent({
      source: "paths.ts/resolvePythonPath",
      category: "path_missing",
      severity: "medium",
      message: `Venv python not found: ${venvPython}, falling back to system python`,
      context: { repoRoot, venvPython },
    });
    return process.platform === "win32" ? "python" : "python3";
  }
}

export const AUGUR_ROOT = resolveRepoRoot();

export const AUGUR_RUNTIME_DIR = resolveRuntimeBase();
export const AUGUR_PYTHON = resolvePythonPath();
export const AUGUR_STATE_DIR = resolveStateDir();
export const AUGUR_LOGS_DIR = resolveLogsDir();
export const AUGUR_CACHE_DIR = resolveCacheDir();
export const AUGUR_VAULT_DIR = resolveVaultDir();
export const AUGUR_DOCUMENTS_DIR = resolveDocumentsDir();
export const AUGUR_RAG_DIR = resolveRagDir();

/**
 * Vault config directory. The domains layout (vault reorg) relocated machine
 * content — including config/ — under _augur/. Mirrors Python's
 * brain_layout.vault_machine_dir(root, "config"): prefer the _augur location,
 * fall back to the legacy flat path for pre-migration vaults. Without this the
 * dashboard read cli_agents.yaml at $VAULT/config/ai/ and never found it after
 * the migration, so every chat send failed with "Unknown CLI".
 */
export const AUGUR_VAULT_CONFIG_DIR = (() => {
  const machine = path.join(AUGUR_VAULT_DIR, "_augur", "config");
  const legacy = path.join(AUGUR_VAULT_DIR, "config");
  if (fsSync.existsSync(machine)) return machine;
  if (fsSync.existsSync(legacy)) return legacy;
  return machine;
})();

/** ADR-087: config/ at repo root */
export const AUGUR_CONFIG_DIR = path.join(AUGUR_ROOT, "config");
/** ADR-270: memory lives inside the user vault */
export const AUGUR_MEMORY_DIR =
  envPath("AUGUR_MEMORY") || path.join(AUGUR_VAULT_DIR, "memory");

// discoverBundles imported from ./plugin-discovery (ADR-126 consolidation)

// Cache for discovered skill data paths and plugin paths
let skillDataPathsCache: Map<string, string> | null = null;
let skillPluginPathsCache: Map<string, string> | null = null;

/**
 * Get all plugin directories to scan.
 * Returns both core (augur-core) and user (augur) plugin directories.
 */
function getAllPluginDirs(): string[] {
  return discoverPluginDirs(AUGUR_ROOT);
}

/**
 * Check if a skill directory is a valid skill.
 * Requires canonical SKILL.md metadata.
 */
function isValidSkillDir(skillDir: string): boolean {
  return fsSync.existsSync(path.join(skillDir, "SKILL.md"));
}

/**
 * Read x-augur-hub from SKILL.md frontmatter.
 * Returns the hub string or null if not found.
 */
function readSkillHub(skillDir: string): string | null {
  const skillMd = path.join(skillDir, "SKILL.md");
  try {
    const content = fsSync.readFileSync(skillMd, "utf8");
    if (!content.startsWith("---")) return null;
    const endIdx = content.indexOf("---", 3);
    if (endIdx === -1) return null;
    const frontmatter = content.slice(3, endIdx);
    const match = frontmatter.match(/^x-augur-hub:\s*(.+)$/m);
    return match?.[1]?.trim() || null;
  } catch {
    return null;
  }
}

function registerSkillMappings(
  skillDir: string,
  skillName: string,
  bundle: string,
  mapping: Map<string, string>,
  pluginMapping: Map<string, string>,
): void {
  if (!isValidSkillDir(skillDir)) {
    return;
  }

  pluginMapping.set(skillName, skillDir);
  mapping.set(skillName, path.join(AUGUR_VAULT_DIR, bundle, skillName));
}

function scanBundleSkills(
  skillsDir: string,
  bundle: string,
  mapping: Map<string, string>,
  pluginMapping: Map<string, string>,
): void {
  const skills = fsSync.readdirSync(skillsDir, { withFileTypes: true });
  for (const skill of skills) {
    if (!skill.isDirectory() || skill.name.startsWith(".")) {
      continue;
    }
    const skillDir = path.join(skillsDir, skill.name);
    registerSkillMappings(skillDir, skill.name, bundle, mapping, pluginMapping);
  }
}

/**
 * Discover skill vault directory mapping from skill directories.
 *
 * @returns Map of skill name to vault directory path
 */
function discoverSkillDataPaths(): Map<string, string> {
  if (skillDataPathsCache) {
    return skillDataPathsCache;
  }

  const mapping = new Map<string, string>();
  const pluginMapping = new Map<string, string>();
  const pluginDirs = getAllPluginDirs();

  for (const pluginsDir of pluginDirs) {
    for (const bundle of discoverBundles(pluginsDir)) {
      const skillsDir = path.join(pluginsDir, bundle, "skills");

      if (!fsSync.existsSync(skillsDir)) continue;

      try {
        scanBundleSkills(skillsDir, bundle, mapping, pluginMapping);
      } catch {
        // Bundle doesn't exist or can't be read
      }
    }
  }

  // Scan managed skill directories (flat structure, e.g. project-brain/capabilities/skills/{skill}/)
  const clientDirs = getClientSkillDirs();
  for (const [, clientDir] of Object.entries(clientDirs)) {
    let skills: fsSync.Dirent[];
    try {
      skills = fsSync.readdirSync(clientDir, { withFileTypes: true });
    } catch {
      continue;
    }

    for (const skill of skills) {
      if (!skill.isDirectory() || skill.name.startsWith(".")) {
        continue;
      }
      const skillDir = path.join(clientDir, skill.name);
      if (!isValidSkillDir(skillDir)) {
        continue;
      }
      // Only add if not already discovered from plugin dirs (plugin dirs take precedence)
      if (!pluginMapping.has(skill.name)) {
        pluginMapping.set(skill.name, skillDir);
        // Determine vault bundle path from canonical SKILL.md metadata.
        let bundle = readSkillHub(skillDir);
        if (!bundle) {
          bundle = skill.name;
        }
        mapping.set(skill.name, path.join(AUGUR_VAULT_DIR, bundle, skill.name));
      }
    }
  }

  skillDataPathsCache = mapping;
  skillPluginPathsCache = pluginMapping;
  return mapping;
}

/**
 * Get the vault data directory path for a skill.
 *
 * @param skillName - The skill name (e.g., 'career', 'health')
 * @returns Full path to skill's vault directory
 * @throws Error if skill not found in any plugin
 */
export function getSkillAugurDataPath(skillName: string): string {
  const mapping = discoverSkillDataPaths();
  const dataDir = mapping.get(skillName);

  if (dataDir) {
    return dataDir;
  }

  throw new Error(
    `[paths] Skill '${skillName}' not found. ` +
      `Ensure the skill exists under project-brain/capabilities/skills/ or the configured private-vault skills root.`,
  );
}

/**
 * @deprecated Use getSkillAugurDataPath instead — renamed for clarity (ADR-177).
 */
export function getSkillDataPath(skillName: string): string {
  return getSkillAugurDataPath(skillName);
}

/**
 * Check if a skill has a vault path configured.
 *
 * @param skillName - The skill name
 * @returns true if skill exists in a discovered bundle
 */
export function hasSkillDataPath(skillName: string): boolean {
  const mapping = discoverSkillDataPaths();
  return mapping.has(skillName);
}

/**
 * Get all discovered skill names.
 *
 * @returns Array of skill names that have data_dir configured
 */
export function getDiscoveredSkills(): string[] {
  const mapping = discoverSkillDataPaths();
  return Array.from(mapping.keys());
}

/**
 * Get the plugin directory path for a skill.
 * Returns the skill source directory (e.g., project-brain/capabilities/skills/knowledge/)
 * which contains SKILL.md and the rest of the skill source.
 *
 * @param skillName - The skill name
 * @returns Full path to skill's plugin directory, or null if not found
 */
export function getSkillPluginPath(skillName: string): string | null {
  // Ensure discovery has run
  discoverSkillDataPaths();
  return skillPluginPathsCache?.get(skillName) ?? null;
}

/**
 * Invalidate the skill data paths cache.
 * Call this when plugins are added/removed/updated.
 */
export function invalidateSkillDataPathsCache(): void {
  skillDataPathsCache = null;
  skillPluginPathsCache = null;
}

/**
 * Get a sub-path within a skill's vault directory.
 *
 * @param skillName - The skill name (e.g., 'career', 'apple')
 * @param subpath - Relative path within the skill vault
 * @returns Full resolved path to the sub-directory
 * @throws Error if skill plugin directory not found
 */
export function getSkillSubPath(skillName: string, subpath: string): string {
  const skillPath = getSkillAugurDataPath(skillName);
  if (!skillPath) {
    throw new Error(
      `[paths] Skill '${skillName}' not found. ` +
        `Cannot resolve sub-path '${subpath}'.`,
    );
  }
  return path.join(skillPath, subpath);
}

// DATA_PATHS proxy removed (ADR-287: MCP-first).
// Use getSkillSubPath(skill, subpath) or getSkillAugurDataPath(skill) instead.
