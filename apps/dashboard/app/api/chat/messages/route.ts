import path from "path";
import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";
import { AUGUR_STATE_DIR } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function sessionPath(sessionId: string) {
  return path.join(AUGUR_STATE_DIR, "chat", `${sessionId}.jsonl`);
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get("sessionId");

  if (!sessionId) {
    return NextResponse.json(
      { error: "sessionId query parameter is required" },
      { status: 400 },
    );
  }

  try {
    const result = await callMCPTool("file-read", { path: sessionPath(sessionId) });
    if (result.isError) {
      return NextResponse.json({ messages: [] });
    }

    const raw = MCPBridge.extractText(result).trim();
    if (!raw) {
      return NextResponse.json({ messages: [] });
    }

    const parsed = JSON.parse(raw) as { content?: string } | string;
    const content =
      typeof parsed === "string" ? parsed : (parsed.content ?? "");

    if (!content.trim()) {
      return NextResponse.json({ messages: [] });
    }

    const messages = content
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line));

    return NextResponse.json({ messages });
  } catch {
    return NextResponse.json({ messages: [] });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const sessionId =
      typeof body?.sessionId === "string" ? body.sessionId : null;
    const message = body?.message;

    if (!sessionId || !message) {
      return NextResponse.json(
        { error: "sessionId and message are required" },
        { status: 400 },
      );
    }

    const result = await callMCPTool("file-write", {
      path: sessionPath(sessionId),
      content: `${JSON.stringify(message)}\n`,
      append: true,
      create_dirs: true,
    });

    if (result.isError) {
      return NextResponse.json(
        { error: MCPBridge.extractText(result) || "Failed to persist message" },
        { status: 500 },
      );
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to persist message";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
