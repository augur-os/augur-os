/**
 * Prompt template discovery library
 *
 * Server-only: discovers PromptTemplate objects from distributed skill directories.
 * Canonical path: project-brain/capabilities/skills/{skill}/assets/seed-data/prompts/*.md
 * Override path:  <vault>/{skill}/prompts/*.md
 *
 * Each .md file has YAML frontmatter (action, description, dispatch, input_variables,
 * context_hints) and a body with <instructions>, <context>, <task> XML sections
 * using {{handlebars}} variables.
 *
 * Used by:
 *   - /api/prompts/[actionId] (GET route)
 */
import fs from "fs/promises";
import path from "path";
import yaml from "yaml";
import {
  getDiscoveredSkills,
  getSkillAugurDataPath,
  getSkillPluginPath,
} from "@/lib/paths";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PromptTemplate {
  actionId: string;
  filePath: string;
  raw: string;
  frontmatter: Record<string, unknown>;
  body: string;
}

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

let _cache: Map<string, PromptTemplate> | null = null;
let _cacheTime = 0;
const CACHE_TTL_MS = 30_000;

export function invalidatePromptCache(): void {
  _cache = null;
  _cacheTime = 0;
}

// ---------------------------------------------------------------------------
// Frontmatter parsing
// ---------------------------------------------------------------------------

const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/;

/**
 * Split a markdown file into YAML frontmatter and body.
 * Returns `{ frontmatter: {}, body: raw }` when no frontmatter delimiter is found.
 */
export function parseFrontmatter(content: string): {
  frontmatter: Record<string, unknown>;
  body: string;
} {
  const match = content.match(FRONTMATTER_RE);
  if (!match) {
    return { frontmatter: {}, body: content };
  }

  let frontmatter: Record<string, unknown> = {};
  try {
    const parsed = yaml.parse(match[1]);
    if (parsed && typeof parsed === "object") {
      frontmatter = parsed as Record<string, unknown>;
    }
  } catch {
    // Malformed YAML — treat as empty frontmatter
  }

  return { frontmatter, body: match[2] };
}

// ---------------------------------------------------------------------------
// Template rendering
// ---------------------------------------------------------------------------

/**
 * Replace `{{variable}}` placeholders in the template body.
 * Unmatched placeholders are left as-is so callers can see what is missing.
 */
export function renderTemplate(
  body: string,
  variables: Record<string, string>,
): string {
  return body.replace(/\{\{(\w+)\}\}/g, (_match, key: string) => {
    return key in variables ? variables[key] : `{{${key}}}`;
  });
}

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

type PromptDir = {
  dir: string;
  priority: number;
};

async function collectPromptFiles(promptDir: PromptDir): Promise<
  Array<{ fullPath: string; priority: number }>
> {
  let entries: Array<{
    isDirectory(): boolean;
    isFile(): boolean;
    name: string;
  }>;
  try {
    entries = await fs.readdir(promptDir.dir, { withFileTypes: true });
  } catch {
    return [];
  }

  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
    .map((entry) => ({
      fullPath: path.join(promptDir.dir, entry.name),
      priority: promptDir.priority,
    }));
}

function getPromptDirsForSkill(skill: string): PromptDir[] {
  const skillDir = getSkillPluginPath(skill);
  if (!skillDir) {
    return [];
  }

  return [
    { dir: path.join(skillDir, "assets", "prompts"), priority: 1 },
    {
      dir: path.join(skillDir, "assets", "seed-data", "prompts"),
      priority: 2,
    },
    { dir: path.join(getSkillAugurDataPath(skill), "prompts"), priority: 3 },
  ];
}

async function discoverPromptFiles(): Promise<string[]> {
  const files: Array<{ fullPath: string; priority: number }> = [];

  for (const skill of getDiscoveredSkills()) {
    for (const promptDir of getPromptDirsForSkill(skill)) {
      files.push(...(await collectPromptFiles(promptDir)));
    }
  }

  return files
    .sort((left, right) =>
      left.priority === right.priority
        ? left.fullPath.localeCompare(right.fullPath)
        : left.priority - right.priority,
    )
    .map((entry) => entry.fullPath);
}

/**
 * Discover all prompt templates and return a Map keyed by actionId.
 *
 * The actionId is derived from the frontmatter `action` field if present,
 * otherwise from the filename (without .md extension).
 *
 * Results are cached with a 30 s TTL.
 */
export async function loadPromptTemplates(): Promise<
  Map<string, PromptTemplate>
> {
  if (_cache && Date.now() - _cacheTime < CACHE_TTL_MS) {
    return _cache;
  }

  const files = await discoverPromptFiles();
  const templates = new Map<string, PromptTemplate>();

  for (const filePath of files) {
    try {
      const raw = await fs.readFile(filePath, "utf-8");
      const { frontmatter, body } = parseFrontmatter(raw);

      const actionId =
        typeof frontmatter.action === "string"
          ? frontmatter.action
          : path.basename(filePath, ".md");

      templates.set(actionId, {
        actionId,
        filePath,
        raw,
        frontmatter,
        body,
      });
    } catch {
      // Unreadable file — skip silently
    }
  }

  _cache = templates;
  _cacheTime = Date.now();
  return templates;
}

/**
 * Get a single prompt template by actionId.
 * Returns `undefined` when not found.
 */
export async function getPromptTemplate(
  actionId: string,
): Promise<PromptTemplate | undefined> {
  const templates = await loadPromptTemplates();
  return templates.get(actionId);
}
