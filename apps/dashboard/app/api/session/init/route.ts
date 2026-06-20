import { NextRequest, NextResponse } from "next/server";

import {
  getSessionManager,
  type SessionInitializeOptions,
} from "@/lib/session/SessionManager";
import {
  isSessionOwnerConflictError,
  sessionOwnerConflictPayload,
} from "@/lib/session/sessionOwners";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface SessionInitRequestBody {
  airplaneMode?: unknown;
  airplaneLocalModel?: unknown;
  currentPage?: unknown;
  themeMode?: unknown;
}

function readBodyOption(body: SessionInitRequestBody): SessionInitializeOptions {
  const themeMode = body.themeMode === "light" ? "light" : "dark";
  return {
    airplaneMode: body.airplaneMode === true,
    airplaneLocalModel:
      typeof body.airplaneLocalModel === "string" &&
      body.airplaneLocalModel.trim().length > 0
        ? body.airplaneLocalModel.trim()
        : null,
    currentPage:
      typeof body.currentPage === "string" && body.currentPage.length > 0
        ? body.currentPage
        : undefined,
    themeMode,
  };
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (request.headers.get("x-remote-user") === "true") {
    return NextResponse.json(
      {
        error:
          "CLI terminal is not available for remote access. Use your local Claude Desktop with MCP connection instead.",
        code: "REMOTE_BLOCKED",
      },
      { status: 403 },
    );
  }

  let body: SessionInitRequestBody = {};
  try {
    body = (await request.json()) as SessionInitRequestBody;
  } catch {
    body = {};
  }

  try {
    const manager = getSessionManager();
    const options = readBodyOption(body);
    if (
      manager.isRunning() &&
      !(await manager.shouldRestartForOptions(options))
    ) {
      return NextResponse.json({
        ok: true,
        alreadyRunning: true,
        cliId: manager.getCliId(),
        pid: manager.getPid(),
        lastSessionId: manager.getLastSessionId(),
      });
    }

    const restarted = manager.isRunning();
    if (restarted) {
      manager.terminate();
    }
    await manager.initialize(options);
    return NextResponse.json({
      ok: true,
      alreadyRunning: false,
      restarted,
      cliId: manager.getCliId(),
      pid: manager.getPid(),
      lastSessionId: manager.getLastSessionId(),
    });
  } catch (error) {
    if (isSessionOwnerConflictError(error)) {
      return NextResponse.json(
        sessionOwnerConflictPayload(error.sessionId, error.owner),
        { status: 409 },
      );
    }
    const message = error instanceof Error ? error.message : "init failed";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
