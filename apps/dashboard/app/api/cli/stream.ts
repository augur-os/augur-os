/**
 * CLI Route — SSE Streaming
 *
 * Handles GET /api/cli?stream=true — streams real-time PTY output
 * to the browser via Server-Sent Events.  Supports raw (base64)
 * and cleaned (ANSI-stripped) output formats.
 *
 * Extracted from route.ts to isolate the SSE ReadableStream logic
 * from POST action handling.
 */

import { NextRequest, NextResponse } from "next/server";
import {
  filterOutput,
  filterRawOutput,
  type VerbosityLevel,
} from "@/lib/chat/quiet-filter";
import {
  processes,
  stripAnsi,
  ptyHealthy,
  detachSession,
  getRawReplayWindow,
  reattachSession,
} from "./pty-setup";
import { isValidCli } from "./cli-config";
import { getSessionManager } from "@/lib/session/SessionManager";

/**
 * GET /api/cli?cliId=xxx - Get CLI process status
 * GET /api/cli?cliId=xxx&stream=true - SSE output stream (cleaned text)
 * GET /api/cli?cliId=xxx&stream=true&format=raw - SSE output stream (raw PTY data, base64-encoded)
 */
export async function handleGetCli(request: NextRequest): Promise<Response> {
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

  const { searchParams } = new URL(request.url);
  const action = searchParams.get("action");

  // ADR-535 0F: List all active/detached sessions
  if (action === "list") {
    return handleListSessions();
  }

  const cliId = searchParams.get("cliId");
  const stream = searchParams.get("stream") === "true";
  const format = searchParams.get("format") || "cleaned"; // 'raw' | 'cleaned'
  const rawCursorParam = searchParams.get("cursor");
  const verbosity = (searchParams.get("verbosity") ||
    "normal") as VerbosityLevel;
  const rawCursor =
    rawCursorParam !== null && rawCursorParam.trim() !== ""
      ? Number(rawCursorParam)
      : null;

  if (!cliId) {
    return NextResponse.json(
      { error: "Missing cliId parameter" },
      { status: 400 },
    );
  }

  if (!isValidCli(cliId)) {
    return NextResponse.json(
      { error: `Unknown CLI: ${cliId}` },
      { status: 400 },
    );
  }

  // ADR-535 0E: Handle reconnect action
  if (action === "reconnect") {
    return handleReconnect(request, cliId, format === "raw", verbosity, rawCursor);
  }

  const entry = processes.get(cliId);

  if (!stream) {
    if (!entry) {
      return NextResponse.json({
        cliId,
        status: "idle",
        ptyHealthy: ptyHealthy,
      });
    }

    const status = entry.exited ? "exited" : entry.detached ? "detached" : "running";
    const uptime = Math.floor((Date.now() - entry.startTime) / 1000);

    // Expose the backend this session is actually running on (server truth) so
    // the chat header can tell when a toggled airplane preference has not been
    // applied to the in-progress session yet.
    const backend = getSessionManager().getActiveBackend();
    const backendMatches = backend.running && backend.cliId === cliId;

    return NextResponse.json({
      cliId,
      status,
      pid: entry.ptyProcess.pid,
      uptime,
      detached: entry.detached,
      detachedAt: entry.detachedAt,
      ...(backendMatches
        ? {
            sessionAirplaneMode: backend.airplaneMode,
            sessionLocalModel: backend.localModel,
          }
        : {}),
    });
  }

  // SSE streaming output
  if (!entry) {
    return NextResponse.json(
      { error: `CLI '${cliId}' is not running` },
      { status: 409 },
    );
  }

  // ADR-160: If the process already exited, replay buffered output + exit event.
  // This handles the race where the CLI finishes before the browser's SSE connects
  // (common for agent bubbles with fast-completing prompts).
  if (entry.exited) {
    return buildExitedStream(entry, format === "raw");
  }

  // ADR-535 0E: If session was detached, reattach it when a new stream connects
  if (entry.detached) {
    reattachSession(entry);
  }

  return buildLiveStream(
    request,
    entry,
    cliId,
    format === "raw",
    verbosity,
    rawCursor,
  );
}

// ============================================================================
// ADR-535 0E: Reconnect Handler
// ============================================================================

function handleReconnect(
  request: NextRequest,
  cliId: string,
  isRaw: boolean,
  verbosity: VerbosityLevel,
  rawCursor: number | null,
): Response {
  const entry = processes.get(cliId);

  if (!entry) {
    return NextResponse.json(
      { error: `Session '${cliId}' not found`, code: "NOT_FOUND" },
      { status: 404 },
    );
  }

  // If the process already exited, replay final output + exit event
  if (entry.exited) {
    return buildExitedStream(entry, isRaw);
  }

  // Reattach: cancel kill timer, clear detach state
  const replayCursor = rawCursor ?? entry.detachRawIndex;
  reattachSession(entry);

  // Build a live stream that first replays output accumulated since detach
  return buildReconnectStream(
    request,
    entry,
    cliId,
    isRaw,
    verbosity,
    replayCursor,
  );
}

// ============================================================================
// ADR-535 0F: List Sessions Handler
// ============================================================================

function handleListSessions(): Response {
  const sessions: Array<{
    cliId: string;
    status: string;
    pid: number;
    uptime: number;
    detached: boolean;
    detachedAt: number | null;
  }> = [];

  for (const [cliId, entry] of processes.entries()) {
    sessions.push({
      cliId,
      status: entry.exited ? "exited" : entry.detached ? "detached" : "running",
      pid: entry.ptyProcess.pid,
      uptime: Math.floor((Date.now() - entry.startTime) / 1000),
      detached: entry.detached,
      detachedAt: entry.detachedAt,
    });
  }

  return NextResponse.json({ sessions });
}

// ============================================================================
// Stream Builders
// ============================================================================

function buildExitedStream(
  entry: { rawBuffer: string[]; outputBuffer: string[]; exitCode: number | null },
  isRaw: boolean,
): Response {
  const encoder = new TextEncoder();
  const readable = new ReadableStream({
    start(controller) {
      const send = (payload: string) => {
        try {
          controller.enqueue(encoder.encode(payload));
        } catch {
          /* stream closed */
        }
      };

      const buf = isRaw ? entry.rawBuffer : entry.outputBuffer;
      if (buf.length > 0) {
        if (isRaw) {
          const b64 = Buffer.from(buf.join(""), "utf-8").toString("base64");
          send(`data: ${JSON.stringify({ raw: b64 })}\n\n`);
        } else {
          send(`data: ${JSON.stringify({ output: buf.join("\n") })}\n\n`);
        }
      }
      send(
        `data: ${JSON.stringify({ event: "exit", code: entry.exitCode })}\n\n`,
      );
      controller.close();
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

function buildLiveStream(
  request: NextRequest,
  entry: ReturnType<typeof processes.get> & {},
  cliId: string,
  isRaw: boolean,
  verbosity: VerbosityLevel,
  rawCursor: number | null,
): Response {
  const encoder = new TextEncoder();

  // Disposable listeners and timers — cleaned up on disconnect/exit
  let dataDisposable: { dispose(): void } | null = null;
  let exitDisposable: { dispose(): void } | null = null;
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  let streamClosed = false;

  function cleanup() {
    if (dataDisposable) {
      dataDisposable.dispose();
      dataDisposable = null;
    }
    if (exitDisposable) {
      exitDisposable.dispose();
      exitDisposable = null;
    }
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
  }

  const readable = new ReadableStream({
    start(controller) {
      // Helper: enqueue an SSE message, return false if stream is dead
      const send = (payload: string): boolean => {
        if (streamClosed) {
          return false;
        }
        try {
          controller.enqueue(encoder.encode(payload));
          return true;
        } catch (err) {
          console.error(`[SSE:${cliId}] enqueue FAILED:`, err);
          cleanup();
          streamClosed = true;
          return false;
        }
      };

      // 1. Send the initial buffered content as one dump
      if (isRaw) {
        const replay = getRawReplayWindow(entry, rawCursor);
        if (replay.chunks.length > 0) {
          const combined = replay.chunks.join("");
          const b64 = Buffer.from(combined, "utf-8").toString("base64");
          send(
            `data: ${JSON.stringify({ raw: b64, cursor: replay.cursorEnd, reset: replay.reset })}\n\n`,
          );
        }
      } else if (entry.outputBuffer.length > 0) {
        const chunk = entry.outputBuffer.join("\n");
        send(`data: ${JSON.stringify({ output: chunk })}\n\n`);
      }

      // 2. Send padding to prime HTTP response buffers and force initial flush.
      //    SSE comments (lines starting with ':') are ignored by clients.
      send(`: ${" ".repeat(2048)}\n\n`);

      // 3. Event-driven: push new PTY data directly into the stream
      //    ADR-157: Apply quiet mode filter when verbosity is set
      dataDisposable = entry.ptyProcess.onData((data: string) => {
        if (isRaw) {
          const filtered = filterRawOutput(data, verbosity);
          if (!filtered) return;
          const b64 = Buffer.from(filtered, "utf-8").toString("base64");
          send(
            `data: ${JSON.stringify({ raw: b64, cursor: entry.rawCursorEnd })}\n\n`,
          );
        } else {
          const cleaned = stripAnsi(data);
          const filtered = filterOutput(cleaned, verbosity);
          const lines = filtered
            .split("\n")
            .filter((line) => line.trim() !== "");
          if (lines.length === 0) return;
          send(`data: ${JSON.stringify({ output: lines.join("\n") })}\n\n`);
        }
      });

      // 4. Handle process exit
      exitDisposable = entry.ptyProcess.onExit(({ exitCode }) => {
        send(`data: ${JSON.stringify({ event: "exit", code: exitCode })}\n\n`);
        cleanup();
        streamClosed = true;
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });

      // 5. Heartbeat every 15s to keep connection alive and detect stale processes
      heartbeatInterval = setInterval(() => {
        const current = processes.get(cliId);
        if (!current || current.exited) {
          send(
            `data: ${JSON.stringify({ event: "exit", code: current?.exitCode ?? null })}\n\n`,
          );
          cleanup();
          streamClosed = true;
          try {
            controller.close();
          } catch {
            /* already closed */
          }
          return;
        }
        send(`: heartbeat\n\n`);
      }, 15_000);

      // 6. Cleanup on client disconnect — ADR-535 0E: mark detached instead of killing
      request.signal.addEventListener("abort", () => {
        cleanup();
        streamClosed = true;
        // Mark session as detached so it can be reconnected
        const current = processes.get(cliId);
        if (current && !current.exited) {
          detachSession(cliId, current);
        }
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });
    },
    cancel() {
      cleanup();
      streamClosed = true;
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "Content-Encoding": "none",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}

// ============================================================================
// ADR-535 0E: Reconnect Stream Builder
// ============================================================================

/**
 * Build an SSE stream for a reconnected session.
 * First replays raw output accumulated since detach, then switches to live streaming.
 */
function buildReconnectStream(
  request: NextRequest,
  entry: ReturnType<typeof processes.get> & {},
  cliId: string,
  isRaw: boolean,
  verbosity: VerbosityLevel,
  replayCursor: number | null,
): Response {
  const encoder = new TextEncoder();

  let dataDisposable: { dispose(): void } | null = null;
  let exitDisposable: { dispose(): void } | null = null;
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  let streamClosed = false;

  function cleanup() {
    if (dataDisposable) {
      dataDisposable.dispose();
      dataDisposable = null;
    }
    if (exitDisposable) {
      exitDisposable.dispose();
      exitDisposable = null;
    }
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
  }

  const readable = new ReadableStream({
    start(controller) {
      const send = (payload: string): boolean => {
        if (streamClosed) return false;
        try {
          controller.enqueue(encoder.encode(payload));
          return true;
        } catch (err) {
          console.error(`[SSE:${cliId}] reconnect enqueue FAILED:`, err);
          cleanup();
          streamClosed = true;
          return false;
        }
      };

      // 1. Send reconnect event so client knows this is a reconnection
      send(`data: ${JSON.stringify({ event: "reconnected", cliId })}\n\n`);

      // 2. Replay output accumulated during detach period
      if (isRaw) {
        const replay = getRawReplayWindow(entry, replayCursor);
        if (replay.chunks.length > 0) {
          const combined = replay.chunks.join("");
          const b64 = Buffer.from(combined, "utf-8").toString("base64");
          send(
            `data: ${JSON.stringify({ raw: b64, cursor: replay.cursorEnd, reset: replay.reset })}\n\n`,
          );
        }
      } else if (entry.outputBuffer.length > 0) {
        // For cleaned format, replay the full buffer (no index tracking for cleaned)
        const chunk = entry.outputBuffer.join("\n");
        send(`data: ${JSON.stringify({ output: chunk })}\n\n`);
      }

      // Clear the replay index now that we've caught up
      entry.detachRawIndex = null;

      // 3. Send padding to prime response buffers
      send(`: ${" ".repeat(2048)}\n\n`);

      // 4. Live streaming from here on (same as buildLiveStream)
      dataDisposable = entry.ptyProcess.onData((data: string) => {
        if (isRaw) {
          const filtered = filterRawOutput(data, verbosity);
          if (!filtered) return;
          const b64 = Buffer.from(filtered, "utf-8").toString("base64");
          send(
            `data: ${JSON.stringify({ raw: b64, cursor: entry.rawCursorEnd })}\n\n`,
          );
        } else {
          const cleaned = stripAnsi(data);
          const filtered = filterOutput(cleaned, verbosity);
          const lines = filtered
            .split("\n")
            .filter((line) => line.trim() !== "");
          if (lines.length === 0) return;
          send(`data: ${JSON.stringify({ output: lines.join("\n") })}\n\n`);
        }
      });

      // 5. Handle process exit
      exitDisposable = entry.ptyProcess.onExit(({ exitCode }) => {
        send(`data: ${JSON.stringify({ event: "exit", code: exitCode })}\n\n`);
        cleanup();
        streamClosed = true;
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });

      // 6. Heartbeat
      heartbeatInterval = setInterval(() => {
        const current = processes.get(cliId);
        if (!current || current.exited) {
          send(
            `data: ${JSON.stringify({ event: "exit", code: current?.exitCode ?? null })}\n\n`,
          );
          cleanup();
          streamClosed = true;
          try {
            controller.close();
          } catch {
            /* already closed */
          }
          return;
        }
        send(`: heartbeat\n\n`);
      }, 15_000);

      // 7. Cleanup on client disconnect — mark detached again
      request.signal.addEventListener("abort", () => {
        cleanup();
        streamClosed = true;
        const current = processes.get(cliId);
        if (current && !current.exited) {
          detachSession(cliId, current);
        }
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });
    },
    cancel() {
      cleanup();
      streamClosed = true;
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "Content-Encoding": "none",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
