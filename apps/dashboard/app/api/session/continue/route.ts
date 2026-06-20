import { NextRequest, NextResponse } from "next/server";
import { getSessionManager } from "@/lib/session/SessionManager";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface ContinueSessionRequestBody {
  sessionId?: unknown;
  answer?: unknown;
  force?: unknown;
}

function readNonEmptyString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export async function POST(request: NextRequest) {
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

  let body: ContinueSessionRequestBody;

  try {
    body = (await request.json()) as ContinueSessionRequestBody;
  } catch {
    return NextResponse.json(
      { error: "Request body must be valid JSON." },
      { status: 400 },
    );
  }

  const sessionId = readNonEmptyString(body.sessionId);
  const answer = typeof body.answer === "string" ? body.answer : null;
  const force = body.force === true;
  const sessionManager = getSessionManager();

  try {
    const hasActiveConversation = sessionManager.hasActiveConversation();
    if (hasActiveConversation && !force) {
      return NextResponse.json(
        { collision: true, message: "Session already active" },
        { status: 409 },
      );
    }

    const shouldResumeRequestedSession =
      sessionId !== null && sessionId !== sessionManager.getLastSessionId();
    const shouldReplaceActiveConversation = force && hasActiveConversation;

    if (shouldReplaceActiveConversation) {
      sessionManager.terminateActiveConversations();
    }

    if (shouldResumeRequestedSession) {
      sessionManager.terminate();
      if (sessionId) {
        sessionManager.saveSessionId(sessionId);
      }
    }

    if (!sessionManager.isRunning()) {
      if (
        sessionId &&
        !shouldResumeRequestedSession &&
        !shouldReplaceActiveConversation
      ) {
        sessionManager.saveSessionId(sessionId);
      }

      await sessionManager.initialize();
    }

    if (answer !== null && answer.length > 0) {
      sessionManager.sendMessage(
        `Previous result:\n${answer}\n\nContinue from here.`,
      );
    }

    return NextResponse.json({
      ok: true,
      cliId: sessionManager.getCliId(),
      pid: sessionManager.getPid(),
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to continue session.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
