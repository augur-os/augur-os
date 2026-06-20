/** @jest-environment node */

const mockWrite = jest.fn();

jest.mock("@/app/api/cli/pty-setup", () => ({
  PTY_SPAWN_HELPER: { path: "/mock/spawn-helper", exists: true },
  attachPtyHandlers: jest.fn(),
  createPtyEntry: jest.fn(),
  detachSession: jest.fn(),
  processes: new Map(),
  pty: {
    spawn: jest.fn(),
  },
  ptyHealthy: true,
  setPtyHealthy: jest.fn(),
}));

jest.mock("@/app/api/cli/cli-config", () => ({
  AUGUR_ROOT: "/augur/root",
  buildCliSpawnEnv: jest.fn(() => ({})),
  getCliConfigOrThrow: jest.fn((cliId: string) => ({
    cmd: [cliId === "codex" ? "codex" : cliId === "gemini" ? "gemini" : "claude"],
    cwd: "/augur/root",
  })),
  extractOllamaRunModel: (cmd: unknown) =>
    Array.isArray(cmd) &&
    cmd[0] === "ollama" &&
    cmd[1] === "run" &&
    typeof cmd[2] === "string"
      ? cmd[2]
      : null,
  isDirectOllamaCli: (cliId: string) => cliId === "ollama",
  isNonEmptyString: (value: unknown) =>
    typeof value === "string" && value.trim().length > 0,
  isValidCli: () => true,
  resolveConfigKey: (cliId: string) => cliId,
  resolveSpawnCommand: (cmd: string) => cmd,
  writeChatSession: jest.fn(),
}));

jest.mock("@/app/api/cli/airplane-routing", () => ({
  airplaneUnavailablePayload: jest.fn(),
  applyAirplaneLaunchOverride: jest.fn((command: string, args: string[]) => ({
    command,
    args,
  })),
  readAirplaneLaunchOverrides: jest.fn(),
  readCanonicalAirplaneMode: jest.fn(async () => false),
}));

jest.mock("@/lib/session/SessionManager", () => ({
  __mockSessionManager: {
    getLastSessionId: jest.fn(),
    markConversationActive: jest.fn(),
    markConversationIdle: jest.fn(),
    markCliActivity: jest.fn(),
    markCliStopped: jest.fn(),
    trackCliProcess: jest.fn(),
  },
  getSessionManager: () =>
    jest.requireMock("@/lib/session/SessionManager").__mockSessionManager,
}));

const mockClaimDashboardSessionOwner = jest.fn();
const mockReleaseDashboardSessionOwner = jest.fn();
const mockReleaseSessionOwner = jest.fn();

jest.mock("@/lib/session/sessionOwners", () => ({
  SessionOwnerConflictError: class SessionOwnerConflictError extends Error {},
  claimDashboardSessionOwner: (...args: unknown[]) =>
    mockClaimDashboardSessionOwner(...args),
  releaseDashboardSessionOwner: (...args: unknown[]) =>
    mockReleaseDashboardSessionOwner(...args),
  releaseSessionOwner: (...args: unknown[]) =>
    mockReleaseSessionOwner(...args),
  isSessionOwnerConflictError: (error: unknown) =>
    Boolean(
      error &&
        typeof error === "object" &&
        "owner" in error &&
        (error as { code?: string }).code === "SESSION_OWNED_ELSEWHERE",
    ),
  sessionOwnerConflictPayload: (
    sessionId: string,
    owner: Record<string, unknown>,
  ) => ({
    code: "SESSION_OWNED_ELSEWHERE",
    error: "Session is already open elsewhere.",
    owner,
    sessionId,
  }),
}));

import { CLI_ACTION_HANDLERS } from "@/app/api/cli/actions";

const mockProcesses = jest.requireMock("@/app/api/cli/pty-setup")
  .processes as Map<string, Record<string, unknown>>;
const mockPtySetup = jest.requireMock("@/app/api/cli/pty-setup") as {
  createPtyEntry: jest.Mock;
  pty: { spawn: jest.Mock };
};
const mockSessionManager = jest.requireMock("@/lib/session/SessionManager")
  .__mockSessionManager as {
    getLastSessionId: jest.Mock;
    markConversationActive: jest.Mock;
    markConversationIdle: jest.Mock;
    markCliActivity: jest.Mock;
    markCliStopped: jest.Mock;
    trackCliProcess: jest.Mock;
  };
const mockWriteChatSession = jest.requireMock("@/app/api/cli/cli-config")
  .writeChatSession as jest.Mock;

describe("CLI action handlers", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockProcesses.clear();
    mockClaimDashboardSessionOwner.mockReset();
    mockReleaseDashboardSessionOwner.mockReset();
    mockReleaseSessionOwner.mockReset();
    mockClaimDashboardSessionOwner.mockResolvedValue(undefined);
    mockReleaseDashboardSessionOwner.mockResolvedValue(true);
    mockReleaseSessionOwner.mockResolvedValue(true);
    mockSessionManager.getLastSessionId.mockReturnValue(null);
    mockSessionManager.markCliStopped.mockReturnValue(true);
    mockPtySetup.pty.spawn.mockReset();
    mockPtySetup.createPtyEntry.mockReset();
    mockPtySetup.createPtyEntry.mockImplementation((ptyProcess) => ({
      detached: false,
      detachTimer: null,
      exited: false,
      ptyProcess,
    }));
    mockProcesses.set("claude", {
      exited: false,
      ptyProcess: {
        kill: jest.fn(),
        pid: 1234,
        write: mockWrite,
      },
    });
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("tracks started Claude PTYs with a resumable session id for terminal handoff", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 2468,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
    });

    await expect(response.json()).resolves.toMatchObject({
      cliId: "claude",
      status: "running",
      pid: 2468,
    });
    const spawnArgs = mockPtySetup.pty.spawn.mock.calls[0][1] as string[];
    const sessionIdFlagIndex = spawnArgs.indexOf("--session-id");
    expect(sessionIdFlagIndex).toBeGreaterThanOrEqual(0);
    const sessionId = spawnArgs[sessionIdFlagIndex + 1];
    expect(sessionId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith({
      cliId: "claude",
      ptyProcess,
      sessionId,
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
    expect(mockClaimDashboardSessionOwner).toHaveBeenCalledWith({
      cliId: "claude",
      pid: 2468,
      sessionId,
    });
  });

  it("tracks started Codex PTYs with a latest-session resume marker", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 3579,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);

    const response = await CLI_ACTION_HANDLERS.start("codex", {
      action: "start",
      cliId: "codex",
      current_page: "/browse",
      themeMode: "dark",
    });

    await expect(response.json()).resolves.toMatchObject({
      cliId: "codex",
      status: "running",
      pid: 3579,
    });
    const spawnArgs = mockPtySetup.pty.spawn.mock.calls[0][1] as string[];
    expect(spawnArgs).not.toContain("--session-id");
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith({
      cliId: "codex",
      ptyProcess,
      sessionId: "__codex_latest__",
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
    expect(mockClaimDashboardSessionOwner).toHaveBeenCalledWith({
      cliId: "codex",
      pid: 3579,
      sessionId: "__codex_latest__",
    });
  });

  it("does not resume a session id that belongs to another CLI", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 2468,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);
    mockSessionManager.getLastSessionId.mockImplementation((cliId?: string) =>
      cliId === "claude" ? null : "__codex_latest__",
    );

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
    });

    await expect(response.json()).resolves.toMatchObject({
      cliId: "claude",
      status: "running",
      pid: 2468,
    });
    expect(mockSessionManager.getLastSessionId).toHaveBeenCalledWith("claude");
    const spawnArgs = mockPtySetup.pty.spawn.mock.calls[0][1] as string[];
    expect(spawnArgs).not.toContain("--resume");
    expect(spawnArgs).not.toContain("__codex_latest__");
    expect(spawnArgs).toContain("--session-id");
  });

  it("does not resume stale Gemini session ids because Gemini rejects missing session files", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 1357,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);
    mockSessionManager.getLastSessionId.mockImplementation((cliId?: string) =>
      cliId === "gemini" ? "8bbb3ab7-c4b3-489a-a74e-cd01480777f5" : null,
    );

    const response = await CLI_ACTION_HANDLERS.start("gemini", {
      action: "start",
      cliId: "gemini",
      current_page: "/browse",
      themeMode: "dark",
    });

    await expect(response.json()).resolves.toMatchObject({
      cliId: "gemini",
      status: "running",
      pid: 1357,
    });
    const spawnArgs = mockPtySetup.pty.spawn.mock.calls[0][1] as string[];
    expect(spawnArgs).not.toContain("--resume");
    expect(spawnArgs).not.toContain("--session-id");
    expect(spawnArgs).not.toContain("8bbb3ab7-c4b3-489a-a74e-cd01480777f5");
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith({
      cliId: "gemini",
      ptyProcess,
      sessionId: null,
      clearSessionId: true,
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
  });

  it("does not resume stale Claude session ids because Claude exits when the session file is missing", async () => {
    const staleSessionId = "dbed3159-a334-4672-a8d5-32c0b693eb1c";
    const ptyProcess = {
      kill: jest.fn(),
      pid: 2469,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);
    mockSessionManager.getLastSessionId.mockImplementation((cliId?: string) =>
      cliId === "claude" ? staleSessionId : null,
    );

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
    });

    await expect(response.json()).resolves.toMatchObject({
      cliId: "claude",
      status: "running",
      pid: 2469,
    });
    const spawnArgs = mockPtySetup.pty.spawn.mock.calls[0][1] as string[];
    const sessionIdIndex = spawnArgs.indexOf("--session-id");
    expect(spawnArgs).not.toContain("--resume");
    expect(spawnArgs).not.toContain(staleSessionId);
    expect(sessionIdIndex).toBeGreaterThanOrEqual(0);
    expect(spawnArgs[sessionIdIndex + 1]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith({
      cliId: "claude",
      ptyProcess,
      sessionId: spawnArgs[sessionIdIndex + 1],
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
  });

  it("returns a conflict and kills a duplicate PTY when another owner has the session", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 2468,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);
    mockClaimDashboardSessionOwner.mockRejectedValueOnce({
      code: "SESSION_OWNED_ELSEWHERE",
      owner: {
        session_id: "session-123",
        surface: "native-terminal",
        pid: 9999,
        host: "other-host",
        cli_id: "claude",
      },
    });

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
    });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "SESSION_OWNED_ELSEWHERE",
      owner: {
        surface: "native-terminal",
        pid: 9999,
        host: "other-host",
      },
    });
    expect(ptyProcess.kill).toHaveBeenCalledTimes(1);
    expect(mockProcesses.has("claude")).toBe(false);
    expect(mockSessionManager.trackCliProcess).not.toHaveBeenCalled();
    expect(mockWriteChatSession).toHaveBeenLastCalledWith({
      isActive: false,
      status: "idle",
      context: {},
    });
  });

  it("releases the existing owner and retries the dashboard claim when takeover is requested", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 2468,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);
    mockClaimDashboardSessionOwner
      .mockRejectedValueOnce({
        code: "SESSION_OWNED_ELSEWHERE",
        owner: {
          session_id: "session-123",
          surface: "native-terminal",
          pid: 9999,
          host: "other-host",
          cli_id: "claude",
        },
      })
      .mockResolvedValueOnce(undefined);
    mockSessionManager.getLastSessionId.mockReturnValue("session-123");

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
      takeOverSessionOwner: true,
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      cliId: "claude",
      status: "running",
      pid: 2468,
    });
    const claimedSessionId =
      mockClaimDashboardSessionOwner.mock.calls[0][0].sessionId;
    expect(claimedSessionId).not.toBe("session-123");
    expect(mockReleaseSessionOwner).toHaveBeenCalledWith({
      sessionId: claimedSessionId,
      surface: "native-terminal",
      pid: 9999,
    });
    expect(mockClaimDashboardSessionOwner).toHaveBeenCalledTimes(2);
    expect(ptyProcess.kill).not.toHaveBeenCalled();
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith({
      cliId: "claude",
      ptyProcess,
      sessionId: expect.any(String),
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
  });

  it("refuses dashboard-owned takeover because the old dashboard PTY cannot self-exit", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 2468,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);
    mockClaimDashboardSessionOwner
      .mockRejectedValueOnce({
        code: "SESSION_OWNED_ELSEWHERE",
        owner: {
          session_id: "session-123",
          surface: "dashboard-pty",
          pid: 9999,
          host: "same-host",
          cli_id: "claude",
        },
      });
    mockSessionManager.getLastSessionId.mockReturnValue("session-123");

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
      takeOverSessionOwner: true,
    });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "SESSION_OWNED_ELSEWHERE",
      owner: {
        surface: "dashboard-pty",
        pid: 9999,
      },
    });
    expect(mockReleaseSessionOwner).not.toHaveBeenCalled();
    expect(mockClaimDashboardSessionOwner).toHaveBeenCalledTimes(1);
    expect(ptyProcess.kill).toHaveBeenCalledTimes(1);
    expect(mockSessionManager.trackCliProcess).not.toHaveBeenCalled();
  });

  it("retries the claim when takeover release finds the prior owner already gone", async () => {
    const ptyProcess = {
      kill: jest.fn(),
      pid: 2468,
      write: jest.fn(),
    };
    mockProcesses.clear();
    mockPtySetup.pty.spawn.mockReturnValue(ptyProcess);
    mockReleaseSessionOwner.mockResolvedValueOnce(false);
    mockClaimDashboardSessionOwner
      .mockRejectedValueOnce({
        code: "SESSION_OWNED_ELSEWHERE",
        owner: {
          session_id: "session-123",
          surface: "native-terminal",
          pid: 9999,
          host: "other-host",
          cli_id: "claude",
        },
      })
      .mockResolvedValueOnce(undefined);
    mockSessionManager.getLastSessionId.mockReturnValue("session-123");

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
      takeOverSessionOwner: true,
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      cliId: "claude",
      status: "running",
      pid: 2468,
    });
    const claimedSessionId =
      mockClaimDashboardSessionOwner.mock.calls[0][0].sessionId;
    expect(claimedSessionId).not.toBe("session-123");
    expect(mockReleaseSessionOwner).toHaveBeenCalledWith({
      sessionId: claimedSessionId,
      surface: "native-terminal",
      pid: 9999,
    });
    expect(mockClaimDashboardSessionOwner).toHaveBeenCalledTimes(2);
    expect(ptyProcess.kill).not.toHaveBeenCalled();
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalled();
  });

  it("preserves the tracked session id when start reuses an existing PTY", async () => {
    const existing = mockProcesses.get("claude")?.ptyProcess;

    const response = await CLI_ACTION_HANDLERS.start("claude", {
      action: "start",
      cliId: "claude",
      current_page: "/browse",
      themeMode: "dark",
    });

    await expect(response.json()).resolves.toMatchObject({
      cliId: "claude",
      status: "running",
      pid: 1234,
    });
    expect(mockPtySetup.pty.spawn).not.toHaveBeenCalled();
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith({
      cliId: "claude",
      ptyProcess: existing,
      sessionId: null,
      clearSessionId: false,
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
  });

  it("marks the shared SessionManager conversation active when sending user input", async () => {
    const response = await CLI_ACTION_HANDLERS.send("claude", {
      action: "send",
      cliId: "claude",
      input: "hello",
    });

    await expect(response.json()).resolves.toEqual({
      cliId: "claude",
      sent: true,
    });
    expect(mockWrite).toHaveBeenCalledWith("hello");
    expect(mockSessionManager.markCliActivity).toHaveBeenCalledWith("claude");

    jest.advanceTimersByTime(100);
    expect(mockWrite).toHaveBeenCalledWith("\r");
  });

  it("marks the shared SessionManager conversation active for raw terminal input", async () => {
    const response = await CLI_ACTION_HANDLERS.sendRaw("claude", {
      action: "sendRaw",
      cliId: "claude",
      data: "a",
    });

    await expect(response.json()).resolves.toEqual({
      cliId: "claude",
      sent: true,
    });
    expect(mockWrite).toHaveBeenCalledWith("a");
    expect(mockSessionManager.markCliActivity).toHaveBeenCalledWith("claude");
  });

  it("marks the shared SessionManager conversation idle when stopping the CLI", async () => {
    const response = await CLI_ACTION_HANDLERS.stop("claude", {
      action: "stop",
      cliId: "claude",
    });

    await expect(response.json()).resolves.toEqual({
      cliId: "claude",
      status: "exited",
    });
    expect(mockSessionManager.markCliStopped).toHaveBeenCalledWith("claude");
    expect(mockWriteChatSession).toHaveBeenCalledWith({
      isActive: false,
      status: "idle",
      context: {},
    });
    expect(mockProcesses.has("claude")).toBe(false);
  });

  it("does not clear the shared chat session when stopping an agent bubble", async () => {
    mockSessionManager.markCliStopped.mockReturnValueOnce(false);
    mockProcesses.set("agent-bubble-123", {
      exited: false,
      ptyProcess: {
        kill: jest.fn(),
        pid: 5678,
        write: jest.fn(),
      },
    });

    const response = await CLI_ACTION_HANDLERS.stop("agent-bubble-123", {
      action: "stop",
      cliId: "agent-bubble-123",
    });

    await expect(response.json()).resolves.toEqual({
      cliId: "agent-bubble-123",
      status: "exited",
    });
    expect(mockSessionManager.markCliStopped).toHaveBeenCalledWith(
      "agent-bubble-123",
    );
    expect(mockWriteChatSession).not.toHaveBeenCalled();
  });
});
