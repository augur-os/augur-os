import { NextResponse } from "next/server";
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type FocusStatePayload = {
  current_page?: unknown;
  skill_name?: unknown;
  bundle?: unknown;
  session_id?: unknown;
  source?: unknown;
  timestamp?: unknown;
};

function toTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function parsePayload(body: FocusStatePayload) {
  const current_page = toTrimmedString(body.current_page);
  const skill_name = toTrimmedString(body.skill_name);
  const bundle = toTrimmedString(body.bundle);
  const session_id = toTrimmedString(body.session_id) || "dashboard-main";
  const source = toTrimmedString(body.source) || "dashboard";
  const timestamp = toTrimmedString(body.timestamp);

  if (!current_page || !skill_name || !bundle) {
    throw new Error("current_page, skill_name, and bundle are required");
  }

  return {
    scope: "focus-state",
    current_page,
    skill_name,
    bundle,
    session_id,
    source,
    ...(timestamp ? { timestamp } : {}),
  };
}

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as FocusStatePayload;
    const args = parsePayload(body);
    const mcpContext = extractContextFromRequest(req);
    const result = await callMCPTool("set-config", args, mcpContext);

    if (result.isError) {
      return NextResponse.json(
        {
          error:
            MCPBridge.extractText(result) || "Failed to persist focus state",
        },
        { status: 500 },
      );
    }

    const raw = MCPBridge.extractText(result).trim();
    if (!raw) {
      return NextResponse.json({ success: true });
    }

    try {
      return NextResponse.json(JSON.parse(raw));
    } catch {
      return NextResponse.json({ success: true, result: raw });
    }
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Invalid focus state request";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
