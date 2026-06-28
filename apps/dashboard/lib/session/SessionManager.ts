import fs from "fs";
import path from "path";
import {
  AUGUR_ROOT,
  buildCliSpawnEnv,
  extractOllamaRunModel,
  getCliAgentsConfig,
  isDirectOllamaCli,
  resolveDefaultCliId,
  resolveSpawnCommand,
  writeChatSession,
} from "@/app/api/cli/cli-config";
import {
  airplaneUnavailablePayload,
  applyAirplaneLaunchOverride,
  readAirplaneLaunchOverrides,
  readCanonicalAirplaneMode,
  type AirplaneLaunchOverrides,
} from "@/app/api/cli/airplane-routing";
import {
  type IPtyProcess,
  type PtyEntry,
  attachPtyHandlers,
  createPtyEntry,
  processes,
  pty,
} from "@/app/api/cli/pty-setup";
import { AUGUR_STATE_DIR } from "@/lib/paths";
import {
  claimDashboardSessionOwner,
  releaseDashboardSessionOwner,
} from "@/lib/session/sessionOwners";

const SESSION_ID_FILE = path.join(
  AUGUR_STATE_DIR,
  "temp",
  "default_cli_session_id.txt",
);
const SESSION_CLI_ID_FILE = path.join(
  AUGUR_STATE_DIR,
  "temp",
  "default_cli_session_cli.txt",
);

type CliConfig = {
  cmd?: unknown;
  cwd?: unknown;
  env?: Record<string, unknown>;
};

export interface SessionInitializeOptions {
  currentPage?: string;
  airplaneMode?: boolean;
  airplaneLocalModel?: string | null;
  themeMode?: "light" | "dark";
}

interface SessionLaunchOptions {
  airplaneMode: boolean;
  airplaneLocalModel: string | null;
  themeMode?: "light" | "dark";
}

export interface TerminalHandoffSnapshot {
  cliId: string;
  pid: number;
  sessionId: string;
  cwd: string;
  airplaneMode: boolean;
  airplaneLocalModel: string | null;
  themeMode?: "light" | "dark";
}

export interface TerminalHandoffExitOptions {
  timeoutMs?: number;
  pollMs?: number;
}

export interface TrackCliProcessOptions {
  cliId: string;
  ptyProcess: IPtyProcess;
  sessionId?: string | null;
  clearSessionId?: boolean;
  airplaneMode: boolean;
  airplaneLocalModel: string | null;
  themeMode?: "light" | "dark";
}

export type TerminalHandoffExitResult =
  | { ok: true }
  | { ok: false; reason: "no_running_session" | "exit_timeout" };

function readSessionIdFromDisk(): string | null {
  try {
    if (!fs.existsSync(SESSION_ID_FILE)) {
      return null;
    }

    const value = fs.readFileSync(SESSION_ID_FILE, "utf8").trim();
    return value.length > 0 ? value : null;
  } catch {
    return null;
  }
}

function readSessionCliIdFromDisk(): string | null {
  try {
    if (!fs.existsSync(SESSION_CLI_ID_FILE)) {
      return null;
    }

    const value = fs.readFileSync(SESSION_CLI_ID_FILE, "utf8").trim();
    return value.length > 0 ? value : null;
  } catch {
    return null;
  }
}

function writeSessionIdToDisk(id: string, cliId: string | null): void {
  try {
    const dir = path.dirname(SESSION_ID_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(SESSION_ID_FILE, id, "utf8");
    if (cliId) {
      fs.writeFileSync(SESSION_CLI_ID_FILE, cliId, "utf8");
    } else if (fs.existsSync(SESSION_CLI_ID_FILE)) {
      fs.unlinkSync(SESSION_CLI_ID_FILE);
    }
  } catch {
    // Best-effort state persistence. Session startup must continue.
  }
}

function clearSessionIdOnDisk(): void {
  try {
    if (fs.existsSync(SESSION_ID_FILE)) {
      fs.unlinkSync(SESSION_ID_FILE);
    }
    if (fs.existsSync(SESSION_CLI_ID_FILE)) {
      fs.unlinkSync(SESSION_CLI_ID_FILE);
    }
  } catch {
    // Best-effort state persistence. Session startup must continue.
  }
}

function normalizeCliId(value: string | null | undefined): string | null {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : null;
}

function readCmdArray(config: CliConfig): string[] {
  if (!Array.isArray(config.cmd) || config.cmd.length === 0) {
    throw new Error("CLI config must define a non-empty cmd array");
  }

  return config.cmd.map((value) => {
    if (typeof value !== "string" || value.length === 0) {
      throw new Error("CLI config cmd entries must be non-empty strings");
    }
    return value;
  });
}

function resolveCwd(config: CliConfig): string {
  const cwd = config.cwd;
  if (typeof cwd === "string" && cwd.length > 0) {
    return path.isAbsolute(cwd) ? cwd : path.resolve(AUGUR_ROOT, cwd);
  }

  return AUGUR_ROOT;
}

function buildResumeCmdArgs(
  cliId: string,
  config: CliConfig,
  lastSessionId: string | null,
): { command: string; args: string[] } {
  const cmd = readCmdArray(config);
  const binary = path.basename(cmd[0]);
  if (!lastSessionId) {
    return { command: cmd[0], args: cmd.slice(1) };
  }

  if (cliId === "codex" || binary === "codex") {
    return {
      command: cmd[0],
      args: ["resume", lastSessionId, ...cmd.slice(1)],
    };
  }

  return { command: cmd[0], args: cmd.slice(1) };
}

function supportsPersistedResume(cliId: string, config: CliConfig): boolean {
  try {
    const cmd = readCmdArray(config);
    const binary = path.basename(cmd[0]);
    return cliId === "codex" || binary === "codex";
  } catch {
    return false;
  }
}

function isResumableCli(cliId: string, config: CliConfig): boolean {
  try {
    const cmd = readCmdArray(config);
    const binary = path.basename(cmd[0]);
    return (
      cliId === "codex" ||
      binary === "codex" ||
      cliId === "claude" ||
      cliId.startsWith("claude-") ||
      binary === "claude"
    );
  } catch {
    return false;
  }
}

function buildAirplaneUnavailableError(
  overrides: AirplaneLaunchOverrides | undefined,
): Error {
  const payload = airplaneUnavailablePayload(overrides);
  return new Error(
    `${payload.error}. reason=${payload.reason}. setup_hint=${payload.setup_hint}`,
  );
}

function normalizeLocalModel(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

function extractAirplaneLaunchModel(
  overrides: AirplaneLaunchOverrides | undefined,
): string | null {
  const launchArgv = overrides?.launch_argv;
  if (!Array.isArray(launchArgv)) {
    return null;
  }
  const modelFlagIndex = launchArgv.findIndex((arg) => arg === "--model");
  const model =
    modelFlagIndex >= 0 ? launchArgv[modelFlagIndex + 1] : undefined;
  return normalizeLocalModel(model) ?? null;
}

function extractDirectOllamaModel(cliId: string, config: CliConfig | undefined): string | null {
  if (!config || !isDirectOllamaCli(cliId)) {
    return null;
  }
  return extractOllamaRunModel(config.cmd);
}

export class SessionManager {
  private proc: IPtyProcess | null = null;
  private cliId: string | null = null;
  private conversationActive = false;
  private activeCliIds = new Set<string>();
  private launchOptions: SessionLaunchOptions | null = null;
  private lastSessionId: string | null;
  private lastSessionCliId: string | null;

  constructor() {
    this.lastSessionId = readSessionIdFromDisk();
    this.lastSessionCliId = readSessionCliIdFromDisk();
  }

  isRunning(): boolean {
    if (!this.proc) {
      return false;
    }

    if (!this.cliId) {
      this.clearRuntimeState();
      return false;
    }

    const entry = processes.get(this.cliId);
    if (!entry || entry.exited || entry.ptyProcess !== this.proc) {
      this.clearRuntimeState();
      return false;
    }

    return true;
  }

  getCliId(): string | null {
    return this.cliId;
  }

  getPid(): number | null {
    return this.isRunning() ? this.proc?.pid ?? null : null;
  }

  getLastSessionId(cliId?: string | null): string | null {
    const targetCliId = normalizeCliId(cliId);
    if (targetCliId && this.lastSessionCliId !== targetCliId) {
      return null;
    }
    return this.lastSessionId;
  }

  /**
   * Backend the currently-tracked session is actually running on, derived from
   * the options it was launched with. Lets the UI show the live backend instead
   * of the toggled airplane preference (which may not have been applied yet).
   */
  getActiveBackend(): {
    running: boolean;
    cliId: string | null;
    airplaneMode: boolean;
    localModel: string | null;
  } {
    const running = this.isRunning();
    return {
      running,
      cliId: running ? this.cliId : null,
      airplaneMode: running ? this.launchOptions?.airplaneMode === true : false,
      localModel: running ? this.launchOptions?.airplaneLocalModel ?? null : null,
    };
  }

  private annotatePtyEntry(cliId: string, entry: PtyEntry): void {
    entry.cliId = cliId;
    entry.sessionId = this.getLastSessionId(cliId);
    entry.airplaneMode = this.launchOptions?.airplaneMode === true;
    entry.airplaneLocalModel = this.launchOptions?.airplaneLocalModel ?? null;
    entry.themeMode = this.launchOptions?.themeMode;
  }

  private recoverRunningProcessFromRegistry(): boolean {
    const candidates = Array.from(processes.entries()).filter(
      ([, entry]) => !entry.exited,
    );
    if (candidates.length === 0) {
      return false;
    }

    const persistedCliId = normalizeCliId(this.lastSessionCliId);
    const selected = persistedCliId
      ? candidates.find(([cliId]) => cliId === persistedCliId)
      : candidates.length === 1
        ? candidates[0]
        : undefined;
    if (!selected) {
      return false;
    }

    const [cliId, entry] = selected;
    if (typeof entry.ptyProcess.pid !== "number") {
      return false;
    }

    this.proc = entry.ptyProcess;
    this.cliId = cliId;
    this.conversationActive = false;
    this.activeCliIds.add(cliId);
    this.launchOptions = {
      airplaneMode: entry.airplaneMode === true,
      airplaneLocalModel:
        typeof entry.airplaneLocalModel === "string"
          ? entry.airplaneLocalModel
          : null,
      themeMode: entry.themeMode,
    };
    this.annotatePtyEntry(cliId, entry);
    return true;
  }

  private ensureRunningForTerminalHandoff(): boolean {
    return this.isRunning() || this.recoverRunningProcessFromRegistry();
  }

  getTerminalHandoffSnapshot(): TerminalHandoffSnapshot | null {
    if (!this.ensureRunningForTerminalHandoff() || !this.cliId || !this.proc) {
      return null;
    }
    const sessionId = this.getLastSessionId(this.cliId);
    if (!sessionId) {
      return null;
    }

    if (typeof this.proc.pid !== "number") {
      return null;
    }

    const agents = getCliAgentsConfig() as Record<string, CliConfig>;
    const config = agents[this.cliId];
    if (!config || !isResumableCli(this.cliId, config)) {
      return null;
    }

    return {
      cliId: this.cliId,
      pid: this.proc.pid,
      sessionId,
      cwd: resolveCwd(config),
      airplaneMode: this.launchOptions?.airplaneMode === true,
      airplaneLocalModel: this.launchOptions?.airplaneLocalModel ?? null,
      themeMode: this.launchOptions?.themeMode,
    };
  }

  async exitForTerminalHandoff(
    options: TerminalHandoffExitOptions = {},
  ): Promise<TerminalHandoffExitResult> {
    if (!this.isRunning() || !this.cliId || !this.proc) {
      return { ok: false, reason: "no_running_session" };
    }

    const timeoutMs = options.timeoutMs ?? 5000;
    const pollMs = options.pollMs ?? 100;
    const cliId = this.cliId;
    const proc = this.proc;
    proc.write("exit");
    proc.write("\r");

    const deadline = Date.now() + timeoutMs;
    return this.waitForTerminalHandoffExit(cliId, proc, deadline, pollMs);
  }

  private async waitForTerminalHandoffExit(
    cliId: string,
    proc: IPtyProcess,
    deadline: number,
    pollMs: number,
  ): Promise<TerminalHandoffExitResult> {
    if (Date.now() >= deadline) {
      return { ok: false, reason: "exit_timeout" };
    }

    const current = processes.get(cliId);
    if (!current || current.exited || current.ptyProcess !== proc) {
      if (current?.detachTimer) {
        clearTimeout(current.detachTimer);
        current.detachTimer = null;
      }
      await this.releaseDashboardOwnerFor(this.getLastSessionId(cliId), proc.pid);
      this.markCliStopped(cliId);
      writeChatSession({ isActive: false, status: "idle", context: {} });
      return { ok: true };
    }

    await new Promise((resolve) => setTimeout(resolve, pollMs));
    return this.waitForTerminalHandoffExit(cliId, proc, deadline, pollMs);
  }

  async shouldRestartForOptions(
    options: SessionInitializeOptions = {},
  ): Promise<boolean> {
    if (!this.isRunning() || this.hasActiveConversation()) {
      return false;
    }

    const airplaneMode = await readCanonicalAirplaneMode();
    if (this.launchOptions?.airplaneMode !== airplaneMode) {
      return true;
    }

    if (!airplaneMode) {
      return false;
    }

    const hintedLocalModel = normalizeLocalModel(options.airplaneLocalModel);
    let currentLocalModel: string | null | undefined = hintedLocalModel;
    if (currentLocalModel === undefined) {
      const cliId = this.cliId ?? this.resolveDefaultCliId();
      if (!cliId) {
        return false;
      }
      const agents = getCliAgentsConfig() as Record<string, CliConfig>;
      const directOllamaModel = extractDirectOllamaModel(cliId, agents[cliId]);
      if (directOllamaModel) {
        currentLocalModel = directOllamaModel;
      } else {
        const airplaneOverrides = await readAirplaneLaunchOverrides(cliId);
        if (airplaneOverrides.ready !== true) {
          return false;
        }
        currentLocalModel = extractAirplaneLaunchModel(airplaneOverrides);
      }
    }

    return this.launchOptions?.airplaneLocalModel !== currentLocalModel;
  }

  saveSessionId(id: string, cliId?: string | null): void {
    this.lastSessionId = id;
    this.lastSessionCliId = normalizeCliId(cliId);
    writeSessionIdToDisk(id, this.lastSessionCliId);
  }

  private clearSessionIdFor(cliId: string): void {
    if (this.lastSessionCliId !== cliId) {
      return;
    }
    this.lastSessionId = null;
    this.lastSessionCliId = null;
    clearSessionIdOnDisk();
  }

  trackCliProcess(options: TrackCliProcessOptions): void {
    this.proc = options.ptyProcess;
    this.cliId = options.cliId;
    this.conversationActive = false;
    this.activeCliIds.delete(options.cliId);
    this.launchOptions = {
      airplaneMode: options.airplaneMode,
      airplaneLocalModel: options.airplaneLocalModel,
      themeMode: options.themeMode,
    };

    const sessionId =
      typeof options.sessionId === "string" ? options.sessionId.trim() : "";
    if (sessionId.length > 0) {
      this.saveSessionId(sessionId, options.cliId);
    } else if (options.clearSessionId !== false) {
      this.lastSessionId = null;
      this.lastSessionCliId = null;
      clearSessionIdOnDisk();
    }

    const entry = processes.get(options.cliId);
    if (entry && entry.ptyProcess === options.ptyProcess) {
      this.annotatePtyEntry(options.cliId, entry);
    }
  }

  private async claimDashboardOwner(cliId: string, proc: IPtyProcess): Promise<void> {
    const sessionId = this.getLastSessionId(cliId);
    if (!sessionId || typeof proc.pid !== "number") {
      return;
    }
    await claimDashboardSessionOwner({
      cliId,
      pid: proc.pid,
      sessionId,
    });
  }

  private releaseDashboardOwner(): void {
    const sessionId = this.getLastSessionId(this.cliId);
    if (!sessionId || typeof this.proc?.pid !== "number") {
      return;
    }
    const pid = this.proc.pid;
    void releaseDashboardSessionOwner({ sessionId, pid }).catch((error) => {
      console.warn("[SessionManager] failed to release dashboard session owner", error);
    });
  }

  private async releaseDashboardOwnerFor(
    sessionId: string | null,
    pid: number | null,
  ): Promise<void> {
    if (!sessionId || typeof pid !== "number") {
      return;
    }
    try {
      await releaseDashboardSessionOwner({ sessionId, pid });
    } catch (error) {
      console.warn("[SessionManager] failed to release dashboard session owner", error);
    }
  }

  hasActiveConversation(): boolean {
    for (const cliId of [...this.activeCliIds]) {
      const entry = processes.get(cliId);
      if (entry && !entry.exited) {
        return true;
      }
      this.activeCliIds.delete(cliId);
    }

    if (!this.conversationActive) {
      return false;
    }

    const cliId = this.cliId ?? this.resolveDefaultCliId();
    if (!cliId) {
      this.conversationActive = false;
      return false;
    }

    const entry = processes.get(cliId);
    const hasLiveProcess = entry ? !entry.exited : this.proc !== null;
    if (!hasLiveProcess) {
      this.conversationActive = false;
      return false;
    }

    if (this.conversationActive) {
      return true;
    }

    return this.proc === null;
  }

  markConversationActive(): void {
    this.conversationActive = true;
    const cliId = this.cliId ?? this.resolveDefaultCliId();
    if (cliId) {
      this.activeCliIds.add(cliId);
    }
  }

  markCliActivity(cliId: string): void {
    if (cliId.startsWith("agent-bubble-")) {
      return;
    }

    this.activeCliIds.add(cliId);
    this.conversationActive = true;
  }

  markConversationIdle(): void {
    this.conversationActive = false;
    if (this.cliId) {
      this.activeCliIds.delete(this.cliId);
    }
  }

  markCliStopped(cliId: string): boolean {
    const wasActive = this.activeCliIds.delete(cliId);
    const trackedCliId = this.cliId ?? this.resolveDefaultCliId();
    const wasTracked = trackedCliId === cliId;

    if (wasTracked) {
      this.clearRuntimeState();
    } else if (wasActive && this.activeCliIds.size === 0) {
      this.conversationActive = false;
    }

    return (wasActive || wasTracked) && !this.hasActiveConversation();
  }

  terminateActiveConversations(): void {
    const activeCliIds = [...this.activeCliIds];

    for (const cliId of activeCliIds) {
      const entry = processes.get(cliId);
      if (!entry || entry.exited) {
        this.activeCliIds.delete(cliId);
        continue;
      }

      try {
        if (entry.detachTimer) {
          clearTimeout(entry.detachTimer);
          entry.detachTimer = null;
        }
        entry.ptyProcess.kill();
      } catch {
        // Best-effort shutdown.
      }
      processes.delete(cliId);

      if (this.cliId === cliId) {
        this.clearRuntimeState();
      } else {
        this.activeCliIds.delete(cliId);
      }
    }

    if (this.activeCliIds.size === 0) {
      this.conversationActive = false;
    }
  }

  private clearRuntimeState(): void {
    this.releaseDashboardOwner();
    if (this.cliId) {
      this.activeCliIds.delete(this.cliId);
    }
    this.proc = null;
    this.cliId = null;
    this.conversationActive = false;
    this.launchOptions = null;
  }

  private resolveDefaultCliId(): string | null {
    try {
      const cliId = resolveDefaultCliId(
        getCliAgentsConfig() as Record<string, CliConfig>,
      );
      return cliId || null;
    } catch {
      return null;
    }
  }

  async initialize(options: SessionInitializeOptions = {}): Promise<void> {
    if (this.proc) {
      return;
    }

    const agents = getCliAgentsConfig() as Record<string, CliConfig>;
    const cliId = resolveDefaultCliId(agents);
    const config = agents[cliId];
    if (!config) {
      throw new Error(`CLI '${cliId}' not found in cli_agents.yaml`);
    }

    const airplaneMode = await readCanonicalAirplaneMode();
    const directOllamaModel = extractDirectOllamaModel(cliId, config);
    const existing = processes.get(cliId);
    if (existing && !existing.exited) {
      await this.claimDashboardOwner(cliId, existing.ptyProcess);
      this.proc = existing.ptyProcess;
      this.cliId = cliId;
      this.conversationActive = false;
      this.launchOptions = {
        airplaneMode,
        airplaneLocalModel:
          airplaneMode
            ? normalizeLocalModel(options.airplaneLocalModel) ?? directOllamaModel
            : null,
        themeMode: options.themeMode,
      };
      writeChatSession({
        isActive: true,
        status: "running",
        context: {
          current_page: options.currentPage ?? "dashboard",
          cliId,
          airplaneMode,
        },
      });
      return;
    }

    if (existing) {
      processes.delete(cliId);
    }

    let airplaneOverrides: AirplaneLaunchOverrides | undefined;
    let airplaneLocalModel =
      airplaneMode ? normalizeLocalModel(options.airplaneLocalModel) ?? null : null;
    if (airplaneMode && directOllamaModel) {
      airplaneLocalModel = directOllamaModel;
    } else if (airplaneMode) {
      airplaneOverrides = await readAirplaneLaunchOverrides(cliId);
      if (airplaneOverrides.ready !== true) {
        throw buildAirplaneUnavailableError(airplaneOverrides);
      }
      airplaneLocalModel =
        extractAirplaneLaunchModel(airplaneOverrides) ?? airplaneLocalModel;
    }

    const persistedResumeSessionId = supportsPersistedResume(cliId, config)
      ? this.getLastSessionId(cliId)
      : null;
    if (!persistedResumeSessionId) {
      this.clearSessionIdFor(cliId);
    }
    const resumeArgv = buildResumeCmdArgs(
      cliId,
      config,
      persistedResumeSessionId,
    );
    const spawnArgv = applyAirplaneLaunchOverride(
      resumeArgv.command,
      resumeArgv.args,
      airplaneOverrides,
    );
    const command = resolveSpawnCommand(spawnArgv.command);
    const args = spawnArgv.args;

    const env = buildCliSpawnEnv(config, options.currentPage, options.themeMode);
    const cwd = resolveCwd(config);
    const sessionContext: Record<string, unknown> = {
      current_page: options.currentPage ?? "dashboard",
      cliId,
      airplaneMode,
    };

    this.conversationActive = false;
    writeChatSession({
      isActive: true,
      status: "running",
      context: sessionContext,
    });

    let spawned: IPtyProcess | null = null;
    try {
      // @spawn-exempt: interactive CLI/PTY session (the terminal feature) — a live
      // bidirectional terminal cannot be a request/response MCP tool. See ADR-817.
      spawned = pty.spawn(command, args, {
        name: "xterm-256color",
        cols: 200,
        rows: 50,
        cwd,
        env,
      });
      await this.claimDashboardOwner(cliId, spawned);
      this.proc = spawned;
      this.cliId = cliId;
      this.launchOptions = {
        airplaneMode,
        airplaneLocalModel,
        themeMode: options.themeMode,
      };

      const entry = createPtyEntry(this.proc);
      this.annotatePtyEntry(cliId, entry);
      attachPtyHandlers(entry);
      processes.set(cliId, entry);

      this.proc.onExit(() => {
        this.clearRuntimeState();
        writeChatSession({ isActive: false, status: "idle", context: {} });
      });
    } catch (error) {
      try {
        spawned?.kill();
      } catch {
        // Best-effort cleanup after failed ownership claim or spawn.
      }
      writeChatSession({ isActive: false, status: "idle", context: {} });
      throw error;
    }
  }

  sendMessage(text: string): void {
    if (!this.isRunning() || !this.proc) {
      throw new Error("Session is not running");
    }

    this.proc.write(text);
    this.proc.write("\r");
    this.conversationActive = true;
    if (this.cliId) {
      this.activeCliIds.add(this.cliId);
    }
  }

  terminate(): void {
    const cliId = this.cliId ?? this.resolveDefaultCliId();
    const entry = cliId ? processes.get(cliId) : null;
    const proc = this.proc ?? entry?.ptyProcess ?? null;

    if (proc) {
      try {
        if (entry?.detachTimer) {
          clearTimeout(entry.detachTimer);
          entry.detachTimer = null;
        }
        proc.kill();
        if (cliId && entry?.ptyProcess === proc) {
          processes.delete(cliId);
        }
      } catch {
        // Best-effort shutdown.
      }
    }

    this.clearRuntimeState();
    writeChatSession({ isActive: false, status: "idle", context: {} });
  }
}

let sessionManagerSingleton: SessionManager | null = null;

export function getSessionManager(): SessionManager {
  if (!sessionManagerSingleton) {
    sessionManagerSingleton = new SessionManager();
  }

  return sessionManagerSingleton;
}
