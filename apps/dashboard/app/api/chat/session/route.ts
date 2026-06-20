import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await callMCPTool("get-chat-session", {});
    if (result.isError) {
      return NextResponse.json({
        session: null,
        isActive: false,
        mode: "idle",
        status: "no_session",
        message: "No active chat session",
      });
    }

    const raw = MCPBridge.extractText(result).trim();
    if (!raw) {
      return NextResponse.json({
        session: null,
        isActive: false,
        mode: "idle",
        status: "no_session",
        message: "No active chat session",
      });
    }

    return NextResponse.json(JSON.parse(raw));
  } catch {
    return NextResponse.json({
      session: null,
      isActive: false,
      mode: "idle",
      status: "no_session",
      message: "No active chat session",
    });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const args: Record<string, unknown> = {};

    if ("isActive" in body) args.is_active = body.isActive;
    if ("mode" in body) args.mode = body.mode;
    if ("status" in body) args.status = body.status;
    if ("actionId" in body) args.action_id = body.actionId;
    if ("context" in body) args.context = JSON.stringify(body.context);

    const result = await callMCPTool("update-chat-session", args);
    if (result.isError) {
      return NextResponse.json(
        {
          success: true,
          message: "Session update acknowledged (fallback mode)",
        },
        { status: 200 },
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
      error instanceof Error ? error.message : "Failed to update chat session";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
