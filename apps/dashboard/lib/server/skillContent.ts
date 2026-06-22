import fs from "fs/promises";
import type { Dirent } from "fs";
import path from "path";
import { parseMatter } from "./frontmatter";

import type { SkillCommand, SkillPrompt } from "@/lib/browse/types";
import { getProjectBrainSkillsRoot } from "@/lib/plugin-discovery/paths";
import { getRepoRoot } from "@/lib/server/repo";
import { getManagedSkillSourcesInPriorityOrder } from "./managedSkillSources";

type MarkdownSkillContent = {
  id: string;
  label: string;
  description?: string;
  icon?: string;
  body: string;
};

function frontmatterString(
  data: Record<string, unknown>,
  key: string,
): string | undefined {
  const value = data[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function humanize(id: string): string {
  return id
    .split(/[-_]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

async function hasSkillFile(skillDir: string): Promise<boolean> {
  try {
    await fs.readFile(path.join(skillDir, "SKILL.md"), "utf8");
    return true;
  } catch {
    return false;
  }
}

async function resolveSkillContentDir(skillId: string): Promise<string> {
  const repoRoot = getRepoRoot();
  const candidates = getManagedSkillSourcesInPriorityOrder(repoRoot).map((source) =>
    path.join(source.absoluteRoot, skillId),
  );
  const availability = await Promise.all(
    candidates.map(async (skillDir) => ({
      skillDir,
      exists: await hasSkillFile(skillDir),
    })),
  );
  const match = availability.find((candidate) => candidate.exists);
  if (match) return match.skillDir;

  return path.join(getProjectBrainSkillsRoot(repoRoot), skillId);
}

async function readMarkdownFile(
  filePath: string,
): Promise<MarkdownSkillContent | null> {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    const parsed = parseMatter(raw);
    const data = parsed.data ?? {};
    const fallbackId = path.basename(filePath, path.extname(filePath));
    const id = frontmatterString(data, "id") ?? fallbackId;

    return {
      id,
      label: frontmatterString(data, "label") ?? humanize(id),
      description: frontmatterString(data, "description"),
      icon: frontmatterString(data, "icon"),
      body: parsed.content,
    };
  } catch {
    return null;
  }
}

async function scanDir(dir: string): Promise<MarkdownSkillContent[]> {
  let entries: Dirent[];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }

  const files = entries.flatMap((entry) =>
    entry.isFile() && entry.name.endsWith(".md")
      ? [path.join(dir, entry.name)]
      : [],
  );

  const parsed = await Promise.all(files.map(readMarkdownFile));
  return parsed.filter((item): item is MarkdownSkillContent => item !== null);
}

export async function readSkillPrompts(
  skillId: string,
): Promise<SkillPrompt[]> {
  const dir = path.join(await resolveSkillContentDir(skillId), "prompts");
  const prompts = await scanDir(dir);
  return prompts.map((prompt) => ({
    id: prompt.id,
    label: prompt.label,
    description: prompt.description,
    icon: prompt.icon,
    prompt: prompt.body,
  }));
}

export async function readSkillCommands(
  skillId: string,
): Promise<SkillCommand[]> {
  const dir = path.join(await resolveSkillContentDir(skillId), "commands");
  const commands = await scanDir(dir);
  return commands.map((command) => ({
    id: command.id,
    label: command.label,
    description: command.description,
    icon: command.icon,
    command: `/${command.id}`,
  }));
}
