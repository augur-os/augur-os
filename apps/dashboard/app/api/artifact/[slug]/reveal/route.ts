import { NextResponse } from "next/server";
import { MCPBridge } from "@/lib/mcp/connection";
import { callCoreTool, callMCPTool } from "@/lib/mcp/helpers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;

  // Resolve the artifact server-side so the FS path never leaves the server
  const res = await callCoreTool("artifact-resolve", { slug });
  const data = MCPBridge.parseJSON<{ found?: boolean; path?: string }>(res);

  if (!data.found || !data.path) {
    return NextResponse.json({ found: false }, { status: 404 });
  }

  try {
    await callMCPTool("reveal-in-finder", { path: data.path });
    return NextResponse.json({ ok: true });
  } catch (error) {
    // Log the detailed error server-side only; never send FS paths to the client.
    console.error("[reveal] reveal-in-finder failed:", error);
    return NextResponse.json({ ok: false, error: "Reveal failed" }, { status: 500 });
  }
}
