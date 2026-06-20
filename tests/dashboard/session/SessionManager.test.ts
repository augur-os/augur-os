/** @jest-environment node */

import path from "path";
import { SessionManager, getSessionManager } from "@/lib/session/SessionManager";
import { AUGUR_STATE_DIR } from "@/lib/paths";
import { buildCliSpawnEnv, getCliAgentsConfig, resolveSpawnCommand, writeChatSession } from "@/app/api/cli/cli-config";
import { pty } from "@/app/api/cli/pty-setup";

const mockSessionIdFile = path.join(
  AUGUR_STATE_DIR,
  "temp",
  "default_cli_session_id.txt",
);
const mockSessionCliFile = path.join(
  AUGUR_STATE_DIR,
  "temp",
  "default_cli_session_cli.txt",
);

let mockLastSessionId: string | null = null;
let mockLastSessionCliId: string | null = null;
let mockAgentsConfig: Record<string, Record<string, unknown>> = {};
const mockBuildCliSpawnEnv = buildCliSpawnEnv as jest.MockedFunction<
  typeof buildCliSpawnEnv
>;
const mockResolveSpawnCommand = resolveSpawnCommand as jest.MockedFunction<
  typeof resolveSpawnCommand
>;
const mockWriteChatSession = writeChatSession as jest.MockedFunction<
  typeof writeChatSession
>;
const mockPtySpawn = pty.spawn as jest.MockedFunction<typeof pty.spawn>;
const mockFs = jest.requireMock("fs") as {
  existsSync: jest.Mock;
  unlinkSync: jest.Mock;
  mkdirSync: jest.Mock;
  readFileSync: jest.Mock;
  writeFileSync: jest.Mock;
};
const mockProcesses = jest.requireMock("@/app/api/cli/pty-setup")
  .processes as Map<string, Record<string, unknown>>;
const mockCreatePtyEntry = jest.requireMock("@/app/api/cli/pty-setup")
  .createPtyEntry as jest.Mock;
const mockAttachPtyHandlers = jest.requireMock("@/app/api/cli/pty-setup")
  .attachPtyHandlers as jest.Mock;

jest.mock("@/lib/paths", () => ({
  AUGUR_STATE_DIR: "/tmp/augur-state",
}));

jest.mock("@/app/api/cli/cli-config", () => ({
  AUGUR_ROOT: "/augur/root",
  buildCliSpawnEnv: jest.fn(() => ({ PATH: "/mock/path", COLORFGBG: "15;0" })),
  getCliAgentsConfig: jest.fn(() => mockAgentsConfig),
  isNonEmptyString: (value: unknown) =>
    typeof value === "string" && value.length > 0,
  extractOllamaRunModel: (cmd: unknown) =>
    Array.isArray(cmd) &&
    cmd[0] === "ollama" &&
    cmd[1] === "run" &&
    typeof cmd[2] === "string"
      ? cmd[2]
      : null,
  isDirectOllamaCli: (cliId: string) => cliId === "ollama",
  resolveDefaultCliId: jest.fn((agents: Record<string, unknown>) =>
    Object.keys(agents)[0] || "",
  ),
  resolveConfigKey: (cliId: string) =>
    cliId.startsWith("agent-bubble-") ? "claude" : cliId,
  resolveSpawnCommand: jest.fn((cmd: string) => `/resolved/${cmd}`),
  writeChatSession: jest.fn(),
}));

jest.mock("@/app/api/cli/pty-setup", () => ({
  pty: {
    spawn: jest.fn(() => mockPtyProcess),
  },
  processes: new Map(),
  createPtyEntry: jest.fn((ptyProcess) => ({
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
  })),
  attachPtyHandlers: jest.fn(),
}));

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: jest.fn(),
  MCPBridge: {
    extractText: (result: { content?: Array<{ type: string; text: string }> }) =>
      result.content
        ?.filter((item) => item.type === "text")
        .map((item) => item.text)
        .join("\n") ?? "",
  },
}));

jest.mock("fs", () => {
  const actual = jest.requireActual("fs");
  return {
    ...actual,
    existsSync: jest.fn((candidate: string) => {
      if (candidate === mockSessionIdFile) return mockLastSessionId !== null;
      if (candidate === mockSessionCliFile) return mockLastSessionCliId !== null;
      return false;
    }),
    mkdirSync: jest.fn(),
    readFileSync: jest.fn((candidate: string) => {
      if (candidate === mockSessionIdFile) {
        return mockLastSessionId ?? "";
      }
      if (candidate === mockSessionCliFile) {
        return mockLastSessionCliId ?? "";
      }
      throw new Error(`unexpected read: ${candidate}`);
    }),
    writeFileSync: jest.fn((candidate: string, value: string) => {
      if (candidate === mockSessionIdFile) {
        mockLastSessionId = value;
      } else if (candidate === mockSessionCliFile) {
        mockLastSessionCliId = value;
      }
    }),
    unlinkSync: jest.fn((candidate: string) => {
      if (candidate === mockSessionIdFile) {
        mockLastSessionId = null;
      } else if (candidate === mockSessionCliFile) {
        mockLastSessionCliId = null;
      }
    }),
  };
});

const mockPtyProcess = {
  pid: 1234,
  onData: jest.fn(),
  onExit: jest.fn(),
  write: jest.fn(),
  kill: jest.fn(),
};

const mockCallMCPTool = jest.requireMock("@/lib/mcp/MCPBridge")
  .callMCPTool as jest.Mock;

function mcpJson(value: unknown) {
  return {
    content: [{ type: "text", text: JSON.stringify(value) }],
  };
}

function mockCanonicalAirplane(
  enabled: boolean,
  agentId = "claude",
  model = "qwen3.5:9b",
): void {
  mockCallMCPTool.mockImplementation(async (tool: string) => {
    if (tool === "toggle-airplane-mode") {
      return mcpJson({ airplane_mode: { enabled } });
    }
    if (tool === "session-claim") {
      return mcpJson({ ok: true, owner: { surface: "dashboard-pty" } });
    }
    if (tool === "session-release") {
      return mcpJson({ ok: true, released: true });
    }
    if (tool === "session-status") {
      return mcpJson({ ok: true, owner: null });
    }
    if (tool === "get-airplane-launch-overrides" && enabled) {
      return mcpJson({
        ready: true,
        launch_argv: [
          "/opt/homebrew/bin/ollama",
          "launch",
          agentId,
          "--model",
          model,
          "--",
        ],
      });
    }
    throw new Error(`Unexpected MCP tool: ${tool}`);
  });
}

function resetState(): void {
  jest.useRealTimers();
  mockLastSessionId = null;
  mockLastSessionCliId = null;
  mockAgentsConfig = {};
  mockProcesses.clear();
  mockCallMCPTool.mockReset();
  mockCanonicalAirplane(false);
  jest.clearAllMocks();
}

describe("SessionManager", () => {
  beforeEach(() => {
    resetState();
  });

  it("starts idle with no saved session", () => {
    const manager = new SessionManager();

    expect(manager.isRunning()).toBe(false);
    expect(manager.hasActiveConversation()).toBe(false);
    expect(manager.getLastSessionId()).toBeNull();
  });

  it("saves and reloads the last session id", () => {
    const manager = new SessionManager();

    manager.saveSessionId("abc-123", "claude");

    expect(manager.getLastSessionId()).toBe("abc-123");
    expect(manager.getLastSessionId("claude")).toBe("abc-123");
    expect(manager.getLastSessionId("codex")).toBeNull();
    expect(mockFs.writeFileSync).toHaveBeenCalledWith(
      mockSessionIdFile,
      "abc-123",
      "utf8",
    );
    expect(mockFs.writeFileSync).toHaveBeenCalledWith(
      mockSessionCliFile,
      "claude",
      "utf8",
    );

    const secondManager = new SessionManager();
    expect(secondManager.getLastSessionId()).toBe("abc-123");
    expect(secondManager.getLastSessionId("claude")).toBe("abc-123");
    expect(secondManager.getLastSessionId("codex")).toBeNull();
  });

  it("tracks an externally-started CLI process for terminal handoff", () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    mockProcesses.set("claude", {
      exited: false,
      ptyProcess: mockPtyProcess,
    });
    const manager = new SessionManager();

    manager.trackCliProcess({
      cliId: "claude",
      ptyProcess: mockPtyProcess,
      sessionId: "session-456",
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });

    expect(manager.getTerminalHandoffSnapshot()).toEqual({
      cliId: "claude",
      pid: 1234,
      sessionId: "session-456",
      cwd: "/workspace/claude",
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
    expect(mockFs.writeFileSync).toHaveBeenCalledWith(
      mockSessionIdFile,
      "session-456",
      "utf8",
    );
  });

  it("clears stale session ids when tracking a process without a resumable id", () => {
    mockLastSessionId = "old-session";
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    mockProcesses.set("claude", {
      exited: false,
      ptyProcess: mockPtyProcess,
    });
    const manager = new SessionManager();

    manager.trackCliProcess({
      cliId: "claude",
      ptyProcess: mockPtyProcess,
      sessionId: null,
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });

    expect(manager.getLastSessionId()).toBeNull();
    expect(manager.getTerminalHandoffSnapshot()).toBeNull();
    expect(mockFs.unlinkSync).toHaveBeenCalledWith(mockSessionIdFile);
  });

  it("preserves the previous session id when re-tracking an existing process", () => {
    mockLastSessionId = "session-789";
    mockLastSessionCliId = "claude";
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    mockProcesses.set("claude", {
      exited: false,
      ptyProcess: mockPtyProcess,
    });
    const manager = new SessionManager();

    manager.trackCliProcess({
      cliId: "claude",
      ptyProcess: mockPtyProcess,
      sessionId: null,
      clearSessionId: false,
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });

    expect(manager.getLastSessionId()).toBe("session-789");
    expect(manager.getTerminalHandoffSnapshot()?.sessionId).toBe("session-789");
    expect(mockFs.unlinkSync).not.toHaveBeenCalled();
  });

  it("recovers a terminal handoff snapshot from the live PTY registry after manager state resets", () => {
    mockLastSessionId = "session-abc";
    mockLastSessionCliId = "claude";
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    mockProcesses.set("claude", {
      exited: false,
      ptyProcess: mockPtyProcess,
      sessionId: "session-abc",
      cliId: "claude",
      airplaneMode: true,
      airplaneLocalModel: "qwen3.5:9b",
      themeMode: "dark",
    });
    const manager = new SessionManager();

    expect(manager.getTerminalHandoffSnapshot()).toEqual({
      cliId: "claude",
      pid: 1234,
      sessionId: "session-abc",
      cwd: "/workspace/claude",
      airplaneMode: true,
      airplaneLocalModel: "qwen3.5:9b",
      themeMode: "dark",
    });
    expect(manager.isRunning()).toBe(true);
  });

  it("initializes the default claude session with configured cwd and env", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude", "-p", "--output-format", "stream-json"],
        cwd: "/workspace/claude",
        env: { CLAUDE_MODE: "interactive" },
      },
    };

    const manager = new SessionManager();

    await manager.initialize();

    expect(manager.isRunning()).toBe(true);
    expect(manager.getCliId()).toBe("claude");
    expect(manager.getPid()).toBe(1234);
    expect(mockBuildCliSpawnEnv).toHaveBeenCalledWith(
      mockAgentsConfig.claude,
      undefined,
      undefined,
    );
    expect(mockResolveSpawnCommand).toHaveBeenCalledWith("claude");
    expect(mockWriteChatSession).toHaveBeenCalledWith({
      isActive: true,
      status: "running",
      context: {
        current_page: "dashboard",
        cliId: "claude",
        airplaneMode: false,
      },
    });
    expect(mockPtySpawn).toHaveBeenCalledWith(
      "/resolved/claude",
      ["-p", "--output-format", "stream-json"],
      expect.objectContaining({
        cwd: "/workspace/claude",
        env: { PATH: "/mock/path", COLORFGBG: "15;0" },
      }),
    );
    expect(mockCreatePtyEntry).toHaveBeenCalledWith(mockPtyProcess);
    expect(mockAttachPtyHandlers).toHaveBeenCalledTimes(1);
    expect(mockProcesses.get("claude")).toMatchObject({
      ptyProcess: mockPtyProcess,
      exited: false,
    });
  });

  it("attaches to an existing visible CLI process instead of spawning a hidden PTY", async () => {
    const visibleProcess = {
      ...mockPtyProcess,
      pid: 5678,
    };
    mockProcesses.set("claude", {
      ptyProcess: visibleProcess,
      exited: false,
    });
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();

    expect(mockPtySpawn).not.toHaveBeenCalled();
    expect(manager.isRunning()).toBe(true);
    expect(manager.getCliId()).toBe("claude");
    expect(manager.getPid()).toBe(5678);
  });

  it.each([
    {
      cliId: "claude",
      config: {
        claude: {
          cmd: ["claude", "-p", "--output-format", "stream-json"],
          cwd: "/workspace/claude",
        },
      },
      expectedCwd: "/workspace/claude",
      expectedCommand: "/resolved/claude",
      expectedArgs: ["-p", "--output-format", "stream-json"],
    },
    {
      cliId: "codex",
      config: {
        codex: {
          cmd: ["codex", "--search", "--json"],
          cwd: "/workspace/codex",
        },
      },
      expectedCwd: "/workspace/codex",
      expectedCommand: "/resolved/codex",
      expectedArgs: ["resume", "session-123", "--search", "--json"],
    },
    {
      cliId: "gemini",
      config: {
        gemini: {
          cmd: ["gemini", "--yolo"],
          cwd: "/workspace/gemini",
        },
      },
      expectedCwd: "/workspace/gemini",
      expectedCommand: "/resolved/gemini",
      expectedArgs: ["--yolo"],
    },
    {
      cliId: "claude-kimi",
      config: {
        "claude-kimi": {
          cmd: ["claude", "--model", "ollama/kimi-k2.5:cloud"],
          cwd: "/workspace/claude-kimi",
        },
      },
      expectedCwd: "/workspace/claude-kimi",
      expectedCommand: "/resolved/claude",
      expectedArgs: ["--model", "ollama/kimi-k2.5:cloud"],
    },
  ])(
    "builds launch args for $cliId",
    async ({ cliId, config, expectedCommand, expectedArgs, expectedCwd }) => {
      mockAgentsConfig = config as Record<string, Record<string, unknown>>;

      const manager = new SessionManager();
      manager.saveSessionId("session-123", cliId);

      await manager.initialize();

      expect(mockPtySpawn).toHaveBeenCalledWith(
        expectedCommand,
        expectedArgs,
        expect.objectContaining({
          cwd: expectedCwd,
        }),
      );
    },
  );

  it("does not append unsupported resume flags for non-resumable CLIs", async () => {
    mockAgentsConfig = {
      opencode: {
        cmd: ["opencode"],
        cwd: "/workspace/opencode",
      },
    };

    const manager = new SessionManager();
    manager.saveSessionId("session-123", "opencode");

    await manager.initialize();

    expect(mockPtySpawn).toHaveBeenCalledWith(
      "/resolved/opencode",
      [],
      expect.objectContaining({
        cwd: "/workspace/opencode",
      }),
    );
  });

  it("spawns prewarm through ollama launch and strips auto-approve flags when canonical airplane mode is enabled", async () => {
    mockCanonicalAirplane(true);
    mockAgentsConfig = {
      claude: {
        cmd: ["claude", "--dangerously-skip-permissions", "--model", "sonnet"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();

    await manager.initialize({ airplaneMode: true, currentPage: "/browse" });

    expect(mockBuildCliSpawnEnv).toHaveBeenCalledWith(
      mockAgentsConfig.claude,
      "/browse",
      undefined,
    );
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "status" },
      {},
    );
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "get-airplane-launch-overrides",
      { agent_id: "claude" },
      {},
    );
    expect(mockPtySpawn).toHaveBeenCalledWith(
      "/resolved//opt/homebrew/bin/ollama",
      [
        "launch",
        "claude",
        "--model",
        "qwen3.5:9b",
        "--",
        "--model",
        "sonnet",
      ],
      expect.any(Object),
    );
    expect(mockWriteChatSession).toHaveBeenCalledWith({
      isActive: true,
      status: "running",
      context: {
        current_page: "/browse",
        cliId: "claude",
        airplaneMode: true,
      },
    });
  });

  it("prewarms direct Ollama in airplane mode without requesting an ollama launch override", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "session-claim") {
        return mcpJson({ ok: true, owner: { surface: "dashboard-pty" } });
      }
      if (tool === "get-airplane-launch-overrides") {
        throw new Error("direct Ollama must not use ollama launch overrides");
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });
    mockAgentsConfig = {
      ollama: {
        cmd: ["ollama", "run", "augur-codex-llama3.2:3b-4k"],
        cwd: "/workspace/ollama",
      },
    };

    const manager = new SessionManager();

    await manager.initialize({ airplaneMode: true, currentPage: "/browse" });

    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "status" },
      {},
    );
    expect(mockCallMCPTool).not.toHaveBeenCalledWith(
      "get-airplane-launch-overrides",
      expect.anything(),
      expect.anything(),
    );
    expect(mockPtySpawn).toHaveBeenCalledWith(
      "/resolved/ollama",
      ["run", "augur-codex-llama3.2:3b-4k"],
      expect.objectContaining({
        cwd: "/workspace/ollama",
      }),
    );
    expect(manager.getActiveBackend()).toMatchObject({
      running: true,
      cliId: "ollama",
      airplaneMode: true,
      localModel: "augur-codex-llama3.2:3b-4k",
    });
  });

  it("preserves resume args after the airplane ollama launch wrapper", async () => {
    mockCanonicalAirplane(true, "codex");
    mockAgentsConfig = {
      codex: {
        cmd: [
          "codex",
          "--dangerously-skip-permissions",
          "--search",
          "--json",
        ],
        cwd: "/workspace/codex",
      },
    };

    const manager = new SessionManager();
    manager.saveSessionId("session-123", "codex");

    await manager.initialize({ airplaneMode: true });

    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "get-airplane-launch-overrides",
      { agent_id: "codex" },
      {},
    );
    expect(mockPtySpawn).toHaveBeenCalledWith(
      "/resolved//opt/homebrew/bin/ollama",
      [
        "launch",
        "codex",
        "--model",
        "qwen3.5:9b",
        "--",
        "resume",
        "session-123",
        "--search",
        "--json",
      ],
      expect.objectContaining({
        cwd: "/workspace/codex",
      }),
    );
  });

  it("requests an idle prewarm restart when canonical airplane mode changes despite a stale client hint", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude", "--dangerously-skip-permissions", "--model", "sonnet"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize({ airplaneMode: false });

    mockCallMCPTool.mockClear();
    mockCanonicalAirplane(true);

    await expect(
      manager.shouldRestartForOptions({ airplaneMode: false }),
    ).resolves.toBe(true);
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "status" },
      {},
    );

    manager.markConversationActive();
    mockCallMCPTool.mockClear();
    await expect(
      manager.shouldRestartForOptions({ airplaneMode: false }),
    ).resolves.toBe(false);
    expect(mockCallMCPTool).not.toHaveBeenCalled();
  });

  it("requests an idle prewarm restart when airplane mode stays on but the local model changes", async () => {
    mockCanonicalAirplane(true, "claude", "qwen3.5:9b");
    mockAgentsConfig = {
      claude: {
        cmd: ["claude", "--dangerously-skip-permissions", "--model", "sonnet"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize({
      airplaneMode: true,
      airplaneLocalModel: "qwen3.5:9b",
    });

    await expect(
      manager.shouldRestartForOptions({
        airplaneMode: true,
        airplaneLocalModel: "qwen3.5:9b",
      }),
    ).resolves.toBe(false);

    await expect(
      manager.shouldRestartForOptions({
        airplaneMode: true,
        airplaneLocalModel: "llama3.2:3b",
      }),
    ).resolves.toBe(true);
  });

  it("tracks active and idle conversation state for an owned prewarmed CLI", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    const manager = new SessionManager();
    await manager.initialize();

    expect(manager.hasActiveConversation()).toBe(false);

    manager.markConversationActive();
    expect(manager.hasActiveConversation()).toBe(true);

    manager.markConversationIdle();
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("clears stale active state after the owned CLI exits", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    const manager = new SessionManager();
    await manager.initialize();
    manager.markConversationActive();

    const entry = mockProcesses.get("claude");
    if (entry) {
      entry.exited = true;
    }

    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("treats an externally active default CLI as an active conversation", () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    mockProcesses.set("claude", {
      ptyProcess: mockPtyProcess,
      exited: false,
    });

    const manager = new SessionManager();
    manager.markCliActivity("claude");

    expect(manager.hasActiveConversation()).toBe(true);
  });

  it("sends a message, presses Enter, and marks the conversation active", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();

    manager.sendMessage("hello there");

    expect(mockPtyProcess.write).toHaveBeenNthCalledWith(1, "hello there");
    expect(mockPtyProcess.write).toHaveBeenNthCalledWith(2, "\r");
    expect(manager.hasActiveConversation()).toBe(true);
  });

  it("returns a terminal handoff snapshot for a running resumable session", async () => {
    mockAgentsConfig = {
      codex: {
        cmd: ["codex", "--dangerously-bypass-approvals-and-sandbox"],
        cwd: "/workspace/codex",
      },
    };
    const manager = new SessionManager();
    manager.saveSessionId("session-123", "codex");

    await manager.initialize({
      airplaneMode: false,
      currentPage: "/workspace/inbox",
      themeMode: "dark",
    });

    expect(manager.getTerminalHandoffSnapshot()).toEqual({
      cliId: "codex",
      pid: 1234,
      sessionId: "session-123",
      cwd: "/workspace/codex",
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
  });

  it("returns null terminal handoff snapshot when no session id is saved", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    const manager = new SessionManager();

    await manager.initialize();

    expect(manager.getTerminalHandoffSnapshot()).toBeNull();
  });

  it("returns null terminal handoff snapshot for non-resumable CLIs", async () => {
    mockAgentsConfig = {
      opencode: {
        cmd: ["opencode"],
        cwd: "/workspace/opencode",
      },
    };
    const manager = new SessionManager();
    manager.saveSessionId("session-123", "opencode");

    await manager.initialize();

    expect(manager.getTerminalHandoffSnapshot()).toBeNull();
  });

  it("sends exit and resolves terminal handoff exit when the PTY exits", async () => {
    jest.useFakeTimers();
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    const manager = new SessionManager();
    manager.saveSessionId("session-123", "claude");
    await manager.initialize();

    const exitPromise = manager.exitForTerminalHandoff({
      timeoutMs: 500,
      pollMs: 50,
    });
    const entry = mockProcesses.get("claude");
    if (entry) {
      entry.exited = true;
    }
    await jest.advanceTimersByTimeAsync(50);

    await expect(exitPromise).resolves.toEqual({ ok: true });
    expect(mockPtyProcess.write).toHaveBeenNthCalledWith(1, "exit");
    expect(mockPtyProcess.write).toHaveBeenNthCalledWith(2, "\r");
    expect(mockWriteChatSession).toHaveBeenLastCalledWith({
      isActive: false,
      status: "idle",
      context: {},
    });
  });

  it("reports timeout when terminal handoff exit does not stop the PTY", async () => {
    jest.useFakeTimers();
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    const manager = new SessionManager();
    manager.saveSessionId("session-123", "claude");
    await manager.initialize();

    const exitPromise = manager.exitForTerminalHandoff({
      timeoutMs: 100,
      pollMs: 50,
    });
    await jest.advanceTimersByTimeAsync(150);

    await expect(exitPromise).resolves.toEqual({
      ok: false,
      reason: "exit_timeout",
    });
    expect(manager.isRunning()).toBe(true);
    expect(manager.getCliId()).toBe("claude");
    expect(manager.getPid()).toBe(1234);
    expect(mockProcesses.has("claude")).toBe(true);
    expect(mockWriteChatSession).not.toHaveBeenCalledWith({
      isActive: false,
      status: "idle",
      context: {},
    });
  });

  it("terminates the running PTY and clears runtime state", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();
    manager.markConversationActive();

    manager.terminate();

    expect(mockPtyProcess.kill).toHaveBeenCalledTimes(1);
    expect(mockProcesses.has("claude")).toBe(false);
    expect(manager.isRunning()).toBe(false);
    expect(manager.getCliId()).toBeNull();
    expect(manager.getPid()).toBeNull();
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("clears owned runtime state when the shared CLI stop path reports the process stopped", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();
    manager.markConversationActive();

    mockProcesses.delete("claude");
    manager.markCliStopped("claude");

    expect(manager.isRunning()).toBe(false);
    expect(manager.getCliId()).toBeNull();
    expect(manager.getPid()).toBeNull();
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("ignores unrelated CLI activity and stops when tracking an owned session", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();
    manager.markConversationActive();

    expect(manager.markCliStopped("agent-bubble-123")).toBe(false);
    expect(manager.hasActiveConversation()).toBe(true);

    manager.markConversationIdle();
    manager.markCliActivity("agent-bubble-123");
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("tracks non-default visible CLI activity for collision detection", () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
      codex: {
        cmd: ["codex"],
        cwd: "/workspace/codex",
      },
    };
    mockProcesses.set("codex", {
      ptyProcess: mockPtyProcess,
      exited: false,
    });

    const manager = new SessionManager();
    manager.markCliActivity("codex");

    expect(manager.hasActiveConversation()).toBe(true);
    expect(manager.markCliStopped("agent-bubble-123")).toBe(false);
    expect(manager.hasActiveConversation()).toBe(true);
    expect(manager.markCliStopped("codex")).toBe(true);
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("stopping an active non-default CLI clears collision state even while default prewarm is live", async () => {
    const codexProcess = {
      ...mockPtyProcess,
      pid: 5678,
      kill: jest.fn(),
    };
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
      codex: {
        cmd: ["codex"],
        cwd: "/workspace/codex",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();
    mockProcesses.set("codex", {
      ptyProcess: codexProcess,
      exited: false,
    });
    manager.markCliActivity("codex");

    expect(manager.hasActiveConversation()).toBe(true);
    expect(manager.markCliStopped("codex")).toBe(true);
    expect(manager.isRunning()).toBe(true);
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("terminates active non-default CLIs before replacing into the default session", async () => {
    const codexProcess = {
      ...mockPtyProcess,
      pid: 5678,
      kill: jest.fn(),
    };
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
      codex: {
        cmd: ["codex"],
        cwd: "/workspace/codex",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();
    mockProcesses.set("codex", {
      ptyProcess: codexProcess,
      exited: false,
    });
    manager.markCliActivity("codex");

    manager.terminateActiveConversations();

    expect(codexProcess.kill).toHaveBeenCalledTimes(1);
    expect(mockProcesses.has("codex")).toBe(false);
    expect(manager.isRunning()).toBe(true);
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("terminates the tracked CLI after a previous continue message made it active", async () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };

    const manager = new SessionManager();
    await manager.initialize();
    manager.sendMessage("previous continue");

    manager.terminateActiveConversations();

    expect(mockPtyProcess.kill).toHaveBeenCalledTimes(1);
    expect(mockProcesses.has("claude")).toBe(false);
    expect(manager.isRunning()).toBe(false);
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("terminates an externally registered default CLI when replacing sessions", () => {
    mockAgentsConfig = {
      claude: {
        cmd: ["claude"],
        cwd: "/workspace/claude",
      },
    };
    mockProcesses.set("claude", {
      ptyProcess: mockPtyProcess,
      exited: false,
      detachTimer: null,
    });

    const manager = new SessionManager();
    manager.terminate();

    expect(mockPtyProcess.kill).toHaveBeenCalledTimes(1);
    expect(mockProcesses.has("claude")).toBe(false);
    expect(manager.isRunning()).toBe(false);
    expect(manager.hasActiveConversation()).toBe(false);
  });

  it("returns the same singleton instance", () => {
    expect(getSessionManager()).toBe(getSessionManager());
  });
});
