// eslint-disable-next-line no-restricted-imports -- @fs-exempt: terminal handoff payload and launcher validation are local runtime state for an explicit user action.
import { existsSync, mkdirSync, writeFileSync } from "fs";
import path from "path";
import { NextRequest, NextResponse } from "next/server";

import {
  airplaneUnavailablePayload,
  readAirplaneLaunchOverrides,
  readCanonicalAirplaneMode,
} from "@/app/api/cli/airplane-routing";
import { getSessionManager } from "@/lib/session/SessionManager";
import { AUGUR_ROOT, AUGUR_STATE_DIR } from "@/lib/paths";
import { launchNativeTerminal } from "@/lib/server/nativeTerminal";
import {
  getSessionOwner,
  isSameDashboardOwner,
  sessionOwnerConflictPayload,
} from "@/lib/session/sessionOwners";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type SupportedCliId = "claude" | "codex" | "gemini";
type HandoffShortcut = "ca" | "xa" | "ga";

const SHORTCUT_BY_CLI: Record<SupportedCliId, HandoffShortcut> = {
  claude: "ca",
  codex: "xa",
  gemini: "ga",
};

interface OpenTerminalRequestBody {
  currentPage?: unknown;
  dashboardMode?: unknown;
  themeMode?: unknown;
}

function supportedCli(cliId: string): SupportedCliId | null {
  return cliId === "claude" || cliId === "codex" || cliId === "gemini"
    ? cliId
    : null;
}

function safeName(value: string): string {
  return value.replace(/[^a-zA-Z0-9_.-]+/g, "-");
}

function nonEmptyString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : fallback;
}

function themeModeFromBody(
  value: unknown,
  fallback: "light" | "dark" | undefined,
): "light" | "dark" {
  return value === "light" || value === "dark" ? value : fallback ?? "dark";
}

function validLaunchArgv(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((entry) => typeof entry === "string" && entry.length > 0)
  );
}

function buildHandoffPrompt({
  currentPage,
  dashboardMode,
}: {
  currentPage: string;
  dashboardMode: string;
}): string {
  return [
    "Exited dashboard chat. Continue in this native terminal.",
    `Page: ${currentPage}.`,
    `Dashboard mode: ${dashboardMode}.`,
    "Acknowledge briefly that the terminal handoff is ready, then wait for the user's next request.",
  ].join(" ");
}

function writePayload(payload: Record<string, unknown>): string {
  const dir = path.join(AUGUR_STATE_DIR, "terminal-handoffs");
  mkdirSync(dir, { recursive: true });
  const file = path.join(
    dir,
    `handoff-${safeName(String(payload.cli_id))}-${safeName(
      String(payload.session_id),
    )}-${Date.now()}.json`,
  );
  writeFileSync(file, JSON.stringify(payload, null, 2), "utf8");
  return file;
}

function launcherForShortcut(shortcut: HandoffShortcut): string {
  const extension = process.platform === "win32" ? "ps1" : "sh";
  const launcher = path.join(AUGUR_ROOT, "scripts", `${shortcut}-launch.${extension}`);
  if (!existsSync(launcher)) {
    throw new Error(`Missing terminal handoff launcher: ${launcher}`);
  }
  return launcher;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Native terminal handoff failed.";
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

  const body = (await request.json().catch(() => ({}))) as OpenTerminalRequestBody;
  const manager = getSessionManager();
  const snapshot = manager.getTerminalHandoffSnapshot();
  if (!snapshot) {
    return NextResponse.json(
      {
        error: "No active resumable CLI session is available for terminal handoff.",
        code: "NO_RESUMABLE_SESSION",
      },
      { status: 409 },
    );
  }

  const cliId = supportedCli(snapshot.cliId);
  if (!cliId) {
    return NextResponse.json(
      {
        error: `Terminal handoff is not configured for ${snapshot.cliId}.`,
        code: "UNSUPPORTED_CLIENT",
      },
      { status: 400 },
    );
  }

  const owner = await getSessionOwner(snapshot.sessionId);
  if (owner && !isSameDashboardOwner(owner, snapshot.pid)) {
    return NextResponse.json(
      sessionOwnerConflictPayload(snapshot.sessionId, owner),
      { status: 409 },
    );
  }

  const shortcut = SHORTCUT_BY_CLI[cliId];
  const canonicalAirplaneMode = await readCanonicalAirplaneMode();
  const airplaneMode = snapshot.airplaneMode === true || canonicalAirplaneMode;
  let launchArgv: string[] | undefined;
  if (airplaneMode) {
    const overrides = await readAirplaneLaunchOverrides(cliId);
    if (overrides.ready !== true) {
      return NextResponse.json(airplaneUnavailablePayload(overrides), {
        status: 409,
      });
    }
    if (!validLaunchArgv(overrides.launch_argv)) {
      return NextResponse.json(
        {
          error: "Airplane launch override is not ready",
          reason: "missing_launch_argv",
          setup_hint: "Check local backend setup and try again.",
        },
        { status: 409 },
      );
    }
    launchArgv = overrides.launch_argv;
  }

  let launcher: string;
  try {
    launcher = launcherForShortcut(shortcut);
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: errorMessage(error),
        code: "TERMINAL_LAUNCH_FAILED",
      },
      { status: 500 },
    );
  }

  const exitResult = await manager.exitForTerminalHandoff();
  if (!exitResult.ok) {
    return NextResponse.json(
      {
        error: "Embedded chat did not exit cleanly; native terminal was not opened.",
        code:
          exitResult.reason === "exit_timeout"
            ? "EXIT_TIMEOUT"
            : "NO_RUNNING_SESSION",
      },
      { status: 409 },
    );
  }

  const currentPage = nonEmptyString(body.currentPage, "dashboard");
  const dashboardMode = nonEmptyString(body.dashboardMode, "development");
  const themeMode = themeModeFromBody(body.themeMode, snapshot.themeMode);
  const handoffPrompt = buildHandoffPrompt({ currentPage, dashboardMode });

  const payload = {
    version: 1,
    created_at: new Date().toISOString(),
    cli_id: cliId,
    shortcut,
    session_id: snapshot.sessionId,
    cwd: snapshot.cwd,
    current_page: currentPage,
    dashboard_mode: dashboardMode,
    theme_mode: themeMode,
    handoff_prompt: handoffPrompt,
    route: {
      airplane_mode: airplaneMode,
      local_model: airplaneMode ? snapshot.airplaneLocalModel : null,
      ...(airplaneMode ? { launch_argv: launchArgv } : {}),
    },
  };

  try {
    const payloadFile = writePayload(payload);
    const launch = await launchNativeTerminal({
      cwd: snapshot.cwd,
      argv: [launcher, "--handoff-file", payloadFile],
    });

    return NextResponse.json({
      ok: true,
      cliId,
      shortcut,
      launcher,
      pid: snapshot.pid,
      payloadFile,
      launch,
    });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: errorMessage(error),
        code: "TERMINAL_LAUNCH_FAILED",
      },
      { status: 500 },
    );
  }
}
