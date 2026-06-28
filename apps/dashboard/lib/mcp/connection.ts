// TODO_CLEANUP: This file is 921 lines — consider splitting into smaller modules
/**
 * MCP Bridge Connection
 *
 * Core MCPBridge class providing stdio-based communication with the MCP server.
 * Handles connection lifecycle, reconnection, cleanup, context switching,
 * and JSON-RPC message handling.
 */

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import fsSync from "fs";
import path from "path";
import { AUGUR_PYTHON, AUGUR_ROOT } from "../paths";
import { emitHealEvent } from "../self-heal-event";
import type {
  MCPToolResult,
  MCPServerContext,
  PendingRequest,
  ContextSwitchResult,
} from "./types";
import {
  type PreflightContract,
  resolveMcpClientId,
  resolvePreflightContract,
  scopeDashboardProcessClientId,
} from "./preflight";
import {
  diagnosePermanentFailure,
  tryLLMDiagnosis,
} from "./diagnostics";
import { registerCleanupHandlers } from "./cleanup";

const isTestEnv =
  process.env.NODE_ENV === "test" || process.env.JEST_WORKER_ID !== undefined;

const log = (...args: unknown[]) => {
  if (!isTestEnv) {
    console.log(...args);
  }
};

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

const NOISY_SERVER_STDERR_PATTERNS = [
  "Processing request of type ",
  "Prompt already exists:",
  "Tool already exists:",
  "Chunks pending contextualization:",
  "Contextualized ",
  "Contextualization skipped by caller",
  "Generated index.md (",
  "BM25 index built:",
  "Enriched ",
];
const MCP_STDERR_ERROR_PATTERN = /ERROR|CRITICAL|Traceback|Exception/;
const MCP_STDERR_WARNING_PATTERN = /WARNING/;

const DASHBOARD_MCP_SERVER_MODULE = "augur_framework";

export function isNoisyServerStderr(line: string): boolean {
  return NOISY_SERVER_STDERR_PATTERNS.some((pattern) => line.includes(pattern));
}

function hasTopLevelMcpPackage(entry: string): boolean {
  try {
    return fsSync.existsSync(path.join(entry, "mcp", "__init__.py"));
  } catch {
    return false;
  }
}

export function resolveMcpPythonPath(
  augurRoot: string,
  inheritedPythonPath: string | undefined = process.env.PYTHONPATH,
): string {
  const entries = [path.join(augurRoot, "src", "mcp"), augurRoot];
  const seen = new Set(entries.map((entry) => path.resolve(entry).toLowerCase()));

  for (const rawEntry of (inheritedPythonPath || "").split(path.delimiter)) {
    const entry = rawEntry.trim();
    if (!entry) continue;

    const resolved = path.resolve(entry);
    const key = resolved.toLowerCase();
    if (seen.has(key)) continue;

    // Some daemon helper paths contain a local `mcp` package used by tests/tools.
    // Leaving those ahead of site-packages shadows the MCP SDK's `mcp.server`.
    if (hasTopLevelMcpPackage(resolved)) continue;

    seen.add(key);
    entries.push(resolved);
  }

  return entries.join(path.delimiter);
}

/**
 * MCP Bridge - Singleton stdio client for MCP server communication
 */
export class MCPBridge extends EventEmitter {
  private static instance: MCPBridge | null = null;
  private static instances: Map<string, MCPBridge> = new Map();
  private serverModule: string;
  private process: ChildProcess | null = null;
  private buffer: string = "";
  private requestId: number = 0;
  private pendingRequests: Map<number, PendingRequest> = new Map();
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 3;
  private reconnectAttemptLogs: Array<{
    attempt: number;
    error: string;
    timestamp: string;
  }> = []; // ADR-106
  private requestTimeout: number = 60000; // 60 seconds
  private connectionPromise: Promise<void> | null = null;
  private maxConcurrent: number = 10;
  private activeRequests: number = 0;
  private requestQueue: Array<() => void> = [];
  private lastStderrOutput: string = "";
  private lastExitSignal: string | null = null;
  private permanentFailure: string | null = null;
  private lastConnectTime: number = 0;
  private recoveryAttempts: number = 0; // full recovery cycles (after max reconnect exhausted)
  private diagnosisAttempted: boolean = false; // fire LLM diagnosis only once per recovery session
  private static STABLE_CONNECTION_MS = 5000; // connection must survive 5s to be "stable"
  private static MAX_RECOVERY_ATTEMPTS = 5;
  private static RECOVERY_BASE_DELAY_MS = 10000; // 10s, doubles each cycle
  private lastLaunchSignature: string | null = null;
  private lastLaunchContract: {
    augurRoot: string;
    pythonCmd: string;
    clientId: string;
    runtimeDir: string;
    mcpPort: string;
    pythonPath: string;
  } | null = null;

  // Context management
  private currentPage: string = "/";
  private toolSwitchInProgress: boolean = false;
  private preloadQueue: Set<string> = new Set();
  private handlersRegistered: boolean = false;

  private constructor(serverModule: string = DASHBOARD_MCP_SERVER_MODULE) {
    super();
    this.serverModule = serverModule;
  }

  /**
   * Get singleton instance of MCPBridge, keyed by server module.
   *
   * Calling with no argument (or with the framework module name) returns the
   * same battle-tested framework singleton as before — behaviour is unchanged.
   * Calling with a different module name (e.g. "augur_core") returns a distinct
   * lazy instance that only spawns on first connect().
   */
  public static getInstance(serverModule: string = DASHBOARD_MCP_SERVER_MODULE): MCPBridge {
    if (serverModule === DASHBOARD_MCP_SERVER_MODULE) {
      // Framework path: preserve the exact original singleton logic so all
      // existing callers and test cleanup (instance = null / __mcp_bridge__)
      // continue to work without any change.
      if (process.env.NODE_ENV === "development") {
        const g = globalThis as any;
        if (g.__mcp_bridge__ && !(g.__mcp_bridge__ instanceof MCPBridge)) {
          void g.__mcp_bridge__.disconnect?.();
          g.__mcp_bridge__ = null;
        }
        if (!g.__mcp_bridge__) {
          g.__mcp_bridge__ = new MCPBridge(serverModule);
        }
        return g.__mcp_bridge__;
      }

      if (!MCPBridge.instance) {
        MCPBridge.instance = new MCPBridge(serverModule);
      }
      return MCPBridge.instance;
    }

    // Non-framework modules: per-module keyed singletons, lazy and additive.
    if (process.env.NODE_ENV === "development") {
      const g = globalThis as any;
      g.__mcp_bridges__ = g.__mcp_bridges__ || {};
      // Mirror the framework path's HMR-staleness guard: if hot-reload replaced
      // the MCPBridge class, drop the stale instance before reusing it.
      const existing = g.__mcp_bridges__[serverModule];
      if (existing && !(existing instanceof MCPBridge)) {
        void existing.disconnect?.();
        g.__mcp_bridges__[serverModule] = null;
      }
      if (!g.__mcp_bridges__[serverModule]) {
        g.__mcp_bridges__[serverModule] = new MCPBridge(serverModule);
      }
      return g.__mcp_bridges__[serverModule];
    }

    let inst = MCPBridge.instances.get(serverModule);
    if (!inst) {
      inst = new MCPBridge(serverModule);
      MCPBridge.instances.set(serverModule, inst);
    }
    return inst;
  }

  /**
   * Connect to MCP server via stdio
   */
  public async connect(): Promise<void> {
    if (this.isConnected && this.process) {
      return; // Already connected
    }

    const launchContract = this.resolveLaunchContract();

    // Re-run preflight before honoring a cached permanent failure so the bridge
    // can recover when the repo interpreter/runtime changed after a merge or repair.
    if (this.permanentFailure) {
      const contractChanged =
        this.lastLaunchSignature !== null &&
        launchContract.signature !== this.lastLaunchSignature;

      if (!contractChanged) {
        throw new Error(this.permanentFailure);
      }

      warn(
        "[MCPBridge] Clearing cached permanent failure after launch contract changed",
      );
      this.permanentFailure = null;
    }

    if (this.connectionPromise) {
      return this.connectionPromise;
    }

    this.connectionPromise = (async () => {
      try {
        const { preflight, augurRoot, pythonCmd, clientId, signature } =
          launchContract;

        log("[MCPBridge] Starting MCP server via module");

        // Run as module — must match scripts/augur-mcp entry point and PYTHONPATH
        const pythonPath = resolveMcpPythonPath(augurRoot);

        // Pass --force on reconnect attempts to clear stale lock files
        // from crashed MCP processes. Without this, a stale /tmp/augur-mcp-*.pid
        // blocks all subsequent MCP connections permanently.
        const forceFlag = this.reconnectAttempts > 0 || this.recoveryAttempts > 0;
        this.lastLaunchSignature = signature;
        this.lastLaunchContract = {
          augurRoot,
          pythonCmd,
          clientId,
          runtimeDir: preflight.runtime_dir || "",
          mcpPort: String(preflight.mcp_port || process.env.MCP_PORT || ""),
          pythonPath,
        };
        log(
          `[MCPBridge] Launch contract root=${augurRoot} python=${pythonCmd} client=${clientId}`,
        );
        // @spawn-exempt: launches the MCP server process itself — this IS the MCP
        // transport channel, not work that could be routed through MCP. See ADR-817.
        this.process = spawn(
          pythonCmd,
          [
            "-m",
            this.serverModule,
            "--client-id",
            clientId,
            ...(forceFlag ? ["--force"] : []),
          ],
          {
            cwd: augurRoot,
            env: {
              ...process.env,
              AUGUR_ROOT: augurRoot,
              AUGUR_CORE: augurRoot,
              AUGUR_STATE: preflight.runtime_dir || process.env.AUGUR_STATE,
              AUGUR_RUNTIME: preflight.runtime_dir || process.env.AUGUR_RUNTIME,
              MCP_PORT: String(
                preflight.mcp_port || process.env.MCP_PORT || "",
              ),
              AUGUR_DASHBOARD_MCP_INCLUDE_CORE_TOOLS: "1",
              AUGUR_MCP_INCLUDE_VAULT_TIER_TOOLS: "1",
              AUGUR_MCP_CLIENT_ID: clientId,
              PYTHONPATH: pythonPath,
            },
            stdio: ["pipe", "pipe", "pipe"],
            // Detach from parent process group so HMR restarts don't SIGTERM the child
            detached: true,
          },
        );

        // Allow the parent Node.js process to exit without waiting for the child.
        // We manage the child lifecycle explicitly via cleanup handlers.
        this.process.unref();

        // Handle stdout (JSON-RPC responses)
        this.process.stdout?.on("data", (data: Buffer) => {
          this.handleData(data.toString());
        });

        // Handle stderr (logs) — capture output for error diagnosis
        this.process.stderr?.on("data", (data: Buffer) => {
          const output = data.toString();
          this.lastStderrOutput += output;

          // Keep only last 4KB to avoid memory growth
          if (this.lastStderrOutput.length > 4096) {
            this.lastStderrOutput = this.lastStderrOutput.slice(-4096);
          }

          const lines = output.split("\n");

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            if (
              MCP_STDERR_ERROR_PATTERN.test(trimmed)
            ) {
              error("[MCPBridge] Server error:", trimmed);
            } else if (MCP_STDERR_WARNING_PATTERN.test(trimmed)) {
              warn("[MCPBridge] Server warning:", trimmed);
            } else if (isNoisyServerStderr(trimmed)) {
              continue;
            } else {
              // Log all other messages to help debug missing tracebacks
              log("[MCPBridge] stderr:", trimmed);
            }
          }
        });

        // Handle process exit
        this.process.on("close", (code, signal) => {
          log(`[MCPBridge] Server exited with code ${code} signal ${signal}`);
          this.lastExitSignal = signal ?? null;
          this.isConnected = false;
          this.connectionPromise = null;
          this.handleDisconnect();
        });

        this.process.on("error", (err) => {
          error("[MCPBridge] Process error:", err);
          this.isConnected = false;
          this.connectionPromise = null;
          this.emit("error", err);
        });

        // Wait for server initialization
        await this.waitForReady();
        this.isConnected = true;
        this.lastConnectTime = Date.now();
        log("[MCPBridge] Connected to MCP server");

        // Register cleanup handlers to prevent zombie processes
        this.registerCleanupHandlers();
      } catch (error) {
        this.connectionPromise = null;
        throw error;
      }
    })();

    return this.connectionPromise;
  }

  private resolveLaunchContract(): {
    preflight: PreflightContract;
    augurRoot: string;
    pythonCmd: string;
    clientId: string;
    signature: string;
  } {
    const preflight = resolvePreflightContract();
    const augurRoot = preflight.project_root || process.env.AUGUR_ROOT || AUGUR_ROOT;
    const pythonCmd = preflight.python_path || process.env.AUGUR_PYTHON || AUGUR_PYTHON;
    const clientId = scopeDashboardProcessClientId(
      preflight.mcp_client_id || resolveMcpClientId(),
    );
    const signature = JSON.stringify({
      augurRoot,
      pythonCmd,
      runtimeDir: preflight.runtime_dir || "",
      mcpPort: preflight.mcp_port || "",
      clientId,
    });

    return { preflight, augurRoot, pythonCmd, clientId, signature };
  }

  /**
   * Register process cleanup handlers for the parent Node process.
   * Delegates to the cleanup module for process-level handler registration.
   */
  private registerCleanupHandlers(): void {
    if (this.handlersRegistered) return;
    this.handlersRegistered = true;
    registerCleanupHandlers(this.process);
  }

  /**
   * Wait for server to be ready by sending initialize request
   */
  private async waitForReady(): Promise<void> {
    const maxAttempts = 10;
    const delayMs = 500;
    await this.waitForReadyAttempt(0, maxAttempts, delayMs);
  }

  private async waitForReadyAttempt(
    attempt: number,
    maxAttempts: number,
    delayMs: number,
  ): Promise<void> {
    try {
      await this.sendRequest("initialize", {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: {
          name: "augur-ui",
          version: "1.0.0",
        },
      });
    } catch {
      if (attempt >= maxAttempts - 1) {
        throw new Error("MCP server failed to initialize");
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      return this.waitForReadyAttempt(attempt + 1, maxAttempts, delayMs);
    }
  }

  /**
   * Handle incoming data from MCP server
   */
  private handleData(data: string): void {
    this.buffer += data;

    // Process complete JSON-RPC messages (newline-delimited)
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || ""; // Keep incomplete line in buffer

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const message = JSON.parse(line);
        this.handleMessage(message);
      } catch (err) {
        error("[MCPBridge] Failed to parse message:", line, err);
      }
    }
  }

  /**
   * Release one semaphore slot and unblock the next queued request, if any.
   */
  private releaseSlot(): void {
    this.activeRequests--;
    const next = this.requestQueue.shift();
    if (next) {
      next();
    }
  }

  /**
   * Handle parsed JSON-RPC message
   */
  private handleMessage(message: Record<string, unknown>): void {
    const id = message.id as number;

    if (id !== undefined && this.pendingRequests.has(id)) {
      const pending = this.pendingRequests.get(id)!;
      clearTimeout(pending.timeout);
      this.pendingRequests.delete(id);
      this.releaseSlot();

      if (message.error) {
        pending.reject(new Error(JSON.stringify(message.error)));
      } else {
        pending.resolve(message.result);
      }
    } else {
      // Server notification or unknown message
      this.emit("notification", message);
    }
  }

  /**
   * Handle server disconnect
   */
  private handleDisconnect(): void {
    // Reject all pending requests
    for (const [id, pending] of this.pendingRequests) {
      clearTimeout(pending.timeout);
      pending.reject(new Error("MCP server disconnected"));
    }
    this.pendingRequests.clear();

    // Reset semaphore — the connection is gone so in-flight count is meaningless.
    // Drain queued waiters with a rejection so callers don't hang indefinitely.
    this.activeRequests = 0;
    const queued = this.requestQueue.splice(0);
    for (const resolveSlot of queued) {
      // Resolving (not rejecting) the slot promise lets the caller proceed to
      // the "MCP server not connected" check at the top of sendRequest(), which
      // will throw the correct error rather than leaving promises unresolved.
      resolveSlot();
    }

    // Check stderr for permanent failures that make retries pointless
    const stderr = this.lastStderrOutput;
    const permanentError = diagnosePermanentFailure(stderr);

    if (permanentError) {
      this.permanentFailure = permanentError;
      this.reconnectAttemptLogs = []; // logs serve no purpose after giving up
      error(`[MCPBridge] ${permanentError}`);
      this.emit("permanent_failure", permanentError);
      return;
    }

    // Only reset reconnect counter if the connection was stable (survived >5s).
    // This prevents infinite loops where the server starts, responds to
    // initialize, then crashes immediately — resetting the counter each time.
    const uptime = Date.now() - this.lastConnectTime;
    if (uptime > MCPBridge.STABLE_CONNECTION_MS) {
      this.reconnectAttempts = 0;
      this.recoveryAttempts = 0; // stable connection resets all recovery state
      this.diagnosisAttempted = false; // allow diagnosis again after stable connection
      this.reconnectAttemptLogs = []; // ADR-106: reset logs on stable connection
    }

    // Attempt reconnection if within limit
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;

      // ADR-106: Track reconnect attempt for LLM diagnosis
      this.reconnectAttemptLogs.push({
        attempt: this.reconnectAttempts,
        error: `Disconnect after ${uptime}ms uptime, signal=${this.lastExitSignal}`,
        timestamp: new Date().toISOString(),
      });
      if (this.reconnectAttemptLogs.length > 50) {
        this.reconnectAttemptLogs.shift();
      }

      log(
        `[MCPBridge] Attempting reconnection (${this.reconnectAttempts}/${this.maxReconnectAttempts})`,
      );

      // ADR-106: Trigger async LLM diagnosis at trigger_attempt threshold
      this.tryLLMDiagnosis();

      // ADR-466: globalThis singleton guard prevents duplicate reconnect timers on HMR reload
      const RECONNECT_TIMER_KEY = '__mcp_reconnect_timer__';
      if ((globalThis as any)[RECONNECT_TIMER_KEY]) {
        clearTimeout((globalThis as any)[RECONNECT_TIMER_KEY]);
      }
      (globalThis as any)[RECONNECT_TIMER_KEY] = setTimeout(() => {
        (globalThis as any)[RECONNECT_TIMER_KEY] = null;
        this.connect().catch((err) => {
          error("[MCPBridge] Reconnect attempt failed:", err);
        });
      }, 2000);
    } else {
      // All quick reconnects exhausted — enter recovery mode with exponential backoff
      this.recoveryAttempts++;
      const canRecover =
        this.recoveryAttempts <= MCPBridge.MAX_RECOVERY_ATTEMPTS;

      error(
        `[MCPBridge] Max reconnection attempts reached (recovery ${this.recoveryAttempts}/${MCPBridge.MAX_RECOVERY_ATTEMPTS})`,
      );
      emitHealEvent({
        source: "MCPBridge",
        category: "mcp_reconnect_failed",
        severity: canRecover ? "high" : "critical",
        message: `MCP server failed ${this.maxReconnectAttempts} reconnection attempts (recovery cycle ${this.recoveryAttempts})`,
        context: {
          attempts: this.reconnectAttemptLogs,
          stderr: this.lastStderrOutput.slice(0, 500),
        },
      });
      this.emit("max_reconnect_failed");

      if (canRecover) {
        // Exponential backoff: 10s, 20s, 40s, 80s, 160s
        const delay =
          MCPBridge.RECOVERY_BASE_DELAY_MS *
          Math.pow(2, this.recoveryAttempts - 1);
        warn(`[MCPBridge] Scheduling recovery attempt in ${delay / 1000}s...`);
        // ADR-466: globalThis singleton guard prevents duplicate recovery timers on HMR reload
        const RECOVERY_TIMER_KEY = '__mcp_recovery_timer__';
        if ((globalThis as any)[RECOVERY_TIMER_KEY]) {
          clearTimeout((globalThis as any)[RECOVERY_TIMER_KEY]);
        }
        (globalThis as any)[RECOVERY_TIMER_KEY] = setTimeout(() => {
          (globalThis as any)[RECOVERY_TIMER_KEY] = null;
          log(
            `[MCPBridge] Recovery attempt ${this.recoveryAttempts} — resetting and reconnecting`,
          );
          this.reconnectAttempts = 0;
          this.diagnosisAttempted = false;
          this.reconnectAttemptLogs = [];
          this.connectionPromise = null;
          this.permanentFailure = null;
          this.lastStderrOutput = "";
          this.connect().catch((err) => {
            error("[MCPBridge] Recovery connect failed:", err);
          });
        }, delay);
      } else {
        error(
          "[MCPBridge] All recovery attempts exhausted — MCP bridge is down. Manual restart required.",
        );
      }
    }
  }

  /**
   * ADR-106: Trigger async LLM diagnosis when reconnect attempts hit threshold.
   * Delegates to diagnostics module. Non-blocking.
   */
  private tryLLMDiagnosis(): void {
    const attempted = tryLLMDiagnosis(
      this.reconnectAttempts,
      this.reconnectAttemptLogs,
      this.lastStderrOutput,
      this.diagnosisAttempted,
    );
    if (attempted) {
      this.diagnosisAttempted = true;
    }
  }

  /**
   * Send JSON-RPC request to MCP server.
   *
   * A semaphore (maxConcurrent = 10) gates how many requests may be in-flight
   * simultaneously. Requests beyond the limit are queued and admitted one at a
   * time as prior requests complete (resolve, reject, timeout, or write error).
   * This prevents the stdio pipe from being saturated with 50+ frames at once,
   * which would cause later requests to time out before the Python server even
   * starts processing them — triggering reconnect cascades.
   */
  private async sendRequest(method: string, params: unknown): Promise<unknown> {
    if (!this.process || !this.process.stdin) {
      throw new Error("MCP server not connected");
    }

    // Acquire semaphore slot — wait in queue if at capacity
    if (this.activeRequests >= this.maxConcurrent) {
      await new Promise<void>((resolveSlot) => {
        this.requestQueue.push(resolveSlot);
      });
    }
    this.activeRequests++;

    const id = ++this.requestId;
    const request = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    return new Promise((resolve, reject) => {
      // Per-request timeout — NOT a singleton. Cleanup is correct:
      // - success: clearTimeout in handleMessage() + releaseSlot()
      // - write error: clearTimeout below + releaseSlot()
      // - timeout: self-cleans via callback + pendingRequests.delete + releaseSlot()
      // - disconnect: clearTimeout in handleDisconnect() for all pending
      //   (handleDisconnect clears pendingRequests but does NOT release slots;
      //    the bridge is dead at that point so the queue will drain on reconnect)
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id);
        this.releaseSlot();
        reject(
          new Error(`Request ${id} timed out after ${this.requestTimeout}ms`),
        );
      }, this.requestTimeout);

      this.pendingRequests.set(id, { resolve, reject, timeout });

      const message = JSON.stringify(request) + "\n";
      this.process!.stdin!.write(message, (err) => {
        if (err) {
          clearTimeout(timeout);
          this.pendingRequests.delete(id);
          this.releaseSlot();
          reject(err);
        }
      });
    });
  }

  /**
   * Call MCP tool with arguments
   */
  public async callTool(
    toolName: string,
    args: Record<string, unknown> = {},
    context?: MCPServerContext,
  ): Promise<MCPToolResult> {
    if (!this.isConnected) {
      await this.connect();
    }

    // Note: context parameter is available but not sent to MCP tools
    // Tools use ContextInjector directly to access sprint/project context
    // MCP SDK doesn't allow parameter names starting with '_'

    try {
      const result = (await this.sendRequest("tools/call", {
        name: toolName,
        arguments: args,
      })) as MCPToolResult;

      return result;
    } catch (err) {
      // Retry once on transient disconnect — the bridge auto-reconnects
      const msg = err instanceof Error ? err.message : "";
      if (
        msg.includes("MCP server disconnected") ||
        msg.includes("MCP server not connected")
      ) {
        log(`[MCPBridge] Retrying ${toolName} after transient disconnect`);
        await this.connect();
        return (await this.sendRequest("tools/call", {
          name: toolName,
          arguments: args,
        })) as MCPToolResult;
      }
      throw err instanceof Error ? err : new Error(String(err));
    }
  }

  /**
   * List available MCP tools
   */
  public async listTools(): Promise<
    Array<{ name: string; description?: string; inputSchema?: unknown }>
  > {
    if (!this.isConnected) {
      await this.connect();
    }

    const result = (await this.sendRequest("tools/list", {})) as {
      tools: Array<{
        name: string;
        description?: string;
        inputSchema?: unknown;
      }>;
    };

    return result.tools || [];
  }

  /**
   * Get MCP server capabilities
   */
  public async getCapabilities(): Promise<Record<string, unknown>> {
    if (!this.isConnected) {
      await this.connect();
    }

    const result = (await this.sendRequest("capabilities", {})) as Record<
      string,
      unknown
    >;
    return result;
  }

  /**
   * Disconnect from MCP server
   */
  public async disconnect(): Promise<void> {
    if (this.process) {
      this.process.kill();
      this.process = null;
      this.isConnected = false;
      this.pendingRequests.clear();
      log("[MCPBridge] Disconnected from MCP server");
    }
  }

  /**
   * Force-reset all state and reconnect fresh.
   * Use after permanent failures or when the caller knows the server environment changed.
   */
  public async reconnect(): Promise<void> {
    if (this.process) {
      try {
        this.process.kill();
      } catch {}
      this.process = null;
    }
    this.isConnected = false;
    this.connectionPromise = null;
    this.reconnectAttempts = 0;
    this.permanentFailure = null;
    this.diagnosisAttempted = false;
    this.reconnectAttemptLogs = [];
    this.lastStderrOutput = "";
    this.lastExitSignal = null;
    await this.connect();
  }

  /**
   * Extract tool result text from MCP response
   */
  public static extractText(result: MCPToolResult): string {
    if (!result.content || result.content.length === 0) {
      return "";
    }

    return result.content
      .flatMap((item) => (item.type === "text" ? [item.text] : []))
      .join("\n");
  }

  /**
   * Parse JSON from tool result text
   */
  public static parseJSON<T = unknown>(result: MCPToolResult): T {
    const text = MCPBridge.extractText(result);

    // Debug logging removed to reduce noise

    try {
      return JSON.parse(text) as T;
    } catch (err) {
      // If the response is a plain string error (not JSON structure), throw as clean Error
      if (!text.startsWith("{") && !text.startsWith("[")) {
        throw new Error(text || "Empty MCP response");
      }

      error("[MCPBridge ERROR] JSON parse failed");
      error("[MCPBridge ERROR] Full text:", text);
      error("[MCPBridge ERROR] Error:", err);
      throw err instanceof Error ? err : new Error(String(err));
    }
  }

  private parseContextSwitchResult(result: MCPToolResult): ContextSwitchResult {
    const parsed = JSON.parse(
      MCPBridge.extractText(result),
    ) as ContextSwitchResult;
    if (!parsed.success) {
      throw new Error(parsed.error || "Context switch failed");
    }
    return parsed;
  }

  private completeContextSwitch(
    newPage: string,
    switchResult: ContextSwitchResult,
    duration: number,
  ): void {
    this.currentPage = newPage;

    const removedCount = Array.isArray(switchResult.removed)
      ? switchResult.removed.length
      : 0;
    const addedCount = Array.isArray(switchResult.added)
      ? switchResult.added.length
      : 0;

    log(
      `[MCPBridge] Context switched to ${newPage} in ${duration}ms`,
      `(${removedCount} removed, ${addedCount} added)`,
    );

    this.emit("context-changed", {
      page: newPage,
      activeCount: switchResult.active_count,
      duration,
      removed: switchResult.removed,
      added: switchResult.added,
    });
  }

  /**
   * Switch MCP context based on page navigation
   *
   * @param newPage - Target page path (e.g., "/brain", "/workforce")
   * @param preloaded - Whether tools were preloaded on hover
   */
  public async switchContext(
    newPage: string,
    preloaded: boolean = false,
  ): Promise<void> {
    if (this.toolSwitchInProgress) {
      log("[MCPBridge] Tool switch already in progress, queuing...");
      return;
    }

    if (this.currentPage === newPage) {
      return; // No change needed
    }

    this.toolSwitchInProgress = true;
    const startTime = Date.now();

    try {
      // Emit switching event
      this.emit("context-switching", { page: newPage });

      log(`[MCPBridge] Context switch: ${this.currentPage} → ${newPage}`);

      // Call MCP tool to switch context
      const result = await this.callTool("switch-mcp-context", {
        current_page: newPage,
        preloaded: preloaded,
      });
      const duration = Date.now() - startTime;
      const switchResult = this.parseContextSwitchResult(result);
      this.completeContextSwitch(newPage, switchResult, duration);
    } catch (err: any) {
      const duration = Date.now() - startTime;
      error("[MCPBridge] Context switch failed:", err);
      this.emit("context-switch-failed", {
        error: err,
        page: newPage,
        duration,
      });
      throw err instanceof Error ? err : new Error(String(err));
    } finally {
      this.toolSwitchInProgress = false;
    }
  }

  /**
   * Preload tools for a page (on hover)
   *
   * @param targetPage - Page to preload tools for
   */
  public async preloadContext(targetPage: string): Promise<void> {
    // Skip if already current page
    if (this.currentPage === targetPage) {
      return;
    }

    // Skip if already in preload queue
    if (this.preloadQueue.has(targetPage)) {
      return;
    }

    this.preloadQueue.add(targetPage);

    try {
      log(`[MCPBridge] Preloading context for ${targetPage}`);

      await this.callTool("preload-mcp-context", {
        target_page: targetPage,
      });

      log(`[MCPBridge] Preload complete for ${targetPage}`);
    } catch (error) {
      warn(`[MCPBridge] Preload failed for ${targetPage}:`, error);
    } finally {
      this.preloadQueue.delete(targetPage);
    }
  }

  /**
   * Get current page context
   */
  public getCurrentPage(): string {
    return this.currentPage;
  }

  /**
   * Check if context switch is in progress
   */
  public isContextSwitching(): boolean {
    return this.toolSwitchInProgress;
  }

  /**
   * Return internal state snapshot for the /api/mcp/debug route.
   * Keeps private fields private while exposing diagnostics.
   */
  public getDebugState(): Record<string, unknown> {
    return {
      isConnected: this.isConnected,
      permanentFailure: this.permanentFailure,
      reconnectAttempts: this.reconnectAttempts,
      recoveryAttempts: this.recoveryAttempts,
      hasProcess: !!this.process,
      processExited: this.process
        ? this.process.exitCode !== null
        : "no process",
      processPid: this.process?.pid ?? null,
      lastStderrOutput: this.lastStderrOutput?.slice(-500),
      lastExitSignal: this.lastExitSignal,
      connectionPromise: this.connectionPromise !== null,
      activeRequests: this.activeRequests,
      requestQueueLength: this.requestQueue?.length ?? 0,
      lastLaunchContract: this.lastLaunchContract,
    };
  }
}
