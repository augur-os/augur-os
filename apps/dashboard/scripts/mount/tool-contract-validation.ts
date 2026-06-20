import fsSync from "fs";
import path from "path";

import { scanSkillConfigs } from "../../lib/plugin-discovery";
import type { SkillConfig } from "../../lib/plugin-discovery/types";

type AssembledToolConfig = {
  core_tools: string[];
  tool_groups: Record<string, string[]>;
  pages: Record<
    string,
    {
      description: string;
      groups: string[];
      max_tools: number;
      skill?: string;
    }
  >;
  skill_tool_groups: Record<string, { tools: string[] }>;
};

export type ToolContractIssue = {
  code:
    | "missing-register-tools"
    | "page-references-unloadable-skill-tools"
    | "ui-skill-tools-unreachable";
  message: string;
  skill?: string;
  page?: string;
  tools?: string[];
};

type ValidateOptions = {
  repoRoot: string;
  assembled: AssembledToolConfig;
  skillConfigs?: SkillConfig[];
};

function hasRegisterToolsEntrypoint(skillConfig: SkillConfig): boolean {
  const mcpEntrypoint = getMcpEntrypointPath(skillConfig);
  if (!fsSync.existsSync(mcpEntrypoint)) return false;
  try {
    const content = fsSync.readFileSync(mcpEntrypoint, "utf8");
    return /\bregister_tools\b/.test(content);
  } catch {
    return false;
  }
}

function getMcpEntrypointPath(skillConfig: SkillConfig): string {
  const skillDir = path.dirname(skillConfig.path);
  return path.join(skillDir, "scripts", "mcp", "__init__.py");
}

function hasLocalMcpEntrypoint(skillConfig: SkillConfig): boolean {
  const skillDir = path.dirname(skillConfig.path);
  return fsSync.existsSync(path.join(skillDir, "scripts", "mcp"));
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}

export function validateAssembledToolContracts({
  repoRoot,
  assembled,
  skillConfigs = scanSkillConfigs({ startDir: repoRoot }),
}: ValidateOptions): ToolContractIssue[] {
  const issues: ToolContractIssue[] = [];
  const declaredToolsBySkill = new Map<string, string[]>();
  const skillByDeclaredTool = new Map<string, string>();
  const loadableSkills = new Set<string>();

  for (const skillConfig of skillConfigs) {
    const declaredTools = Array.isArray(skillConfig.config.mcp_tools)
      ? unique(skillConfig.config.mcp_tools)
      : [];
    if (declaredTools.length === 0) continue;

    const hasLocalMcp = hasLocalMcpEntrypoint(skillConfig);

    if (hasLocalMcp) {
      declaredToolsBySkill.set(skillConfig.skill, declaredTools);
      for (const tool of declaredTools) {
        skillByDeclaredTool.set(tool, skillConfig.skill);
      }
    }

    if (hasLocalMcp && !hasRegisterToolsEntrypoint(skillConfig)) {
      issues.push({
        code: "missing-register-tools",
        skill: skillConfig.skill,
        tools: declaredTools,
        message: `Skill ${skillConfig.skill} declares MCP tools but scripts/mcp/__init__.py does not export register_tools(): ${declaredTools.join(", ")}`,
      });
      continue;
    }

    loadableSkills.add(skillConfig.skill);
  }

  const loadableDeclaredTools = new Set<string>();
  for (const skill of loadableSkills) {
    for (const tool of declaredToolsBySkill.get(skill) ?? []) {
      loadableDeclaredTools.add(tool);
    }
  }

  const grantedToolsBySkill = new Map<string, Set<string>>();

  for (const [page, pageConfig] of Object.entries(assembled.pages)) {
    const pageTools = new Set<string>();

    for (const group of pageConfig.groups ?? []) {
      for (const tool of assembled.tool_groups[group] ?? []) {
        pageTools.add(tool);
      }
    }

    if (pageConfig.skill && loadableSkills.has(pageConfig.skill)) {
      for (const tool of assembled.skill_tool_groups[pageConfig.skill]?.tools ?? []) {
        pageTools.add(tool);
      }
    }

    if (pageConfig.skill) {
      const granted = grantedToolsBySkill.get(pageConfig.skill) ?? new Set<string>();
      for (const tool of pageTools) {
        granted.add(tool);
      }
      grantedToolsBySkill.set(pageConfig.skill, granted);
    }

    const unloadableSkillTools = unique(
      Array.from(pageTools).filter((tool) => {
        const owner = skillByDeclaredTool.get(tool);
        return owner !== undefined && !loadableDeclaredTools.has(tool);
      }),
    );
    if (unloadableSkillTools.length > 0) {
      issues.push({
        code: "page-references-unloadable-skill-tools",
        page,
        tools: unloadableSkillTools,
        message: `Page ${page} grants skill-owned tools without a loadable MCP backend contract: ${unloadableSkillTools.join(", ")}`,
      });
    }
  }

  for (const [skill, declaredTools] of declaredToolsBySkill.entries()) {
    if (!loadableSkills.has(skill)) continue;
    if (!grantedToolsBySkill.has(skill)) continue;

    const granted = grantedToolsBySkill.get(skill) ?? new Set<string>();
    const unreachable = declaredTools.filter((tool) => !granted.has(tool));
    if (unreachable.length > 0) {
      issues.push({
        code: "ui-skill-tools-unreachable",
        skill,
        tools: unreachable,
        message: `Skill ${skill} has assembled pages but these declared tools are unreachable from them: ${unreachable.join(", ")}`,
      });
    }
  }

  return issues;
}

export function assertValidAssembledToolContracts(options: ValidateOptions): void {
  const issues = validateAssembledToolContracts(options);
  if (issues.length === 0) return;
  const details = issues.map((issue) => `- ${issue.message}`).join("\n");
  throw new Error(`Tool contract validation failed:\n${details}`);
}
