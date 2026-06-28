/**
 * CLI Route — POST Action Handlers
 *
 * Handles start, send, sendRaw, resize, stop, and system actions
 * for managing PTY processes via the POST /api/cli endpoint.
 *
 * Extracted from route.ts to isolate action dispatch from SSE
 * streaming and route-level boilerplate.
 */

import { NextResponse } from "next/server";
import path from "path";
import { randomUUID } from "crypto";
import {
  buildPromptFromEnvelope,
  BUDGET_STANDARD,
} from "@/lib/chat/context-envelope";
import { buildStartupPrompt } from "@/lib/chat/startup-context";
import {
  type IPtyProcess,
  pty,
  PTY_SPAWN_HELPER,
  ptyHealthy,
  setPtyHealthy,
  processes,
  type PtyEntry,
  createPtyEntry,
  attachPtyHandlers,
  detachSession,
} from "./pty-setup";
import {
  AUGUR_ROOT,
  extractOllamaRunModel,
  isNonEmptyString,
  isValidCli,
  isDirectOllamaCli,
  resolveConfigKey,
  getCliConfigOrThrow,
  buildCliSpawnEnv,
  resolveSpawnCommand,
  writeChatSession,
  type CliRequestBody,
} from "./cli-config";
import {
  type AirplaneLaunchOverrides,
  airplaneUnavailablePayload,
  applyAirplaneLaunchOverride,
  readAirplaneLaunchOverrides,
  readCanonicalAirplaneMode,
} from "./airplane-routing";
import { getSessionManager } from "@/lib/session/SessionManager";
import {
  claimDashboardSessionOwner,
  isSessionOwnerConflictError,
  releaseDashboardSessionOwner,
  releaseSessionOwner,
  sessionOwnerConflictPayload,
} from "@/lib/session/sessionOwners";

// ============================================================================
// Validation Helpers
// ============================================================================

type RunningEntryResult =
  | { ok: true; entry: PtyEntry }
  | { ok: false; response: NextResponse };

interface StartCliProcessResult {
  pid: number;
  ptyProcess: IPtyProcess;
  sessionId: string | null;
  clearSessionId: boolean;
  reused: boolean;
  directLocalModel: string | null;
}

const CODEX_LATEST_SESSION_ID = "__codex_latest__";

function getRunningEntry(cliId: string): RunningEntryResult {
  const entry = processes.get(cliId);
  if (!entry || entry.exited) {
    return {
      ok: false,
      response: NextResponse.json(
        { error: `CLI '${cliId}' is not running` },
        { status: 409 },
      ),
    };
  }
  return { ok: true, entry };
}

export function validateCliId(
  cliId: unknown,
): { ok: true; cliId: string } | { ok: false; response: NextResponse } {
  if (!isNonEmptyString(cliId)) {
    return {
      ok: false,
      response: NextResponse.json(
        { error: "Missing or invalid cliId" },
        { status: 400 },
      ),
    };
  }
  if (!isValidCli(cliId)) {
    return {
      ok: false,
      response: NextResponse.json(
        { error: `Unknown CLI: ${cliId}` },
        { status: 400 },
      ),
    };
  }
  return { ok: true, cliId };
}

// ============================================================================
// PTY Spawn
// ============================================================================

function buildSpawnCommand(
  cmd: string[],
  airplaneOverrides?: AirplaneLaunchOverrides,
): { resolvedCmd: string; args: string[] } {
  const spawnArgv = applyAirplaneLaunchOverride(
    cmd[0],
    cmd.slice(1),
    airplaneOverrides,
  );
  return {
    resolvedCmd: resolveSpawnCommand(spawnArgv.command),
    args: spawnArgv.args,
  };
}

function supportsExplicitSessionId(cliId: string, cmd: string[]): boolean {
  const binary = path.basename(cmd[0] || "");
  return (
    cliId === "claude" ||
    cliId.startsWith("claude-") ||
    binary === "claude"
  );
}

function isCodexCli(cliId: string, cmd: string[]): boolean {
  return cliId === "codex" || path.basename(cmd[0] || "") === "codex";
}

export function cmdWithResumableSessionId(
  cliId: string,
  cmd: string[],
  resumeSessionId?: string | null,
): { cmd: string[]; sessionId: string | null } {
  if (cliId.startsWith("agent-bubble-") || !supportsExplicitSessionId(cliId, cmd)) {
    if (!cliId.startsWith("agent-bubble-") && isCodexCli(cliId, cmd)) {
      return { cmd, sessionId: CODEX_LATEST_SESSION_ID };
    }
    return { cmd, sessionId: null };
  }

  const existingFlagIndex = cmd.indexOf("--session-id");
  if (existingFlagIndex >= 0) {
    const existingSessionId = cmd[existingFlagIndex + 1];
    return {
      cmd,
      sessionId:
        typeof existingSessionId === "string" && existingSessionId.length > 0
          ? existingSessionId
          : null,
    };
  }

  // Claude exits immediately when --resume points at an id whose backing
  // session file is missing. The dashboard can mint a new explicit id for
  // ownership, but persisted ids are not proof that the native CLI can resume.
  const sessionId = randomUUID();
  return { cmd: [...cmd, "--session-id", sessionId], sessionId };
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function extractAirplaneLocalModel(
  overrides: AirplaneLaunchOverrides | undefined,
): string | null {
  const launchArgv = overrides?.launch_argv;
  if (!Array.isArray(launchArgv)) {
    return null;
  }
  const modelFlagIndex = launchArgv.findIndex((arg) => arg === "--model");
  const model =
    modelFlagIndex >= 0 ? launchArgv[modelFlagIndex + 1] : undefined;
  return typeof model === "string" && model.trim().length > 0
    ? model.trim()
    : null;
}

function spawnPtyOrThrow(
  cliId: string,
  resolvedCmd: string,
  args: string[],
  cwd: string,
  env: Record<string, string>,
): IPtyProcess {
  try {
    // boundary-ignore: spawn\(
    // @spawn-exempt: interactive CLI/PTY terminal session — a live bidirectional
    // terminal cannot be a request/response MCP tool. See ADR-817.
    return pty.spawn(resolvedCmd, args, {
      name: "xterm-256color",
      cols: 120,
      rows: 40,
      cwd,
      env,
    });
  } catch (spawnErr: unknown) {
    setPtyHealthy(false);
    const msg = spawnErr instanceof Error ? spawnErr.message : String(spawnErr);
    console.error(
      `[CLI] pty.spawn failed for '${cliId}':\n` +
        `  command: ${resolvedCmd}\n` +
        `  args: ${JSON.stringify(args)}\n` +
        `  cwd: ${cwd}\n` +
        `  spawn-helper: ${PTY_SPAWN_HELPER.path} (exists: ${PTY_SPAWN_HELPER.exists})\n` +
        `  error: ${msg}`,
    );
    throw new Error(
      `Failed to spawn PTY for '${cliId}' (${resolvedCmd}): ${msg}. ` +
        `spawn-helper: ${PTY_SPAWN_HELPER.exists}, pty-healthy: ${ptyHealthy}. ` +
        `Try restarting the dev server (npm run dev).`,
    );
  }
}

function startCliProcess(
  cliId: string,
  currentPage?: string,
  themeMode?: "light" | "dark",
  airplaneOverrides?: AirplaneLaunchOverrides,
  resumeSessionId?: string | null,
): StartCliProcessResult {
  // ADR-160: Agent bubble IDs resolve to 'claude' config
  const configKey = resolveConfigKey(cliId);
  const config = getCliConfigOrThrow(configKey);
  const directLocalModel = isDirectOllamaCli(cliId)
    ? extractOllamaRunModel(config.cmd)
    : null;

  const existing = processes.get(cliId);
  if (existing && !existing.exited) {
    return {
      pid: existing.ptyProcess.pid,
      ptyProcess: existing.ptyProcess,
      sessionId: null,
      clearSessionId: false,
      reused: true,
      directLocalModel,
    };
  }
  if (existing) {
    processes.delete(cliId);
  }

  const launch = cmdWithResumableSessionId(
    cliId,
    [...(config.cmd as string[])],
    resumeSessionId,
  );
  const cmd = launch.cmd;

  // Agent bubbles run in interactive mode with post-startup prompt injection.
  // Print mode (-p) with stream-json doesn't render through PTY/xterm reliably.

  const cwd = config.cwd === "." ? AUGUR_ROOT : config.cwd || AUGUR_ROOT;
  const env = buildCliSpawnEnv(config, currentPage, themeMode);
  const { resolvedCmd, args } = buildSpawnCommand(cmd, airplaneOverrides);
  const ptyProcess = spawnPtyOrThrow(
    cliId,
    resolvedCmd,
    args,
    cwd,
    env,
  );

  // Mark PTY as healthy after first successful spawn
  if (ptyHealthy === null) setPtyHealthy(true);

  const entry = createPtyEntry(ptyProcess);
  attachPtyHandlers(entry);
  processes.set(cliId, entry);

  return {
    pid: ptyProcess.pid,
    ptyProcess,
    sessionId: launch.sessionId,
    clearSessionId: launch.sessionId === null,
    reused: false,
    directLocalModel,
  };
}

function cleanupStartedProcess(cliId: string, ptyProcess: IPtyProcess): void {
  const entry = processes.get(cliId);
  if (entry?.ptyProcess === ptyProcess) {
    stopCliProcess(entry);
    processes.delete(cliId);
    return;
  }

  try {
    ptyProcess.kill();
  } catch {
    // Best-effort cleanup for a duplicate PTY that failed ownership claim.
  }
}

// ============================================================================
// Action Handlers
// ============================================================================

async function handleStartAction(
  cliId: string,
  body: CliRequestBody,
): Promise<NextResponse> {
  const currentPage = body.current_page;
  const themeMode = body.themeMode === "light" ? "light" : "dark";
  const autoContext = body.autoContext === true;
  let wroteSession = false;
  let airplaneMode = false;
  let airplaneOverrides: AirplaneLaunchOverrides | undefined;

  try {
    airplaneMode = await readCanonicalAirplaneMode();
  } catch (err) {
    return NextResponse.json(
      {
        error: "Failed to read canonical airplane mode status",
        reason: errorMessage(err),
      },
      { status: 500 },
    );
  }

  const directOllama = isDirectOllamaCli(cliId);

  if (airplaneMode && !directOllama) {
    try {
      airplaneOverrides = await readAirplaneLaunchOverrides(cliId);
    } catch (err) {
      return NextResponse.json(
        {
          error: "Failed to read airplane launch overrides",
          reason: errorMessage(err),
        },
        { status: 500 },
      );
    }

    if (airplaneOverrides.ready !== true) {
      const payload = airplaneUnavailablePayload(airplaneOverrides);
      return NextResponse.json(
        payload,
        { status: 409 },
      );
    }
  }

  // ADR-160: Skip session file write for agent bubbles — they use print mode
  // and don't need the session protocol context (which would pollute the main chat session).
  if (currentPage && !cliId.startsWith("agent-bubble-")) {
    // ADR-161: Write enriched session data from envelope if available
    const sessionContext: Record<string, unknown> = {
      current_page: currentPage,
      cliId,
      airplaneMode,
    };
    if (body.envelope) {
      if (body.envelope.hub) sessionContext.hub = body.envelope.hub;
      if (body.envelope.skill) sessionContext.skill = body.envelope.skill;
      if (body.envelope.skillTools?.length)
        sessionContext.skillTools = body.envelope.skillTools;
      if (body.envelope.skillActions?.length)
        sessionContext.skillActions = body.envelope.skillActions;
    }
    writeChatSession({
      isActive: true,
      status: "running",
      context: sessionContext,
    });
    wroteSession = true;
  }

  try {
    // Resume the current conversation on (re)start so switching backends —
    // e.g. toggling airplane mode and restarting the chat — keeps history.
    // Agent bubbles are one-shot and must never inherit the main session.
    const manager = getSessionManager();
    const resumeSessionId = cliId.startsWith("agent-bubble-")
      ? null
      : manager.getLastSessionId(cliId);
    const {
      pid,
      ptyProcess,
      sessionId,
      clearSessionId,
      reused,
      directLocalModel,
    } = startCliProcess(
      cliId,
      currentPage,
      themeMode,
      airplaneOverrides,
      resumeSessionId,
    );
    if (!cliId.startsWith("agent-bubble-")) {
      const effectiveSessionId = sessionId ?? resumeSessionId;
      if (effectiveSessionId) {
        try {
          await claimDashboardSessionOwner({
            cliId,
            pid,
            sessionId: effectiveSessionId,
          });
        } catch (err) {
          let claimRecovered = false;
          if (
            body.takeOverSessionOwner === true &&
            isSessionOwnerConflictError(err)
          ) {
            const owner = err.owner;
            const ownerSurface =
              typeof owner.surface === "string" ? owner.surface : null;
            const ownerPid =
              typeof owner.pid === "number" ? owner.pid : undefined;
            if (ownerSurface === "native-terminal") {
              try {
                await releaseSessionOwner({
                  sessionId: effectiveSessionId,
                  surface: ownerSurface,
                  pid: ownerPid,
                });
              } catch (releaseErr) {
                if (!reused) {
                  cleanupStartedProcess(cliId, ptyProcess);
                }
                if (wroteSession) {
                  writeChatSession({
                    isActive: false,
                    status: "idle",
                    context: {},
                  });
                }
                throw releaseErr;
              }

              try {
                await claimDashboardSessionOwner({
                  cliId,
                  pid,
                  sessionId: effectiveSessionId,
                });
                claimRecovered = true;
              } catch (retryErr) {
                if (!reused) {
                  cleanupStartedProcess(cliId, ptyProcess);
                }
                if (wroteSession) {
                  writeChatSession({
                    isActive: false,
                    status: "idle",
                    context: {},
                  });
                }
                if (isSessionOwnerConflictError(retryErr)) {
                  return NextResponse.json(
                    sessionOwnerConflictPayload(
                      effectiveSessionId,
                      retryErr.owner,
                    ),
                    { status: 409 },
                  );
                }
                throw retryErr;
              }
            }
          }
          if (!claimRecovered) {
            if (!reused) {
              cleanupStartedProcess(cliId, ptyProcess);
            }
            if (wroteSession) {
              writeChatSession({ isActive: false, status: "idle", context: {} });
            }
            if (isSessionOwnerConflictError(err)) {
              return NextResponse.json(
                sessionOwnerConflictPayload(effectiveSessionId, err.owner),
                { status: 409 },
              );
            }
            throw err;
          }
        }
      }
      manager.trackCliProcess({
        cliId,
        ptyProcess,
        sessionId,
        ...(sessionId === null ? { clearSessionId } : {}),
        airplaneMode,
        airplaneLocalModel: airplaneMode
          ? extractAirplaneLocalModel(airplaneOverrides) ?? directLocalModel
          : null,
        themeMode,
      });
    }

    // Inject startup context for interactive chat sessions (autoContext).
    // Agent bubble prompt injection is handled client-side (useActionRunner).
    //
    // ADR-748 follow-up: an explicit oneshotPrompt (e.g. a Browse AI-action draft
    // sent to a cold CLI) is injected server-side after startup via the same
    // calibrated write-then-Enter below, avoiding the client-side readiness race
    // that silently dropped the message. Agent bubbles inject client-side, so
    // exclude them here to avoid a double send.
    const explicitOneshot =
      typeof body.oneshotPrompt === "string" &&
      body.oneshotPrompt.trim().length > 0 &&
      !cliId.startsWith("agent-bubble-")
        ? body.oneshotPrompt
        : null;
    const injectPrompt = explicitOneshot ?? (autoContext && currentPage
        ? (body.envelope?.hub
            ? buildPromptFromEnvelope({
                sessionId: cliId,
                timestamp: Date.now(),
                page: currentPage,
                hub: body.envelope.hub,
                skill: body.envelope.skill ?? null,
                skillSummary: body.envelope.skillSummary ?? null,
                skillDataDir: null,
                skillTools: body.envelope.skillTools ?? [],
                skillActions: body.envelope.skillActions ?? [],
                action: null,
                projectIdentity: null,
                maxContextTokens: BUDGET_STANDARD,
                priority: "standard",
              })
            : buildStartupPrompt(currentPage))
        : null);


    if (injectPrompt) {
      const safePrompt = injectPrompt.replace(/\n+/g, " ").trim();
      setTimeout(() => {
        const current = processes.get(cliId);
        if (current && !current.exited) {
          current.ptyProcess.write(safePrompt);
          // Submit after the TUI settles. 100ms was too tight when the CLI is
          // still finishing startup, leaving the prompt typed-but-unsent.
          setTimeout(() => {
            if (!current.exited) {
              current.ptyProcess.write("\r");
            }
          }, 700);
        }
      }, 2000);
    }

    return NextResponse.json({
      cliId,
      status: "running",
      pid,
      current_page: currentPage,
      airplaneMode,
    });
  } catch (err) {
    if (wroteSession) {
      writeChatSession({ isActive: false, status: "idle", context: {} });
    }
    throw err;
  }
}

/**
 * ADR-157 Decision 4: System command — writes to PTY without logging to outputBuffer.
 * Used for lifecycle commands (refocus, context-save) that shouldn't appear in chat history.
 */
function handleSystemAction(cliId: string, body: CliRequestBody): NextResponse {
  if (!isNonEmptyString(body.input)) {
    return NextResponse.json({ error: "Missing input text" }, { status: 400 });
  }

  const running = getRunningEntry(cliId);
  if (!running.ok) {
    return running.response;
  }

  // Write directly to PTY — output will be buffered by normal onData handler
  // but the input itself is not logged to chat messages (that's the client's job to skip)
  running.entry.ptyProcess.write(body.input);
  setTimeout(() => {
    running.entry.ptyProcess.write("\r");
  }, 100);
  return NextResponse.json({ cliId, sent: true, system: true });
}

function handleSendAction(cliId: string, body: CliRequestBody): NextResponse {
  if (!isNonEmptyString(body.input)) {
    return NextResponse.json({ error: "Missing input text" }, { status: 400 });
  }

  const running = getRunningEntry(cliId);
  if (!running.ok) {
    return running.response;
  }

  // Write text first, then send \r (Enter) separately after a short delay.
  // Claude Code's Ink TUI treats text+\r in a single write as pasted input.
  running.entry.ptyProcess.write(body.input);
  getSessionManager().markCliActivity(cliId);
  setTimeout(() => {
    running.entry.ptyProcess.write("\r");
  }, 100);
  return NextResponse.json({ cliId, sent: true });
}

function handleSendRawAction(
  cliId: string,
  body: CliRequestBody,
): NextResponse {
  if (!isNonEmptyString(body.data)) {
    return NextResponse.json({ error: "Missing raw data" }, { status: 400 });
  }

  const running = getRunningEntry(cliId);
  if (!running.ok) {
    return running.response;
  }

  running.entry.ptyProcess.write(body.data);
  getSessionManager().markCliActivity(cliId);
  return NextResponse.json({ cliId, sent: true });
}

function handleResizeAction(cliId: string, body: CliRequestBody): NextResponse {
  if (
    typeof body.cols !== "number" ||
    typeof body.rows !== "number" ||
    body.cols <= 0 ||
    body.rows <= 0
  ) {
    return NextResponse.json(
      { error: "Missing or invalid cols/rows" },
      { status: 400 },
    );
  }

  const running = getRunningEntry(cliId);
  if (!running.ok) {
    return running.response;
  }

  running.entry.ptyProcess.resize(body.cols, body.rows);
  return NextResponse.json({
    cliId,
    resized: true,
    cols: body.cols,
    rows: body.rows,
  });
}

function stopCliProcess(entry: PtyEntry): void {
  if (entry.exited) return;

  // ADR-535 0E: Clear detach timer if set
  if (entry.detachTimer) {
    clearTimeout(entry.detachTimer);
    entry.detachTimer = null;
  }

  entry.ptyProcess.kill();
  setTimeout(() => {
    try {
      if (!entry.exited) {
        process.kill(entry.ptyProcess.pid, "SIGKILL");
      }
    } catch {
      // Process may already be dead
    }
  }, 3000);
}

async function handleStopAction(cliId: string): Promise<NextResponse> {
  const entry = processes.get(cliId);
  if (!entry) {
    return NextResponse.json({ cliId, status: "idle" });
  }

  const sessionId = cliId.startsWith("agent-bubble-")
    ? null
    : getSessionManager().getLastSessionId(cliId);
  const pid = entry.ptyProcess.pid;
  stopCliProcess(entry);
  processes.delete(cliId);
  const shouldClearSharedSession = getSessionManager().markCliStopped(cliId);
  if (sessionId && typeof pid === "number") {
    try {
      await releaseDashboardSessionOwner({ sessionId, pid });
    } catch (err) {
      console.warn("[CLI] failed to release dashboard session owner", err);
    }
  }
  if (shouldClearSharedSession) {
    writeChatSession({ isActive: false, status: "idle", context: {} });
  }
  return NextResponse.json({ cliId, status: "exited" });
}

/**
 * ADR-535 0F: Detach a running session — close SSE without killing PTY.
 */
function handleDetachAction(cliId: string): NextResponse {
  const entry = processes.get(cliId);
  if (!entry) {
    return NextResponse.json(
      { error: `CLI '${cliId}' is not running` },
      { status: 409 },
    );
  }

  if (entry.exited) {
    return NextResponse.json({
      cliId,
      status: "exited",
      exitCode: entry.exitCode,
    });
  }

  if (entry.detached) {
    // Already detached — return current state
    return NextResponse.json({
      success: true,
      cliId,
      pid: entry.ptyProcess.pid,
      status: "detached",
      uptime: Math.floor((Date.now() - entry.startTime) / 1000),
      detachedAt: entry.detachedAt,
    });
  }

  detachSession(cliId, entry);

  return NextResponse.json({
    success: true,
    cliId,
    pid: entry.ptyProcess.pid,
    status: "detached",
    uptime: Math.floor((Date.now() - entry.startTime) / 1000),
  });
}

// ============================================================================
// Action Dispatch Map
// ============================================================================

type CliActionHandler = (
  cliId: string,
  body: CliRequestBody,
) => Promise<NextResponse> | NextResponse;

export const CLI_ACTION_HANDLERS: Record<string, CliActionHandler> = {
  start: handleStartAction,
  send: handleSendAction,
  sendRaw: handleSendRawAction,
  resize: handleResizeAction,
  stop: (cliId: string) => handleStopAction(cliId),
  system: handleSystemAction,
  detach: (cliId: string) => handleDetachAction(cliId),
};
