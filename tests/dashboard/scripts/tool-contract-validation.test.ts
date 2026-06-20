/**
 * @jest-environment node
 */

import fs from "fs/promises";
import os from "os";
import path from "path";

import type { SkillConfig } from "@/lib/plugin-discovery/types";
import {
  assertValidAssembledToolContracts,
  validateAssembledToolContracts,
} from "@/scripts/mount/tool-contract-validation";

type AssembledToolConfig = Parameters<typeof validateAssembledToolContracts>[0]["assembled"];

async function createSkill(
  root: string,
  skill: string,
  {
    hub = "brain",
    mcpTools = [],
    registerTools = true,
  }: { hub?: string; mcpTools?: string[]; registerTools?: boolean } = {},
): Promise<SkillConfig> {
  const skillDir = path.join(root, "skills", skill);
  const mcpDir = path.join(skillDir, "scripts", "mcp");
  await fs.mkdir(mcpDir, { recursive: true });
  await fs.writeFile(
    path.join(skillDir, "SKILL.md"),
    `---\nname: ${skill}\nx-augur-hub: ${hub}\nx-augur-mcp-tools:\n${mcpTools.map((tool) => `  - ${tool}`).join("\n")}\n---\n`,
    "utf8",
  );
  await fs.writeFile(path.join(skillDir, "scripts", "__init__.py"), "", "utf8");
  await fs.writeFile(
    path.join(mcpDir, "__init__.py"),
    registerTools ? "def register_tools(mcp, interceptor, metrics):\n    return None\n" : '"""missing contract"""',
    "utf8",
  );

  return {
    bundle: hub,
    skill,
    config: {
      contributes_to: hub,
      mcp_tools: mcpTools,
    },
    path: path.join(skillDir, "SKILL.md"),
    hasApi: false,
    hasLib: false,
  };
}

function baseAssembled(): AssembledToolConfig {
  return {
    generated_at: "2026-04-12T00:00:00Z",
    core_tools: [],
    tool_groups: {},
    priority_order: [],
    operation_hidden: [],
    pages: {},
    skill_tool_groups: {},
    tools: {},
  };
}

describe("tool contract validation", () => {
  it("flags skills that declare mcp tools but lack register_tools()", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-tool-contract-"));
    const ingest = await createSkill(repoRoot, "ingest", {
      mcpTools: ["wiki-report-data"],
      registerTools: false,
    });

    const issues = validateAssembledToolContracts({
      repoRoot,
      assembled: baseAssembled(),
      skillConfigs: [ingest],
    });

    expect(issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: "missing-register-tools",
          skill: "ingest",
          tools: ["wiki-report-data"],
        }),
      ]),
    );
  });

  it("flags page groups that reference declared tools without a loadable backend contract", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-tool-contract-"));
    const ingest = await createSkill(repoRoot, "ingest", {
      mcpTools: ["wiki-report-data", "wiki-rewrite-candidates"],
      registerTools: false,
    });

    const assembled = baseAssembled();
    assembled.tool_groups = {
      WIKI_MAINTENANCE: ["wiki-report-data", "wiki-rewrite-candidates"],
    };
    assembled.pages = {
      "/workspace/memory": {
        description: "Memory",
        groups: ["WIKI_MAINTENANCE"],
        max_tools: 20,
        skill: "knowledge",
      },
    };

    const issues = validateAssembledToolContracts({
      repoRoot,
      assembled,
      skillConfigs: [ingest],
    });

    expect(issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          code: "page-references-unloadable-skill-tools",
          page: "/workspace/memory",
          tools: ["wiki-report-data", "wiki-rewrite-candidates"],
        }),
      ]),
    );
  });

  it("passes when declared skill tools have a loadable contract and are granted to pages", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-tool-contract-"));
    const knowledge = await createSkill(repoRoot, "knowledge", {
      mcpTools: ["knowledge-memory-read"],
      registerTools: true,
    });
    const ingest = await createSkill(repoRoot, "ingest", {
      mcpTools: ["wiki-report-data", "wiki-rewrite-candidates"],
      registerTools: true,
    });

    const assembled = baseAssembled();
    assembled.tool_groups = {
      WIKI_MAINTENANCE: ["wiki-report-data", "wiki-rewrite-candidates"],
    };
    assembled.pages = {
      "/workspace/memory": {
        description: "Memory",
        groups: ["WIKI_MAINTENANCE"],
        max_tools: 20,
        skill: "knowledge",
      },
    };
    assembled.skill_tool_groups = {
      knowledge: { tools: ["knowledge-memory-read"] },
    };

    expect(() =>
      assertValidAssembledToolContracts({
        repoRoot,
        assembled,
        skillConfigs: [knowledge, ingest],
      }),
    ).not.toThrow();
  });
});
