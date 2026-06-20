import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SKILL_ID = "auto-dependency-audit";

const auditSignals = [
  "Run npm audit against apps/dashboard before classifying package risk.",
  "Treat missing or unreadable audit output as operator-visible evidence.",
  "Keep unattended fixes conservative and limited to safe audit repair paths.",
];

const repairPolicy = [
  "d0: scan and summarize vulnerable packages.",
  "d1: validate findings while keeping repair report-only.",
  "d2: allow npm audit fix without force upgrades.",
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
      auditSignals,
      repairPolicy,
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
