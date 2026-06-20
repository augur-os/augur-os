import { NextResponse } from "next/server";
import { MCPBridge } from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const bridge = MCPBridge.getInstance();
  const state = {
    ...bridge.getDebugState(),
    cwd: process.cwd(),
    env_AUGUR_ROOT: process.env.AUGUR_ROOT,
    env_PYTHONPATH: process.env.PYTHONPATH,
  };

  return NextResponse.json(state);
}
