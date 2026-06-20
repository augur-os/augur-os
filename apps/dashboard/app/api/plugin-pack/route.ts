import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SKILL_ID = "plugin-pack";

const TARGETS = [
  {
    id: "cowork",
    platform: "Claude Desktop",
    output: ".claude-plugin/plugin.json + marketplace",
  },
  {
    id: "codex",
    platform: "OpenAI Codex",
    output: ".codex-plugin/plugin.json + .agents/plugins/marketplace.json",
  },
  {
    id: "gemini",
    platform: "Gemini CLI",
    output: "gemini-extension.json + ~/.gemini/extensions/augur",
  },
];

const PIPELINE = [
  "profiles.py filters skill metadata per target.",
  "plugin_assembler.py builds the shared assembly pipeline.",
  "formatters/* write the final Cowork, Codex, or Gemini manifest bundle.",
  "Installation happens only after the target manifest is validated.",
];

type ToolArgs = Record<string, unknown>;

async function loadToolJson<T>(tool: string, args: ToolArgs = {}): Promise<T> {
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
      targets: TARGETS,
      pipeline: PIPELINE,
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
