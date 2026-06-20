/** @jest-environment node */

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

jest.mock("@/app/api/cli/pty-setup", () => ({
  PTY_SPAWN_HELPER: { path: "/mock/spawn-helper", exists: true },
  attachPtyHandlers: jest.fn(),
  createPtyEntry: jest.fn((ptyProcess) => ({
    detachTimer: null,
    exited: false,
    outputBuffer: [],
    ptyProcess,
    startTime: Date.now(),
  })),
  detachSession: jest.fn(),
  processes: new Map(),
  pty: {
    spawn: jest.fn(() => ({
      kill: jest.fn(),
      pid: 4242,
      write: jest.fn(),
    })),
  },
  ptyHealthy: true,
  setPtyHealthy: jest.fn(),
}));

jest.mock("@/app/api/cli/cli-config", () => ({
  AUGUR_ROOT: "/augur/root",
  buildCliSpawnEnv: jest.fn(() => ({})),
  getCliConfigOrThrow: jest.fn((cliId: string) => {
    const cmdByCli: Record<string, string[]> = {
      claude: ["claude", "--dangerously-skip-permissions", "--session"],
      codex: ["codex", "--dangerously-bypass-approvals-and-sandbox"],
      ollama: ["ollama", "run", "augur-codex-llama3.2:3b-4k"],
      "copilot-cli": ["copilot", "--force"],
    };
    return {
      cmd: cmdByCli[cliId] ?? ["claude", "--dangerously-skip-permissions", "--session"],
      cwd: "/augur/root",
    };
  }),
  isNonEmptyString: (value: unknown) =>
    typeof value === "string" && value.trim().length > 0,
  extractOllamaRunModel: (cmd: unknown) =>
    Array.isArray(cmd) &&
    cmd[0] === "ollama" &&
    cmd[1] === "run" &&
    typeof cmd[2] === "string"
      ? cmd[2]
      : null,
  isDirectOllamaCli: (cliId: string) => cliId === "ollama",
  isValidCli: () => true,
  resolveConfigKey: (cliId: string) =>
    cliId.startsWith("agent-bubble-") ? "claude" : cliId,
  resolveSpawnCommand: (cmd: string) => cmd,
  writeChatSession: jest.fn(),
}));

jest.mock("@/lib/session/SessionManager", () => ({
  __mockSessionManager: {
    markConversationActive: jest.fn(),
    markConversationIdle: jest.fn(),
    markCliActivity: jest.fn(),
    markCliStopped: jest.fn(),
    trackCliProcess: jest.fn(),
    getLastSessionId: jest.fn(() => null),
  },
  getSessionManager: () =>
    jest.requireMock("@/lib/session/SessionManager").__mockSessionManager,
}));

import { CLI_ACTION_HANDLERS } from "@/app/api/cli/actions";

const mockCallMCPTool = jest.requireMock("@/lib/mcp/MCPBridge")
  .callMCPTool as jest.Mock;
const mockPtySetup = jest.requireMock("@/app/api/cli/pty-setup") as {
  processes: Map<string, unknown>;
  pty: { spawn: jest.Mock };
};
const mockSessionManager = jest.requireMock("@/lib/session/SessionManager")
  .__mockSessionManager as {
  getLastSessionId: jest.Mock;
  trackCliProcess: jest.Mock;
};

function mcpJson(value: unknown) {
  return {
    content: [{ type: "text", text: JSON.stringify(value) }],
  };
}

async function startClaude(airplaneMode = true) {
  return startCli("claude", airplaneMode);
}

async function startCli(cliId: string, airplaneMode = true) {
  return CLI_ACTION_HANDLERS.start(cliId, {
    action: "start",
    cliId,
    airplaneMode,
  } as any);
}

describe("CLI route airplane start", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPtySetup.processes.clear();
    // clearAllMocks() resets call history but not return values; restore the
    // default so a per-test mockReturnValue does not leak into later tests.
    mockSessionManager.getLastSessionId.mockReturnValue(null);
  });

  it("rewrites spawned argv to ollama launch when canonical airplane mode is on and override is ready", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "get-airplane-launch-overrides") {
        return mcpJson({
          ready: true,
          launch_argv: [
            "/opt/homebrew/bin/ollama",
            "launch",
            "claude",
            "--model",
            "qwen3.5:9b",
            "--",
          ],
        });
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startClaude(true);

    expect(response.status).toBe(200);
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
    expect(mockPtySetup.pty.spawn).toHaveBeenCalledWith(
      "/opt/homebrew/bin/ollama",
      [
        "launch",
        "claude",
        "--model",
        "qwen3.5:9b",
        "--",
        "--session",
        "--session-id",
        expect.stringMatching(
          /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
        ),
      ],
      expect.objectContaining({
        cwd: "/augur/root",
        env: {},
      }),
    );
  });

  it("mints a fresh Claude session id when launching airplane mode", async () => {
    const priorSession = "11111111-1111-4111-8111-111111111111";
    mockSessionManager.getLastSessionId.mockReturnValue(priorSession);
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "get-airplane-launch-overrides") {
        return mcpJson({
          ready: true,
          launch_argv: [
            "/opt/homebrew/bin/ollama",
            "launch",
            "claude",
            "--model",
            "qwen3.5:9b",
            "--",
          ],
        });
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startClaude(true);

    expect(response.status).toBe(200);
    expect(mockPtySetup.pty.spawn).toHaveBeenCalledWith(
      "/opt/homebrew/bin/ollama",
      [
        "launch",
        "claude",
        "--model",
        "qwen3.5:9b",
        "--",
        "--session",
        "--session-id",
        expect.stringMatching(
          /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
        ),
      ],
      expect.objectContaining({ cwd: "/augur/root", env: {} }),
    );
    const spawnArgs = mockPtySetup.pty.spawn.mock.calls[0][1] as string[];
    expect(spawnArgs).not.toContain("--resume");
    expect(spawnArgs).not.toContain(priorSession);
    const sessionIdIndex = spawnArgs.indexOf("--session-id");
    expect(sessionIdIndex).toBeGreaterThanOrEqual(0);
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: spawnArgs[sessionIdIndex + 1] }),
    );
  });

  it("preserves Codex native Ollama provider args from the airplane override", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "get-airplane-launch-overrides") {
        return mcpJson({
          ready: true,
          launch_argv: [
            "/opt/homebrew/bin/ollama",
            "launch",
            "codex",
            "--model",
            "qwen3.5:9b",
            "--",
            "--oss",
            "--local-provider",
            "ollama",
          ],
        });
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startCli("codex", true);

    expect(response.status).toBe(200);
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "get-airplane-launch-overrides",
      { agent_id: "codex" },
      {},
    );
    expect(mockPtySetup.pty.spawn).toHaveBeenCalledWith(
      "/opt/homebrew/bin/ollama",
      [
        "launch",
        "codex",
        "--model",
        "qwen3.5:9b",
        "--",
        "--oss",
        "--local-provider",
        "ollama",
      ],
      expect.objectContaining({
        cwd: "/augur/root",
        env: {},
      }),
    );
  });

  it("returns 409 with setup hint and does not spawn when airplane override is not ready", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "get-airplane-launch-overrides") {
        return mcpJson({
          ready: false,
          error: "Configured model is unavailable",
          reason: "model_missing",
          setup_hint: "Pull the model: ollama pull qwen3.5:9b",
        });
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startClaude(true);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({
      error: "Configured model is unavailable",
      reason: "model_missing",
      setup_hint: "Pull the model: ollama pull qwen3.5:9b",
    });
    expect(mockPtySetup.pty.spawn).not.toHaveBeenCalled();
  });

  it("starts direct Ollama in airplane mode without requesting an ollama launch override", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "get-airplane-launch-overrides") {
        throw new Error("direct Ollama must not use ollama launch overrides");
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startCli("ollama", true);

    expect(response.status).toBe(200);
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
    expect(mockPtySetup.pty.spawn).toHaveBeenCalledWith(
      "ollama",
      ["run", "augur-codex-llama3.2:3b-4k"],
      expect.objectContaining({
        cwd: "/augur/root",
        env: {},
      }),
    );
    expect(mockSessionManager.trackCliProcess).toHaveBeenCalledWith(
      expect.objectContaining({
        cliId: "ollama",
        airplaneMode: true,
        airplaneLocalModel: "augur-codex-llama3.2:3b-4k",
      }),
    );
  });

  it("uses original configured command when body hints airplane true but canonical state is off", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: false } });
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startClaude(true);

    expect(response.status).toBe(200);
    expect(mockCallMCPTool).toHaveBeenCalledTimes(2);
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "session-claim",
      expect.objectContaining({
        cli_id: "claude",
        surface: "dashboard-pty",
      }),
    );
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "status" },
      {},
    );
    expect(mockCallMCPTool).not.toHaveBeenCalledWith(
      "get-local-backend-status",
      expect.anything(),
      expect.anything(),
    );
    expect(mockCallMCPTool).not.toHaveBeenCalledWith(
      "get-airplane-launch-overrides",
      expect.anything(),
      expect.anything(),
    );
    expect(mockPtySetup.pty.spawn).toHaveBeenCalledWith(
      "claude",
      [
        "--dangerously-skip-permissions",
        "--session",
        "--session-id",
        expect.stringMatching(
          /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
        ),
      ],
      expect.objectContaining({
        cwd: "/augur/root",
        env: {},
      }),
    );
  });

  it("returns JSON 500 when canonical airplane status cannot be read", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        throw new Error("MCP bridge unavailable");
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startClaude(true);

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "Failed to read canonical airplane mode status",
      reason: "MCP bridge unavailable",
    });
    expect(mockPtySetup.pty.spawn).not.toHaveBeenCalled();
  });

  it("uses the resolved config key for agent-bubble airplane override while preserving the raw process identity", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "get-airplane-launch-overrides") {
        return mcpJson({
          ready: true,
          launch_argv: [
            "/opt/homebrew/bin/ollama",
            "launch",
            "claude",
            "--model",
            "qwen3.5:9b",
            "--",
          ],
        });
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startCli("agent-bubble-123", true);

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      cliId: "agent-bubble-123",
      status: "running",
    });
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "get-airplane-launch-overrides",
      { agent_id: "claude" },
      {},
    );
    expect(mockPtySetup.processes.has("agent-bubble-123")).toBe(true);
  });

  it("maps dashboard copilot-cli to Ollama's canonical copilot integration for airplane launch", async () => {
    mockCallMCPTool.mockImplementation(async (tool: string) => {
      if (tool === "session-claim") {
        return mcpJson({ ok: true, success: true });
      }
      if (tool === "toggle-airplane-mode") {
        return mcpJson({ airplane_mode: { enabled: true } });
      }
      if (tool === "get-airplane-launch-overrides") {
        return mcpJson({
          ready: true,
          launch_argv: [
            "/opt/homebrew/bin/ollama",
            "launch",
            "copilot",
            "--model",
            "qwen3.5:9b",
            "--",
          ],
        });
      }
      throw new Error(`Unexpected MCP tool: ${tool}`);
    });

    const response = await startCli("copilot-cli", true);

    expect(response.status).toBe(200);
    expect(mockCallMCPTool).toHaveBeenCalledWith(
      "get-airplane-launch-overrides",
      { agent_id: "copilot" },
      {},
    );
    expect(mockPtySetup.pty.spawn).toHaveBeenCalledWith(
      "/opt/homebrew/bin/ollama",
      ["launch", "copilot", "--model", "qwen3.5:9b", "--"],
      expect.objectContaining({
        cwd: "/augur/root",
        env: {},
      }),
    );
  });
});
