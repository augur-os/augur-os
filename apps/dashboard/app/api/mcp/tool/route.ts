import { NextResponse } from "next/server";
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";
import { pluginForTool } from "@/lib/mcp/pluginFallback";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type ToolRequestBody = {
  tool?: unknown;
  args?: unknown;
  params?: unknown;
};

class BadRequestError extends Error {}

function statusForError(error: unknown): number {
  if (error instanceof BadRequestError) return 400;
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (/timed out after \d+ms/i.test(message)) return 504;
  if (/MCP server (not connected|disconnected)/i.test(message)) return 502;
  return 500;
}

function pluginFallbackResponse(tool: string, errorText: string) {
  const plugin = pluginForTool(tool);
  if (!plugin) return null;
  if (!/unknown tool|not found|not installed|unavailable/i.test(errorText)) {
    return null;
  }
  return NextResponse.json({
    _fallback: true,
    _plugin: plugin,
    _reason: "plugin_tool_unavailable",
    _error: errorText || `MCP tool unavailable: ${tool}`,
  });
}

type McpToolResult = Awaited<ReturnType<typeof callMCPTool>>;
type McpContext = ReturnType<typeof extractContextFromRequest>;

async function retryStaleCoreTool(
  tool: string,
  args: Record<string, unknown>,
  context: McpContext,
  result: McpToolResult,
): Promise<McpToolResult> {
  if (!result.isError) return result;

  const errorText = MCPBridge.extractText(result);
  if (!/unknown tool/i.test(errorText) || pluginForTool(tool)) {
    return result;
  }

  const bridge = MCPBridge.getInstance();
  await bridge.reconnect();
  return callMCPTool(tool, args, context);
}

function parseBody(body: ToolRequestBody): {
  tool: string;
  args: Record<string, unknown>;
} {
  if (!body || typeof body.tool !== "string" || body.tool.trim().length === 0) {
    throw new BadRequestError("`tool` must be a non-empty string");
  }
  const args = body.args ?? body.params;
  if (args == null) {
    return { tool: body.tool.trim(), args: {} };
  }
  if (typeof args !== "object" || Array.isArray(args)) {
    throw new BadRequestError("`args` must be an object");
  }
  return { tool: body.tool.trim(), args: args as Record<string, unknown> };
}

export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const tool = url.searchParams.get("tool");
    if (!tool || tool.trim().length === 0) {
      return NextResponse.json(
        { error: "`tool` query parameter is required" },
        { status: 400 },
      );
    }

    const args: Record<string, string> = {};
    for (const [key, value] of url.searchParams.entries()) {
      if (key !== "tool") args[key] = value;
    }

    const mcpContext = extractContextFromRequest(req);
    const cleanTool = tool.trim();
    let result = await callMCPTool(cleanTool, args, mcpContext);
    result = await retryStaleCoreTool(cleanTool, args, mcpContext, result);

    if (result.isError) {
      const errorText = MCPBridge.extractText(result) || `MCP tool failed: ${tool}`;
      const fallback = pluginFallbackResponse(cleanTool, errorText);
      if (fallback) return fallback;
      return NextResponse.json(
        { error: errorText },
        { status: 500 },
      );
    }

    const raw = MCPBridge.extractText(result).trim();
    if (!raw) return NextResponse.json({});

    try {
      return NextResponse.json(JSON.parse(raw));
    } catch {
      return NextResponse.json({ result: raw });
    }
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to call MCP tool";
    return NextResponse.json({ error: message }, { status: statusForError(error) });
  }
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as ToolRequestBody;
    const { tool, args } = parseBody(body);
    const mcpContext = extractContextFromRequest(req);
    let result = await callMCPTool(tool, args, mcpContext);

    if (result.isError) {
      const errorText = MCPBridge.extractText(result);
      const missingParamsEnvelope =
        /\bparams\b[\s\S]*Field required/i.test(errorText);

      if (
        missingParamsEnvelope &&
        args &&
        typeof args === "object" &&
        !Array.isArray(args) &&
        !("params" in args)
      ) {
        result = await callMCPTool(tool, { params: args }, mcpContext);
      }
    }

    result = await retryStaleCoreTool(tool, args, mcpContext, result);

    if (result.isError) {
      const errorText = MCPBridge.extractText(result) || `MCP tool failed: ${tool}`;
      const fallback = pluginFallbackResponse(tool, errorText);
      if (fallback) return fallback;
      return NextResponse.json(
        { error: errorText },
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
      return NextResponse.json({ result: raw });
    }
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to call MCP tool";
    return NextResponse.json({ error: message }, { status: statusForError(error) });
  }
}
