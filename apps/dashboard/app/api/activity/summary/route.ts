import { NextResponse } from "next/server";
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    const mcpContext = extractContextFromRequest(req);
    const result = await callMCPTool(
      "get-settings",
      { scope: "activity-summary" },
      mcpContext,
    );

    if (result.isError) {
      return NextResponse.json(
        {
          error:
            MCPBridge.extractText(result) || "Failed to load activity summary",
        },
        { status: 500 },
      );
    }

    const raw = MCPBridge.extractText(result).trim();
    if (!raw) {
      return NextResponse.json({
        focus: null,
        workflows: [],
        assets: [],
        pages: [],
        dev: { branch: "", last_commit: "", commit_time: "" },
      });
    }

    try {
      return NextResponse.json(JSON.parse(raw));
    } catch {
      return NextResponse.json(
        { error: "Invalid MCP activity summary response" },
        { status: 500 },
      );
    }
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to load activity summary";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
