import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SKILL_ID = "auto-dir-alignment";

const managedRoots = [
  "Validate first-level directories in managed vault roots.",
  "Apply the same alignment rules to managed docs roots.",
  "Honor .augur-reserved entries before classifying a directory as drift.",
];

const repairStages = [
  "d0: report alignment violations with a classification only.",
  "d1: rename trivial matches when the closest skill is strong enough.",
  "d2: reserve intentional non-skill names in .augur-reserved.",
  "d3: escalate unknown directories for interactive follow-up.",
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
      managedRoots,
      repairStages,
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
