import { NextResponse } from "next/server";
import path from "path";

import { readDisabledSkills } from "@/lib/server/skillsState";
import { getRepoRoot } from "@/lib/server/repo";
import { callMCPTool } from "@/lib/mcp/MCPBridge";
import {
  normalizeSkillSlug,
  promptSlugFromTrigger,
} from "@/lib/server/skillSlug";
import {
  buildSkillPathMap,
  collectSkillSubdir,
} from "@/lib/server/skillsScanning";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type SkillSummary = {
  slug: string;
  title: string;
  description: string;
  triggers: string[];
};

type ResourceItem = {
  uri: string;
  skill: string;
  kind: "overview" | "module" | "reference";
  name: string;
  filePath: string;
};

type PromptItem = {
  name: string;
  skill: string;
  trigger: string;
  filePath: string;
};

type ToolItem = {
  name: string;
  kind: "core" | "script";
  skill?: string;
  filePath: string;
};

type RegistrySkill = {
  name?: string;
  display_name?: string;
  description?: string;
  triggers?: string[];
};

type RegistryResponse = {
  skills?: RegistrySkill[];
};

type SkillBuildResult = {
  summary: SkillSummary;
  resources: ResourceItem[];
  prompts: PromptItem[];
  tools: ToolItem[];
};

const CORE_TOOLS: Array<{ name: string }> = [
  { name: "list-skills" },
  { name: "list-chains" },
  { name: "get-skill" },
  { name: "load-module" },
  { name: "load-reference" },
  { name: "skill-action" },
  { name: "get-config" },
  { name: "find-skill" },
  { name: "metrics" },
  { name: "health" },
  { name: "cache-control" },
  { name: "cross-skill" },
];

function toCoreTools(repoRoot: string): ToolItem[] {
  const mcpServerFile = path.join(repoRoot, "src/lib", "mcp", "server.py");
  return CORE_TOOLS.map((tool) => ({
    name: tool.name,
    kind: "core",
    filePath: mcpServerFile,
  }));
}

function getSkillId(skill: RegistrySkill): string {
  return typeof skill.name === "string" ? skill.name : "";
}

function resolveSkillPath(
  skillId: string,
  skillDirs: Map<string, string>,
): string | undefined {
  const normalizedSkillId = normalizeSkillSlug(skillId);
  if (skillDirs.has(normalizedSkillId)) {
    return skillDirs.get(normalizedSkillId);
  }
  return undefined;
}

function toTriggers(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (entry): entry is string => typeof entry === "string" && Boolean(entry),
  );
}

function mapResources(
  skillId: string,
  kind: ResourceItem["kind"],
  baseSegment: "modules" | "references",
  entries: Array<{ name: string; filePath: string }>,
): ResourceItem[] {
  return entries.map((entry) => ({
    uri: `augur://${skillId}/${baseSegment}/${entry.name}`,
    skill: skillId,
    kind,
    name: entry.name,
    filePath: entry.filePath,
  }));
}

async function buildSkillResult(
  skill: RegistrySkill,
  skillDirs: Map<string, string>,
): Promise<SkillBuildResult | null> {
  const skillId = getSkillId(skill);
  if (!skillId) {
    return null;
  }

  const skillDir = resolveSkillPath(skillId, skillDirs);
  if (!skillDir) {
    return null;
  }

  const skillMdPath = path.join(skillDir, "SKILL.md");
  const triggers = toTriggers(skill.triggers);

  const [modules, refs, scripts] = await Promise.all([
    collectSkillSubdir(skillDir, "modules", ".md"),
    collectSkillSubdir(skillDir, "references", ".md"),
    collectSkillSubdir(skillDir, "scripts", ".py"),
  ]);

  const resources: ResourceItem[] = [
    {
      uri: `augur://${skillId}/overview`,
      skill: skillId,
      kind: "overview",
      name: "overview",
      filePath: skillMdPath,
    },
    ...mapResources(skillId, "module", "modules", modules),
    ...mapResources(skillId, "reference", "references", refs),
  ];

  const prompts: PromptItem[] = triggers.map((trigger) => ({
    name: `${skillId}_${promptSlugFromTrigger(trigger)}`,
    skill: skillId,
    trigger,
    filePath: skillMdPath,
  }));

  const tools: ToolItem[] = scripts.map((script) => ({
    name: `${skillId}_${script.name}`,
    kind: "script",
    skill: skillId,
    filePath: script.filePath,
  }));

  return {
    summary: {
      slug: skillId,
      title: (skill.display_name || skillId).trim(),
      description: (skill.description || "").trim(),
      triggers,
    },
    resources,
    prompts,
    tools,
  };
}

export async function GET() {
  const repoRoot = getRepoRoot();

  try {
    // Fetch data in parallel — CLI may fail if not installed, degrade gracefully
    const [disabled, registry, skillDirs] = await Promise.all([
      readDisabledSkills(),
      callMCPTool("list-skills", {})
        .then((result): RegistryResponse => {
          if (result.isError) return { skills: [] };
          const text = result.content?.[0]?.text ?? "{}";
          const data = JSON.parse(text) as { skills?: RegistrySkill[] };
          return { skills: Array.isArray(data.skills) ? data.skills : [] };
        })
        .catch((): RegistryResponse => ({ skills: [] })),
      buildSkillPathMap(),
    ]);

    const registrySkills = Array.isArray(registry.skills)
      ? registry.skills
      : [];

    const skills: SkillSummary[] = [];
    const resources: ResourceItem[] = [];
    const prompts: PromptItem[] = [];
    const tools: ToolItem[] = toCoreTools(repoRoot);

    const skillResults = (
      await Promise.all(
        registrySkills.map((skill) => buildSkillResult(skill, skillDirs)),
      )
    ).filter(
      (skillResult): skillResult is SkillBuildResult => Boolean(skillResult),
    );

    for (const skillResult of skillResults) {
      skills.push(skillResult.summary);
      resources.push(...skillResult.resources);
      prompts.push(...skillResult.prompts);
      tools.push(...skillResult.tools);
    }

    // Sort all collections
    skills.sort((a, b) => a.title.localeCompare(b.title));
    resources.sort((a, b) => a.uri.localeCompare(b.uri));
    prompts.sort((a, b) => a.name.localeCompare(b.name));
    tools.sort((a, b) => a.name.localeCompare(b.name));

    return NextResponse.json({
      generatedAt: new Date().toISOString(),
      disabledSkills: Array.from(disabled).sort((a, b) => a.localeCompare(b)),
      skills,
      counts: {
        skills: skills.length,
        resources: resources.length,
        prompts: prompts.length,
        tools: tools.length,
      },
      resources,
      prompts,
      tools,
    });
  } catch (error) {
    return NextResponse.json(
      { error: (error as Error).message },
      { status: 500 },
    );
  }
}
