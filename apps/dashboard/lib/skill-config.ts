/**
 * Legacy .config reader for enable/disable compatibility only.
 *
 * Dashboard novelty state now lives in the runtime-backed skill UI state store,
 * not in repo-owned `.config` files. This module remains only for the still
 * supported `enabled` flag and legacy settings blobs while the repo finishes
 * retiring `.config` files.
 */

import fs from "fs";
import path from "path";
import yaml from "yaml";
import {
  discoverRepoRoot,
  getProjectBrainSkillsRoot,
} from "./plugin-discovery/paths";
import { AUGUR_RUNTIME_DIR } from "./paths";

export interface SkillConfig {
  enabled: boolean;
  settings: Record<string, unknown>;
  resolved_deps: Record<string, boolean>;
}

const DEFAULT_CONFIG: SkillConfig = {
  enabled: true,
  settings: {},
  resolved_deps: {},
};

// Cache for .config reads
const _configCache: Map<string, SkillConfig> = new Map();
const _cacheTtlMs = 5000;
const _cacheTimestamps: Map<string, number> = new Map();
const _runtimeDisabledCache: { at: number; disabled: Set<string> } = {
  at: 0,
  disabled: new Set(),
};

function runtimeSkillStatePath(): string {
  return path.join(AUGUR_RUNTIME_DIR, "dashboard", "skills-state.yaml");
}

function readRuntimeDisabledSkills(): Set<string> {
  const now = Date.now();
  if (now - _runtimeDisabledCache.at < _cacheTtlMs) {
    return _runtimeDisabledCache.disabled;
  }

  const statePath = runtimeSkillStatePath();
  if (!fs.existsSync(statePath)) {
    _runtimeDisabledCache.at = now;
    _runtimeDisabledCache.disabled = new Set();
    return _runtimeDisabledCache.disabled;
  }

  try {
    const content = fs.readFileSync(statePath, "utf8");
    const parsed = yaml.parse(content) as { disabled?: unknown } | null;
    const disabledRaw: unknown[] = Array.isArray(parsed?.disabled)
      ? parsed.disabled
      : [];
    const disabled = new Set(
      disabledRaw
        .flatMap((entry) => {
          if (typeof entry !== "string") return [];
          const trimmed = entry.trim();
          return trimmed ? [trimmed] : [];
        }),
    );
    _runtimeDisabledCache.at = now;
    _runtimeDisabledCache.disabled = disabled;
    return disabled;
  } catch {
    _runtimeDisabledCache.at = now;
    _runtimeDisabledCache.disabled = new Set();
    return _runtimeDisabledCache.disabled;
  }
}

function readRuntimeState(): Record<string, unknown> {
  const statePath = runtimeSkillStatePath();
  if (!fs.existsSync(statePath)) {
    return { version: 1 };
  }
  try {
    const content = fs.readFileSync(statePath, "utf8");
    const parsed = yaml.parse(content) ?? {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : { version: 1 };
  } catch {
    return { version: 1 };
  }
}

function writeRuntimeState(next: Record<string, unknown>): void {
  const statePath = runtimeSkillStatePath();
  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  fs.writeFileSync(statePath, yaml.stringify({ version: 1, ...next }), "utf8");
  _runtimeDisabledCache.at = 0;
  _runtimeDisabledCache.disabled = new Set();
}

function canonicalExistingPath(entry: string): string {
  try {
    return fs.realpathSync(entry);
  } catch {
    return path.resolve(entry);
  }
}

function canonicalSkillSlug(dirPath: string): string | null {
  const repoRoot = discoverRepoRoot(dirPath);
  const skillsRoot = getProjectBrainSkillsRoot(repoRoot);
  const normalized = path.resolve(dirPath);
  const parent = path.dirname(normalized);
  if (canonicalExistingPath(parent) !== canonicalExistingPath(skillsRoot)) {
    return null;
  }
  const slug = path.basename(normalized);
  return slug && !slug.startsWith(".") ? slug : null;
}

/**
 * Read a .config file from the given directory.
 * Returns default config (enabled: true) if no .config file exists.
 */
export function readConfigFile(dirPath: string): SkillConfig {
  const now = Date.now();
  const cached = _configCache.get(dirPath);
  const cachedTime = _cacheTimestamps.get(dirPath) ?? 0;

  if (cached && now - cachedTime < _cacheTtlMs) {
    return cached;
  }

  const canonicalSkill = canonicalSkillSlug(dirPath);
  if (canonicalSkill) {
    const disabled = readRuntimeDisabledSkills();
    const config: SkillConfig = {
      enabled: !disabled.has(canonicalSkill),
      settings: {},
      resolved_deps: {},
    };
    _configCache.set(dirPath, config);
    _cacheTimestamps.set(dirPath, now);
    return config;
  }

  const configPath = path.join(dirPath, ".config");

  if (!fs.existsSync(configPath)) {
    _configCache.set(dirPath, DEFAULT_CONFIG);
    _cacheTimestamps.set(dirPath, now);
    return DEFAULT_CONFIG;
  }

  try {
    const content = fs.readFileSync(configPath, "utf8");
    const parsed = yaml.parse(content) ?? {};

    const config: SkillConfig = {
      enabled: parsed.enabled !== false, // default true unless explicitly false
      settings: parsed.settings ?? {},
      resolved_deps: parsed.resolved_deps ?? {},
    };

    _configCache.set(dirPath, config);
    _cacheTimestamps.set(dirPath, now);
    return config;
  } catch (error) {
    console.warn(`Failed to read .config at ${configPath}:`, error);
    _configCache.set(dirPath, DEFAULT_CONFIG);
    _cacheTimestamps.set(dirPath, now);
    return DEFAULT_CONFIG;
  }
}

/**
 * Read a skill's .config file.
 *
 * @param hub - Hub directory name (e.g., "career")
 * @param skill - Skill directory name (e.g., "linkedin-writer")
 * @returns The skill's config
 */
function readSkillConfig(hub: string, skill: string): SkillConfig {
  const repoRoot = discoverRepoRoot();
  const skillDir = path.join(getProjectBrainSkillsRoot(repoRoot), skill);
  return readConfigFile(skillDir);
}

/**
 * Read a hub-level .config file.
 *
 * @param hub - Hub directory name (e.g., "career")
 * @returns The hub's config
 */
function readHubConfig(hub: string): SkillConfig {
  return DEFAULT_CONFIG;
}

/**
 * Check if a skill is enabled.
 * A skill is disabled if:
 *   - Its own .config has enabled: false, OR
 *   - Its hub's .config has enabled: false
 *
 * @param hub - Hub directory name
 * @param skill - Skill directory name
 * @returns true if enabled
 */
function isSkillEnabled(hub: string, skill: string): boolean {
  const hubConfig = readHubConfig(hub);
  if (!hubConfig.enabled) return false;

  const skillConfig = readSkillConfig(hub, skill);
  return skillConfig.enabled;
}

/**
 * Write a .config file to the given directory.
 */
function writeConfigFile(
  dirPath: string,
  config: Partial<SkillConfig>,
): void {
  const canonicalSkill = canonicalSkillSlug(dirPath);
  if (canonicalSkill) {
    const state = readRuntimeState();
    const disabledRaw = Array.isArray(state.disabled) ? state.disabled : [];
    const disabled = new Set(
      disabledRaw
        .flatMap((entry) => {
          if (typeof entry !== "string") return [];
          const trimmed = entry.trim();
          return trimmed ? [trimmed] : [];
        }),
    );
    if (config.enabled === false) {
      disabled.add(canonicalSkill);
    } else if (config.enabled === true) {
      disabled.delete(canonicalSkill);
    }
    state.disabled = Array.from(disabled).sort((a, b) => a.localeCompare(b));
    writeRuntimeState(state);
    _configCache.delete(dirPath);
    _cacheTimestamps.delete(dirPath);
    return;
  }

  const configPath = path.join(dirPath, ".config");

  // Merge with existing config if present
  const existing = readConfigFile(dirPath);
  const merged: SkillConfig = {
    ...existing,
    ...config,
    settings: { ...existing.settings, ...(config.settings ?? {}) },
    resolved_deps: {
      ...existing.resolved_deps,
      ...(config.resolved_deps ?? {}),
    },
  };

  const content = yaml.stringify({
    enabled: merged.enabled,
    ...(Object.keys(merged.settings).length > 0
      ? { settings: merged.settings }
      : {}),
    ...(Object.keys(merged.resolved_deps).length > 0
      ? { resolved_deps: merged.resolved_deps }
      : {}),
  });

  fs.writeFileSync(configPath, content, "utf8");

  // Invalidate cache
  _configCache.delete(dirPath);
  _cacheTimestamps.delete(dirPath);
}

/**
 * Write a skill's .config file.
 */
function writeSkillConfig(
  hub: string,
  skill: string,
  config: Partial<SkillConfig>,
): void {
  const repoRoot = discoverRepoRoot();
  const skillDir = path.join(repoRoot, "plugins", hub, "skills", skill);
  writeConfigFile(skillDir, config);
}

/**
 * Write a hub-level .config file.
 */
function writeHubConfig(
  hub: string,
  config: Partial<SkillConfig>,
): void {
  const repoRoot = discoverRepoRoot();
  const hubDir = path.join(repoRoot, "plugins", hub);
  writeConfigFile(hubDir, config);
}

/**
 * Clear the config cache.
 */
export function clearConfigCache(): void {
  _configCache.clear();
  _cacheTimestamps.clear();
  _runtimeDisabledCache.at = 0;
  _runtimeDisabledCache.disabled = new Set();
}

/**
 * Check if a directory has a .config file with enabled: false.
 * Drop-in replacement for the old isDisabled() check.
 */
export function isDisabledByConfig(dirPath: string): boolean {
  const config = readConfigFile(dirPath);
  return !config.enabled;
}
