import { NextResponse } from "next/server";
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type UsageTrackPayload = {
  page?: unknown;
  action?: unknown;
  timestamp?: unknown;
};

function toTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function parsePayload(body: UsageTrackPayload) {
  const page = toTrimmedString(body.page);
  const action = toTrimmedString(body.action) || "view";
  const timestamp = toTrimmedString(body.timestamp);

  if (!page) {
    throw new Error("page is required");
  }

  return {
    scope: "usage-stats",
    page,
    action,
    ...(timestamp ? { timestamp } : {}),
  };
}

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as UsageTrackPayload;
    const args = parsePayload(body);
    const mcpContext = extractContextFromRequest(req);
    const result = await callMCPTool("set-config", args, mcpContext);

    if (result.isError) {
      return NextResponse.json(
        {
          error: MCPBridge.extractText(result) || "Failed to track page usage",
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
      error instanceof Error ? error.message : "Invalid usage tracking request";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
