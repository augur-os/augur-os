import fs from "fs/promises";
import path from "path";
import matter from "gray-matter";

import { getRepoRoot } from "@/lib/server/repo";
import type { SkillCommand, SkillPrompt } from "@/lib/browse/types";
import { getManagedSkillSourcesInPriorityOrder } from "./managedSkillSources";
import { readSkillCommands, readSkillPrompts } from "./skillContent";

import { normalizeSlug, parseSkillSlug } from "@/lib/browse/skillSlug";
import type { ParsedSkillSlug } from "@/lib/browse/skillSlug";
export { normalizeSlug, parseSkillSlug };
export type { ParsedSkillSlug };

export type SkillLookup = {
  path: string;
  absolutePath?: string;
  baseDir: string;
  canonicalId: string;
  folderName: string;
  source: "skill-md" | "skill-package";
};

export type SkillMeta = {
  title?: string;
  tabLabel?: string;
  description?: string;
  icon?: string;
  mcpTools?: string[];
  prompts?: SkillPrompt[];
  commands?: SkillCommand[];
};

export function stripAutoHeader(markdown: string): string {
  return markdown.replace(/^<!--[\s\S]*?-->\s*/m, "").trimStart();
}

export function getSourcePrefix(resolved: SkillLookup): string {
  return resolved.baseDir
    ? `${resolved.baseDir}/${resolved.path}`
    : `plugins/${resolved.path}`;
}

async function parseSkillFile(filePath: string): Promise<string | null> {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    const parsed = matter(raw);
    const name =
      typeof parsed.data?.name === "string" ? parsed.data.name.trim() : "";
    return name || null;
  } catch {
    return null;
  }
}

async function readSkillMetaFile(
  skillMd: string,
  skillId: string,
): Promise<SkillMeta | null> {
  try {
    const raw = await fs.readFile(skillMd, "utf8");
    const [prompts, commands] = await Promise.all([
      readSkillPrompts(skillId),
      readSkillCommands(skillId),
    ]);
    const parsed = matter(raw);
    const d = parsed.data || {};
    return {
      title: d.name || skillId,
      tabLabel: d["x-augur-tab"] || d.name || skillId,
      description: typeof d.description === "string" ? d.description : undefined,
      icon: undefined, // resolved by caller
      mcpTools: Array.isArray(d["x-augur-mcp-tools"]) ? d["x-augur-mcp-tools"] : [],
      prompts,
      commands,
    };
  } catch {
    return null;
  }
}

/** Extract frontmatter metadata from SKILL.md for auto-page generation */
export async function readSkillMeta(skillId: string): Promise<SkillMeta | null> {
  const repoRoot = getRepoRoot();
  const sources = getManagedSkillSourcesInPriorityOrder(repoRoot);
  const metas = await Promise.all(
    sources.map((source) =>
      readSkillMetaFile(path.join(source.absoluteRoot, skillId, "SKILL.md"), skillId),
    ),
  );
  return metas.find(Boolean) ?? null;
}

async function checkSkillDir(
  skillDir: string,
  target: string,
): Promise<Omit<SkillLookup, "path" | "baseDir"> | null> {
  const folderName = path.basename(skillDir);
  const normalizedFolder = normalizeSlug(folderName);

  const skillMdPath = path.join(skillDir, "SKILL.md");
  const frontmatterName = await parseSkillFile(skillMdPath);
  const canonicalName = frontmatterName || folderName;
  const normalizedCanonical = normalizeSlug(canonicalName);

  if (target === normalizedFolder || target === normalizedCanonical) {
    return {
      canonicalId: canonicalName,
      folderName,
      source: "skill-md",
    };
  }

  const nestedSkillMdPath = path.join(skillDir, "skill-package", "SKILL.md");
  const nestedName = await parseSkillFile(nestedSkillMdPath);
  if (nestedName && target === normalizeSlug(nestedName)) {
    return {
      canonicalId: nestedName,
      folderName,
      source: "skill-package",
    };
  }

  return null;
}

async function readDirectoryEntries(
  basePath: string,
): Promise<Array<{ name: string; isDirectory: () => boolean }>> {
  try {
    return await fs.readdir(basePath, { withFileTypes: true });
  } catch {
    return [];
  }
}

async function findInDirectory(
  basePath: string,
  target: string,
  buildPath: (entryName: string) => string,
  baseDirType: SkillLookup["baseDir"],
): Promise<SkillLookup | null> {
  const entries = await readDirectoryEntries(basePath);
  const matches = await Promise.all(entries.map(async (entry) => {
    if (!entry.isDirectory()) return null;
    const skillDir = path.join(basePath, entry.name);
    const match = await checkSkillDir(skillDir, target);
    if (match) {
      return {
        ...match,
        path: buildPath(entry.name),
        absolutePath: skillDir,
        baseDir: baseDirType,
      };
    }
    return null;
  }));
  return matches.find(Boolean) ?? null;
}

export async function resolveSkillInfo(
  skill: string,
): Promise<SkillLookup | null> {
  const repoRoot = getRepoRoot();
  const target = normalizeSlug(skill);

  const matches = await Promise.all(
    getManagedSkillSourcesInPriorityOrder(repoRoot).map((source) =>
      findInDirectory(
        source.absoluteRoot,
        target,
        (entryName) => entryName,
        source.displayBaseDir,
      ),
    ),
  );
  return matches.find(Boolean) ?? null;
}
