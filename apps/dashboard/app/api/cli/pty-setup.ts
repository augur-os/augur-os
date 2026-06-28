/**
 * CLI Route — PTY Setup
 *
 * Initializes node-pty, validates the POSIX spawn-helper binary when needed,
 * manages the global PTY process registry, and provides
 * buffer/lifecycle constants.
 *
 * Extracted from route.ts to isolate native-addon setup from
 * request handling.
 */

import path from "path";
import fs from "fs";

// node-pty provides a real PTY so interactive CLIs (claude, codex, kimi, etc.)
// detect a terminal and start their interactive REPL properly.
// Without a PTY, these CLIs hang or enter degraded non-interactive mode.
// NOTE: The prebuilt spawn-helper binary needs +x permission on macOS.
// This is handled by the postinstall script in package.json.
//
// IMPORTANT: on POSIX platforms, node-pty's native addon uses posix_spawnp to
// launch an internal spawn-helper binary, which it locates via __dirname-relative
// paths. When Turbopack hot-reloads or re-evaluates this module, the native
// addon's path resolution can break, causing "posix_spawnp failed". We
// pre-validate the spawn-helper path and patch it if needed. Windows uses
// node-pty's win32 backend and does not ship or need this helper.
//
// Lazy require: Turbopack mangles static import names for external modules,
// causing "Cannot find module node-pty-<hash>" at runtime. Dynamic require
// with a computed string bypasses Turbopack's transform.
export type IPtyProcess = import("node-pty").IPty;
export const pty: typeof import("node-pty") = require(/* webpackIgnore: true */ "node-pty");

export interface PtySpawnHelperStatus {
  path: string;
  exists: boolean;
  required: boolean;
}

interface PtySpawnHelperResolveOptions {
  platform?: string;
  arch?: string;
}

function resolveExistingPath(candidate: string | null | undefined): string | null {
  if (!candidate) return null;
  try {
    if (!fs.existsSync(candidate)) return null;
    return fs.realpathSync(candidate);
  } catch {
    return null;
  }
}

export function resolvePtySpawnHelper(
  requireResolve: (request: string) => string = require.resolve,
  cwd: string = process.cwd(),
  options: PtySpawnHelperResolveOptions = {},
): PtySpawnHelperStatus {
  const platform = options.platform ?? process.platform;
  const arch = options.arch ?? process.arch;

  if (platform === "win32") {
    return {
      path: "not-required-on-win32",
      exists: true,
      required: false,
    };
  }

  const candidateRoots: string[] = [];

  for (const request of ["node-pty/package.json", "node-pty"]) {
    try {
      const resolved = requireResolve(request);
      if (typeof resolved === "string") {
        const realResolved = resolveExistingPath(resolved);
        if (realResolved) {
          candidateRoots.push(
            request.endsWith("package.json")
              ? path.dirname(realResolved)
              : path.resolve(path.dirname(realResolved), ".."),
          );
        }
      }
    } catch {
      // Fall through to filesystem candidates below.
    }
  }

  candidateRoots.push(path.join(cwd, "node_modules", "node-pty"));
  candidateRoots.push(path.join(cwd, "..", "node_modules", "node-pty"));

  for (const root of candidateRoots) {
    const realRoot = resolveExistingPath(root);
    if (!realRoot) continue;
    const helperPath = path.join(
      realRoot,
      "prebuilds",
      `${platform}-${arch}`,
      "spawn-helper",
    );
    if (fs.existsSync(helperPath)) {
      try {
        fs.chmodSync(helperPath, 0o755);
      } catch {
        // Non-fatal: might be read-only filesystem
      }
      return { path: helperPath, exists: true, required: true };
    }
  }

  const fallbackRoot =
    resolveExistingPath(path.join(cwd, "node_modules", "node-pty")) ??
    path.resolve(cwd, "node_modules", "node-pty");
  return {
    path: path.join(
      fallbackRoot,
      "prebuilds",
      `${platform}-${arch}`,
      "spawn-helper",
    ),
    exists: false,
    required: true,
  };
}

/**
 * Ensure node-pty's spawn-helper binary is accessible.
 * Turbopack module reloading can break __dirname-based path resolution
 * in the native addon. We verify and log the spawn-helper path on load.
 */
export const PTY_SPAWN_HELPER = (() => {
  try {
    const helper = resolvePtySpawnHelper();
    const { path: helperPath, exists } = helper;
    if (!exists) {
      console.warn(`[CLI] node-pty spawn-helper NOT FOUND at ${helperPath}`);
    }
    return helper;
  } catch (e) {
    console.warn("[CLI] Failed to locate node-pty spawn-helper:", e);
    return { path: "unknown", exists: false };
  }
})();

// Lazy health check — set on first spawn attempt, avoids side effects at module load
export let ptyHealthy: boolean | null = null;
export function setPtyHealthy(value: boolean | null): void {
  ptyHealthy = value;
}

// ============================================================================
// Process Registry
// ============================================================================

export interface PtyEntry {
  ptyProcess: IPtyProcess;
  cliId?: string;
  sessionId?: string | null;
  airplaneMode?: boolean;
  airplaneLocalModel?: string | null;
  themeMode?: "light" | "dark";
  startTime: number;
  outputBuffer: string[];
  rawBuffer: string[]; // Raw PTY chunks with ANSI codes intact (for xterm.js)
  /** Absolute cursor of the first retained raw chunk */
  rawCursorStart: number;
  /** Absolute cursor immediately after the last retained raw chunk */
  rawCursorEnd: number;
  exited: boolean;
  exitCode: number | null;
  /** ADR-535 0E: Session is detached (SSE disconnected, PTY still alive) */
  detached: boolean;
  /** ADR-535 0E: Timestamp when session was detached */
  detachedAt: number | null;
  /** ADR-535 0E: Timer that kills the PTY after idle timeout when detached */
  detachTimer: ReturnType<typeof setTimeout> | null;
  /** ADR-535 0E: Absolute raw cursor at time of detach — used for replay on reconnect */
  detachRawIndex: number | null;
}

// Use process object for storage — it is more reliable than globalThis in Next.js/Turbopack
// which sometimes resets globalThis context during strict HMR updates.
const PROC_KEY = Symbol.for("augur.cli.processes");
const _g = process as unknown as { [PROC_KEY]?: Map<string, PtyEntry> };
if (!_g[PROC_KEY]) _g[PROC_KEY] = new Map();
export const processes = _g[PROC_KEY]!;

const MAX_BUFFER_LINES = 2000;
// TODO_CLEANUP: rawBuffer/outputBuffer are line-capped (2000 entries) but not
// byte-capped — 2000 large raw PTY chunks can still retain tens of MB per
// detached session. A byte cap must be cursor-aware (adjust rawCursorStart/
// rawCursorEnd in lockstep with any extra eviction, per the replay contract in
// cli-stream-replay.test.ts) — a naive slice would desync replay. Deferred from
// the 2026-06-25 dashboard-dev-oom-fix plan: the unbounded leak was exec
// (exec-store, fixed); PTY hardening is unproven as material — add only if a
// heap snapshot shows PTY buffers are a real contributor.

// ============================================================================
// PTY Helpers
// ============================================================================

export function stripAnsi(text: string): string {
  // Strip ANSI escape codes for cleaner output in the chat.
  // Handles: CSI sequences (incl. private modes like ?2026h),
  // OSC sequences (title setting), and other common escapes.
  return text
    .replace(/\x1b\[[?>=<!]?[0-9;]*[a-zA-Z~]/g, "") // CSI sequences (incl. private modes)
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, "") // OSC sequences (title, etc.)
    .replace(/\x1b[()][0-9A-Za-z]/g, "") // Character set selection
    .replace(/\x1b[>=<~}|]/g, "") // Keypad/misc modes
    .replace(/\r/g, ""); // Strip carriage returns
}

/** ADR-535 0E: How long a detached session stays alive before auto-kill (ms) */
const DETACH_IDLE_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

export function createPtyEntry(ptyProcess: IPtyProcess): PtyEntry {
  return {
    ptyProcess,
    startTime: Date.now(),
    outputBuffer: [],
    rawBuffer: [],
    rawCursorStart: 0,
    rawCursorEnd: 0,
    exited: false,
    exitCode: null,
    detached: false,
    detachedAt: null,
    detachTimer: null,
    detachRawIndex: null,
  };
}

/**
 * ADR-535 0E: Mark a session as detached and start the idle kill timer.
 * Called when SSE stream disconnects without an explicit stop.
 */
export function detachSession(cliId: string, entry: PtyEntry): void {
  if (entry.exited || entry.detached) return;

  entry.detached = true;
  entry.detachedAt = Date.now();
  entry.detachRawIndex = entry.rawCursorEnd;

  // Clear any existing timer
  if (entry.detachTimer) clearTimeout(entry.detachTimer);

  // Auto-kill after idle timeout
  entry.detachTimer = setTimeout(() => {
    const current = processes.get(cliId);
    if (current && current.detached && !current.exited) {
      console.log(`[CLI] Detached session '${cliId}' timed out after ${DETACH_IDLE_TIMEOUT_MS / 1000}s — killing PTY`);
      current.ptyProcess.kill();
      processes.delete(cliId);
    }
  }, DETACH_IDLE_TIMEOUT_MS);
}

/**
 * ADR-535 0E: Reattach a detached session (clear detach state, cancel kill timer).
 */
export function reattachSession(entry: PtyEntry): void {
  if (entry.detachTimer) {
    clearTimeout(entry.detachTimer);
    entry.detachTimer = null;
  }
  entry.detached = false;
  entry.detachedAt = null;
  // detachRawIndex is kept until replay is done, then cleared by the stream builder
}

export function attachPtyHandlers(entry: PtyEntry): void {
  const { ptyProcess } = entry;

  ptyProcess.onData((data: string) => {
    entry.rawBuffer.push(data);
    entry.rawCursorEnd += 1;
    if (entry.rawBuffer.length > MAX_BUFFER_LINES) {
      const dropped = entry.rawBuffer.length - MAX_BUFFER_LINES;
      entry.rawBuffer = entry.rawBuffer.slice(-MAX_BUFFER_LINES);
      entry.rawCursorStart += dropped;
    }

    const cleaned = stripAnsi(data);
    const lines = cleaned.split("\n").filter((line) => line.trim() !== "");
    if (lines.length === 0) return;

    entry.outputBuffer.push(...lines);
    if (entry.outputBuffer.length > MAX_BUFFER_LINES) {
      entry.outputBuffer = entry.outputBuffer.slice(-MAX_BUFFER_LINES);
    }
  });

  ptyProcess.onExit(({ exitCode }) => {
    entry.exited = true;
    entry.exitCode = exitCode;
  });
}

export function getRawReplayWindow(
  entry: PtyEntry,
  fromCursor: number | null,
): { chunks: string[]; cursorEnd: number; reset: boolean } {
  if (fromCursor === null || Number.isNaN(fromCursor) || fromCursor <= 0) {
    return {
      chunks: [...entry.rawBuffer],
      cursorEnd: entry.rawCursorEnd,
      reset: false,
    };
  }

  if (fromCursor < entry.rawCursorStart) {
    return {
      chunks: [...entry.rawBuffer],
      cursorEnd: entry.rawCursorEnd,
      reset: true,
    };
  }

  if (fromCursor >= entry.rawCursorEnd) {
    return {
      chunks: [],
      cursorEnd: entry.rawCursorEnd,
      reset: false,
    };
  }

  const startIndex = fromCursor - entry.rawCursorStart;
  return {
    chunks: entry.rawBuffer.slice(startIndex),
    cursorEnd: entry.rawCursorEnd,
    reset: false,
  };
}
