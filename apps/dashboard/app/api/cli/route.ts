/**
 * ADR-266 EXEMPTION: PTY terminal streaming route
 *
 * This route spawns and manages interactive PTY processes (Claude Code, Codex, etc.)
 * for the dashboard's terminal pane. It uses node-pty for real terminal emulation
 * and SSE for streaming output to the browser.
 *
 * This CANNOT be replaced by createAPIRoute because:
 * 1. It manages long-lived PTY processes with bidirectional I/O
 * 2. It streams raw terminal data via SSE (not request-response)
 * 3. It requires node-pty native addon for real terminal emulation
 *
 * ADR-457: PTY management stays in-route; MCP extraction deferred.
 *
 * Sub-modules (extracted for maintainability):
 * - pty-setup.ts:   node-pty initialization, process registry, buffer helpers
 * - cli-config.ts:  CLI agent config, env setup, command resolution, session files
 * - actions.ts:     POST action handlers (start, send, sendRaw, resize, stop, system)
 * - stream.ts:      GET SSE streaming handler
 */

import { NextRequest, NextResponse } from "next/server";
import { validateCliId, CLI_ACTION_HANDLERS } from "./actions";
import { handleGetCli } from "./stream";
import type { CliRequestBody } from "./cli-config";

// Force dynamic rendering — never cache this route (SSE streaming requires it)
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * POST /api/cli - Manage CLI processes
 * Body: { action: 'start' | 'send' | 'sendRaw' | 'stop' | 'resize', cliId: string, input?: string, data?: string, cols?: number, rows?: number }
 */
export async function POST(request: NextRequest) {
  // SECURITY: Block CLI PTY for remote users (ADR-151)
  // PTY spawns a real shell on the server — remote code execution surface.
  // Remote users should use their local Claude Desktop + MCP connection instead.
  const isRemote = request.headers.get("x-remote-user") === "true";
  if (isRemote) {
    return NextResponse.json(
      {
        error:
          "CLI terminal is not available for remote access. Use your local Claude Desktop with MCP connection instead.",
        code: "REMOTE_BLOCKED",
        guidance:
          "Connect Claude Desktop to this server via MCP (streamable-http). See config/remote/README.md for setup.",
      },
      { status: 403 },
    );
  }

  try {
    const body = (await request.json()) as CliRequestBody;
    const cliValidation = validateCliId(body.cliId);
    if (!cliValidation.ok) {
      return cliValidation.response;
    }

    const handler = CLI_ACTION_HANDLERS[body.action || ""];
    if (!handler) {
      return NextResponse.json(
        { error: `Unknown action: ${body.action}` },
        { status: 400 },
      );
    }

    return await handler(cliValidation.cliId, body);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Internal error";
    console.error("CLI API error:", error);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

/**
 * GET /api/cli?cliId=xxx - Get CLI process status
 * GET /api/cli?cliId=xxx&stream=true - SSE output stream (cleaned text)
 * GET /api/cli?cliId=xxx&stream=true&format=raw - SSE output stream (raw PTY data, base64-encoded)
 */
export async function GET(request: NextRequest) {
  return handleGetCli(request);
}
