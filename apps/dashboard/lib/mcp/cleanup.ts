/**
 * MCP Bridge Process Cleanup
 *
 * Registers process-level cleanup handlers that prevent zombie MCP processes
 * and suppress benign network abort/stream errors during HMR restarts.
 */

import { ChildProcess } from "child_process";

const isTestEnv =
  process.env.NODE_ENV === "test" || process.env.JEST_WORKER_ID !== undefined;

const warn = (...args: unknown[]) => {
  if (!isTestEnv) {
    console.warn(...args);
  }
};

const error = (...args: unknown[]) => {
  if (!isTestEnv) {
    console.error(...args);
  }
};

const log = (...args: unknown[]) => {
  if (!isTestEnv) {
    console.log(...args);
  }
};

/** Helper to detect benign network abort errors */
function isAbortError(err: any): boolean {
  return (
    err.code === "ECONNRESET" ||
    err.code === "EPIPE" ||
    err.name === "AbortError" ||
    err.message === "aborted" ||
    err.message === "socket hang up"
  );
}

/**
 * Register process-level cleanup handlers for the MCP child process.
 *
 * In production: kills the MCP process group on exit/SIGINT/SIGTERM.
 * In development: leaves the detached MCP child alive (it dies when stdin closes).
 *
 * Also installs global error handlers to suppress benign ECONNRESET/abort errors
 * and stream errors from SSE routes.
 *
 * @returns cleanup function that can be called to kill the MCP process.
 */
export function registerCleanupHandlers(
  childProcess: ChildProcess | null,
): () => void {
  const cleanup = () => {
    if (childProcess) {
      log("[MCPBridge] Cleaning up MCP process before exit...");
      try {
        // Send SIGTERM to the detached process group
        process.kill(-childProcess.pid!, "SIGTERM");
      } catch (e) {
        // Process may already be dead -- ignore
        if ((e as NodeJS.ErrnoException).code !== "ESRCH") {
          error("[MCPBridge] Error killing MCP process:", e);
        }
      }
      childProcess = null;
    }
  };

  // In dev mode, HMR sends SIGTERM/SIGINT to restart the Node process.
  // Do NOT kill the detached MCP child -- it dies naturally when its stdin
  // pipe closes after the parent exits. Killing it explicitly causes a
  // SIGTERM -> respawn -> SIGTERM loop during rapid HMR restarts (cold .next build).
  if (process.env.NODE_ENV === "production") {
    process.on("exit", cleanup);
    process.on("SIGINT", cleanup);
    process.on("SIGTERM", cleanup);
  }

  // Global uncaught exception handler -- prepended so it runs before Next.js's
  // own handler, suppressing benign ECONNRESET/aborted errors before they're logged.
  process.prependListener("uncaughtException", (err: any) => {
    // Ignore common aborted connection errors that bubble up from Next.js/Node
    // when a client disconnects or aborts a fetch request.
    if (isAbortError(err)) {
      return; // suppress silently -- these are expected client disconnects
    }
    // Ignore WHATWG Streams errors from SSE routes when a client disconnects
    // mid-stream -- the controller is already closed before the interval fires.
    if (
      err instanceof TypeError &&
      typeof err.message === "string" &&
      err.message.includes("Controller is already closed")
    ) {
      return; // suppress silently
    }

    error("[MCPBridge] Uncaught exception:", err);
    if (process.env.NODE_ENV === "production") {
      cleanup();
      process.exit(1);
    }
    // In dev: log but don't kill MCP -- Next.js HMR exceptions shouldn't break MCP
  });

  // Unhandled promise rejection handler for async abort errors (fetch/SSE streams)
  process.on("unhandledRejection", (reason: any) => {
    if (isAbortError(reason)) {
      return; // suppress silently -- expected client disconnect
    }
    // Let other handlers or Node.js default handle non-abort rejections
  });

  // Handle stream errors directly to prevent them from bubbling to process
  if (childProcess) {
    childProcess.stdin?.on("error", (err) =>
      warn("[MCPBridge] stdin error:", err.message),
    );
    childProcess.stdout?.on("error", (err) =>
      warn("[MCPBridge] stdout error:", err.message),
    );
    childProcess.stderr?.on("error", (err) =>
      warn("[MCPBridge] stderr error:", err.message),
    );
  }

  return cleanup;
}
