/**
 * POST /api/blocks/data
 *
 * Generic MCP tool proxy for block data fetching.
 * Accepts { tool: string, args?: Record<string, unknown> }
 * and calls the named MCP tool, returning its result.
 *
 * Used by useBlockData hook in all block components.
 */

import { NextResponse } from "next/server";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request): Promise<Response> {
  let body: { tool?: string; args?: Record<string, unknown> };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body", success: false },
      { status: 400 },
    );
  }

  const { tool, args } = body;
  if (!tool || typeof tool !== "string") {
    return NextResponse.json(
      { error: "Missing required field: tool", success: false },
      { status: 400 },
    );
  }

  try {
    const result = await callMCPTool(tool, args || {});

    if (result.isError) {
      const errorText = MCPBridge.extractText(result);
      console.error(`[blocks/data] MCP tool "${tool}" error:`, errorText);
      return NextResponse.json(
        { error: errorText || "Tool execution failed", success: false },
        { status: 500 },
      );
    }

    const data = MCPBridge.parseJSON(result);
    return NextResponse.json({ success: true, data });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[blocks/data] Error calling tool "${tool}":`, message);
    return NextResponse.json(
      { error: message, success: false },
      { status: 500 },
    );
  }
}
