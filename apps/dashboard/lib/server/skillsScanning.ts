/**
 * Skills Directory Scanning
 *
 * Provides unified skill package discovery across the codebase.
 * Consolidates duplicated scanning logic from mcp/capabilities and setup/skills/manager.
 */
import path from "path";
import matter from "gray-matter";

import { getRepoRoot } from "./repo";
import { normalizeSkillSlug } from "./skillSlug";
import { fileExists, safeReaddir, safeReadFile } from "./fileOps";
import { getManagedSkillSourcesInScanOrder } from "./managedSkillSources";

/** Legacy layer labels retained for compatibility with older registry shapes. */
const SKILL_LAYERS = ["factory", "horizontal", "vertical", "system"] as const;
export type SkillLayer = (typeof SKILL_LAYERS)[number] | "root";

/** Patterns to exclude from skill scanning (test skills, placeholders, etc.) */
const EXCLUDE_PATTERNS = [
  /^test-/i, // test-skill, test-wizard-complete, etc.
  /^new-skill$/i, // new-skill placeholder
  /-test$/i, // anything ending in -test
  /^wizard-test/i, // wizard test skills
];

export interface ScannedSkill {
  slug: string;
  path: string; // Canonical display path relative to project-brain/capabilities/skills/
  absolutePath: string; // Full path to skill directory
  layer: SkillLayer;
  title: string;
  description: string;
  hasSkillMd: boolean;
}

export interface SkillMetadata {
  displayName: string;
  description: string;
  canonicalId: string; // Normalized slug
}

/**
 * Clean a description string (remove trailing triggers, punctuation).
 */
function cleanDescription(raw: string): string {
  const idx = raw.indexOf("Triggers");
  const out = idx === -1 ? raw : raw.slice(0, idx);
  return out.replace(/[.\-\s]+$/, "").trim();
}

/**
 * Parse frontmatter from a SKILL.md file.
 */
function parseFrontmatter(markdown: string): {
  name: string;
  description: string;
} {
  const parsed = matter(markdown);
  const name =
    typeof parsed.data?.name === "string" ? parsed.data.name.trim() : "";
  const description =
    typeof parsed.data?.description === "string"
      ? cleanDescription(parsed.data.description)
      : "";
  return { name, description };
}

/**
 * Find the SKILL.md file in a skill directory.
 * Checks both standard structure and skill-package subdirectory.
 *
 * @param skillDir - Path to skill directory
 * @returns Path to SKILL.md or null if not found
 */
export async function findSkillMdPath(
  skillDir: string,
): Promise<string | null> {
  const candidates = [
    path.join(skillDir, "SKILL.md"),
    path.join(skillDir, "skill-package", "SKILL.md"),
  ];

  const checks = await Promise.all(
    candidates.map(async (candidate) => ({
      candidate,
      exists: await fileExists(candidate),
    })),
  );
  const match = checks.find((check) => check.exists);
  if (match) return match.candidate;

  return null;
}

/**
 * Check if a directory contains a valid skill package.
 *
 * @param skillDir - Path to check
 * @returns true if directory contains SKILL.md
 */
async function isValidSkill(skillDir: string): Promise<boolean> {
  return (await findSkillMdPath(skillDir)) !== null;
}

/**
 * Read metadata from a skill's SKILL.md file.
 *
 * @param skillDir - Path to skill directory
 * @returns Metadata or null if not found
 */
export async function getSkillMetadata(
  skillDir: string,
): Promise<SkillMetadata | null> {
  const skillMdPath = await findSkillMdPath(skillDir);
  if (!skillMdPath) return null;

  const content = await safeReadFile(skillMdPath);
  if (!content) return null;

  const folderName = path.basename(skillDir);
  const { name, description } = parseFrontmatter(content);
  const displayName = name || folderName;
  const canonicalId = normalizeSkillSlug(displayName || folderName);

  return { displayName, description, canonicalId };
}

function inferSkillLayer(scopeName: string): SkillLayer {
  if (scopeName.startsWith("factory-")) return "factory";
  if (scopeName.startsWith("vertical-")) return "vertical";
  if (scopeName.startsWith("horizontal-")) return "horizontal";
  if (scopeName.startsWith("system-")) return "system";
  return "root";
}

function shouldSkipSkillEntry(entry: {
  isDirectory(): boolean;
  name: string;
}): boolean {
  if (!entry.isDirectory()) {
    return true;
  }
  return EXCLUDE_PATTERNS.some((pattern) => pattern.test(entry.name));
}

async function buildScannedSkillRecord(
  scopeName: string,
  skillsDir: string,
  entryName: string,
  layer: SkillLayer,
): Promise<ScannedSkill | null> {
  const skillDir = path.join(skillsDir, entryName);
  const skillMdPath = await findSkillMdPath(skillDir);
  if (!skillMdPath) {
    return null;
  }

  const metadata = await getSkillMetadata(skillDir);
  return {
    slug: metadata?.canonicalId || normalizeSkillSlug(entryName),
    path: entryName,
    absolutePath: skillDir,
    layer,
    title: metadata?.displayName || entryName,
    description: metadata?.description || "",
    hasSkillMd: true,
  };
}

/**
 * Scan a canonical managed skills directory.
 */
async function scanSkillsRoot(
  skillsDir: string,
): Promise<ScannedSkill[]> {
  if (!(await fileExists(skillsDir))) return [];

  const entries = await safeReaddir(skillsDir);
  const skills: ScannedSkill[] = [];
  const layer = inferSkillLayer("root");

  const scannedEntries = await Promise.all(entries.map(async (entry) => {
    if (shouldSkipSkillEntry(entry)) {
      return null;
    }

    return buildScannedSkillRecord(
      "skills",
      skillsDir,
      entry.name,
      layer,
    );
  }));
  for (const scanned of scannedEntries) {
    if (scanned) skills.push(scanned);
  }

  return skills;
}

function dedupeSkillsWithScanPriority(
  scannedSkills: ScannedSkill[],
): ScannedSkill[] {
  const bySlug = new Map<string, ScannedSkill>();
  for (const skill of scannedSkills) {
    bySlug.set(skill.slug, skill);
  }
  return Array.from(bySlug.values());
}

/**
 * Scan canonical managed skill roots in configured authority order.
 */
export async function scanSkillPackages(options?: {
  pluginsDir?: string;
}): Promise<ScannedSkill[]> {
  const repoRoot = getRepoRoot();
  if (options?.pluginsDir) {
    return scanSkillsRoot(options.pluginsDir);
  }

  const scanned = await Promise.all(
    getManagedSkillSourcesInScanOrder(repoRoot).map((source) =>
      scanSkillsRoot(source.absoluteRoot),
    ),
  );
  return dedupeSkillsWithScanPriority(scanned.flat());
}

/**
 * Build a map of normalized slug to the actual skill package path.
 * Useful for matching registry entries to filesystem paths.
 *
 * @returns Map<normalizedSlug, absolutePath>
 *
 * @example
 * ```typescript
 * const skillDirs = await buildSkillPathMap();
 * const path = skillDirs.get('executor'); // '/repo/project-brain/capabilities/skills/executor'
 * ```
 */
export async function buildSkillPathMap(): Promise<Map<string, string>> {
  const skills = await scanSkillPackages();
  const map = new Map<string, string>();

  for (const skill of skills) {
    map.set(skill.slug, skill.absolutePath);
  }

  return map;
}

/**
 * Collect subdirectory contents for a skill.
 * Used to discover modules, references, and scripts.
 *
 * @param skillDir - Skill directory path
 * @param subdir - Subdirectory name (e.g., 'modules', 'references', 'scripts')
 * @param extension - File extension to filter (e.g., '.md', '.py')
 * @returns Array of { name, filePath } for matching files
 */
export async function collectSkillSubdir(
  skillDir: string,
  subdir: string,
  extension: string,
): Promise<Array<{ name: string; filePath: string }>> {
  const subdirPath = path.join(skillDir, subdir);
  const entries = await safeReaddir(subdirPath);
  const results: Array<{ name: string; filePath: string }> = [];

  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (!entry.name.endsWith(extension)) continue;

    const name = entry.name.slice(0, -extension.length);
    results.push({
      name,
      filePath: path.join(subdirPath, entry.name),
    });
  }

  return results;
}
