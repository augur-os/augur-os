import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SKILL_ID = "auto-brain-hub-coverage";

const legacyPatterns = [
  "plugins/<bundle>/skills/<skill>/...",
  "skills/<skill>/...",
  "skills/rag/augur/data/",
  "skills/rag/dashboard/page.tsx",
  "skills/rag/dashboard.yaml",
  "skills/rag/api/",
  "skills/ai/augur/agent-rules.md",
  "skills/ai/augur/agent-topics/",
  "skills/knowledge/augur/augur.yaml",
];

const canonicalTargets = [
  "project-brain/capabilities/skills/<skill>/...",
  "~/Library/Application Support/Augur/rag/",
  "project-brain/capabilities/skills/rag/SKILL.md",
  "project-brain/capabilities/skills/rag/scripts/mcp/",
  "docs/agent-topics/agent-rules.md",
  "docs/agent-topics/",
  "project-brain/capabilities/skills/knowledge/SKILL.md",
];

const difficultyLevels = [
  "d0: Find stale brain-hub references across live markdown surfaces.",
  "d1: Resolve replacements against live skill, docs, and page paths.",
  "d2: Repair stale references in place when the canonical target is known.",
];

type ToolArgs = Record<string, unknown>;

async function loadToolJson<T>(tool: string, args: ToolArgs): Promise<T> {
  const result = await callMCPTool(tool, args);

  if (result.isError) {
    throw new Error(MCPBridge.extractText(result) || `MCP tool failed: ${tool}`);
  }

  const raw = MCPBridge.extractText(result).trim();
  return raw ? (JSON.parse(raw) as T) : ({} as T);
}

function summarizeDoc(content: unknown): string {
  if (typeof content !== "string" || content.trim().length === 0) {
    return "Documentation is unavailable.";
  }

  const firstParagraph = content
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"))[0];

  return firstParagraph || "Documentation is unavailable.";
}

export async function GET(): Promise<Response> {
  try {
    const [health, actions, doc] = await Promise.all([
      loadToolJson("get-skill-health", { skill_id: SKILL_ID }),
      loadToolJson<{ actions?: unknown[] }>("list-skill-actions", { skill_id: SKILL_ID }),
      loadToolJson<{ content?: string }>("get-skill-doc", { skill_id: SKILL_ID }),
    ]);

    return NextResponse.json({
      skill: SKILL_ID,
      generatedAt: new Date().toISOString(),
      health,
      actions: actions.actions ?? [],
      overview: summarizeDoc(doc.content),
      legacyPatterns,
      canonicalTargets,
      difficultyLevels,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        skill: SKILL_ID,
        error: message,
      },
      { status: 500 },
    );
  }
}
