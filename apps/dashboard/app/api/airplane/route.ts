import { NextResponse } from "next/server";
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_ACTIONS = new Set(["on", "off", "toggle"] as const);

type AirplaneAction = "on" | "off" | "toggle";

function parseAction(body: unknown): AirplaneAction {
  const action =
    body && typeof body === "object" && !Array.isArray(body)
      ? (body as { action?: unknown }).action
      : undefined;

  if (
    typeof action !== "string" ||
    !ALLOWED_ACTIONS.has(action as AirplaneAction)
  ) {
    throw new Error("action must be one of: on, off, toggle");
  }

  return action as AirplaneAction;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export async function POST(req: Request): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  let action: AirplaneAction;
  try {
    action = parseAction(body);
  } catch (error) {
    return NextResponse.json(
      { error: errorMessage(error, "Invalid airplane request") },
      { status: 400 },
    );
  }

  let result: Awaited<ReturnType<typeof callMCPTool>>;
  try {
    const mcpContext = extractContextFromRequest(req);
    result = await callMCPTool(
      "toggle-airplane-mode",
      { action },
      mcpContext,
    );
  } catch (error) {
    return NextResponse.json(
      { error: errorMessage(error, "failed to toggle airplane mode") },
      { status: 500 },
    );
  }

  if (result.isError) {
    return NextResponse.json(
      {
        error:
          MCPBridge.extractText(result) || "failed to toggle airplane mode",
      },
      { status: 500 },
    );
  }

  const raw = MCPBridge.extractText(result).trim();
  if (!raw) {
    return NextResponse.json({});
  }

  try {
    return NextResponse.json(JSON.parse(raw));
  } catch {
    return NextResponse.json({ raw });
  }
}
