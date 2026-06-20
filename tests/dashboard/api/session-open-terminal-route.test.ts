/** @jest-environment node */

import { NextRequest } from "next/server";

const mockManager = {
  getTerminalHandoffSnapshot: jest.fn(),
  exitForTerminalHandoff: jest.fn(),
};
const mockLaunchNativeTerminal = jest.fn();
const mockReadCanonicalAirplaneMode = jest.fn();
const mockReadAirplaneLaunchOverrides = jest.fn();
const mockWriteFileSync = jest.fn();
const mockMkdirSync = jest.fn();
const mockExistsSync = jest.fn();
const mockGetSessionOwner = jest.fn();

jest.mock("@/lib/session/SessionManager", () => ({
  getSessionManager: () => mockManager,
}));

jest.mock("@/lib/server/nativeTerminal", () => ({
  launchNativeTerminal: (...args: unknown[]) => mockLaunchNativeTerminal(...args),
}));

jest.mock("@/lib/session/sessionOwners", () => ({
  getSessionOwner: (...args: unknown[]) => mockGetSessionOwner(...args),
  isSameDashboardOwner: (owner: { pid?: number; surface?: string }, pid: number) =>
    owner.surface === "dashboard-pty" && owner.pid === pid,
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

jest.mock("@/app/api/cli/airplane-routing", () => ({
  readCanonicalAirplaneMode: () => mockReadCanonicalAirplaneMode(),
  readAirplaneLaunchOverrides: (cliId: string) =>
    mockReadAirplaneLaunchOverrides(cliId),
  airplaneUnavailablePayload: (overrides: Record<string, unknown> | undefined) => ({
    error: overrides?.error || "Airplane launch override is not ready",
    setup_hint:
      overrides?.setup_hint || "Check local backend setup and try again.",
    reason: overrides?.reason || "not_ready",
  }),
}));

jest.mock("@/lib/paths", () => ({
  AUGUR_ROOT: "/repo/augur",
  AUGUR_STATE_DIR: "/tmp/augur-state",
}));

jest.mock("fs", () => ({
  existsSync: (...args: unknown[]) => mockExistsSync(...args),
  mkdirSync: (...args: unknown[]) => mockMkdirSync(...args),
  writeFileSync: (...args: unknown[]) => mockWriteFileSync(...args),
}));

import { POST } from "@/app/api/session/open-terminal/route";

function request(
  body: Record<string, unknown> = {},
  headers: Record<string, string> = {},
): NextRequest {
  return new NextRequest("http://localhost/api/session/open-terminal", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
}

describe("POST /api/session/open-terminal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockManager.getTerminalHandoffSnapshot.mockReturnValue({
      cliId: "codex",
      pid: 1234,
      sessionId: "session-123",
      cwd: "/workspace/codex",
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });
    mockManager.exitForTerminalHandoff.mockResolvedValue({ ok: true });
    mockReadCanonicalAirplaneMode.mockResolvedValue(false);
    mockReadAirplaneLaunchOverrides.mockResolvedValue({
      ready: true,
      launch_argv: ["/opt/homebrew/bin/ollama", "launch", "codex", "--"],
    });
    mockGetSessionOwner.mockResolvedValue(null);
    mockExistsSync.mockReturnValue(true);
    mockLaunchNativeTerminal.mockResolvedValue({
      command: "osascript",
      args: [],
      cwd: "/workspace/codex",
    });
  });

  it("blocks remote users", async () => {
    const response = await POST(request({}, { "x-remote-user": "true" }));

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "REMOTE_BLOCKED",
    });
    expect(mockManager.getTerminalHandoffSnapshot).not.toHaveBeenCalled();
  });

  it("writes payload, exits embedded PTY, and opens native terminal", async () => {
    const response = await POST(
      request({
        currentPage: "/workspace/inbox",
        dashboardMode: "operation",
        themeMode: "dark",
      }),
    );

    expect(response.status).toBe(200);
    expect(mockManager.exitForTerminalHandoff).toHaveBeenCalledTimes(1);
    expect(mockWriteFileSync).toHaveBeenCalledWith(
      expect.stringContaining("terminal-handoffs"),
      expect.any(String),
      "utf8",
    );
    const payloadText = mockWriteFileSync.mock.calls[0][1] as string;
    const payload = JSON.parse(payloadText);
    expect(payload).toMatchObject({
      version: 1,
      cli_id: "codex",
      shortcut: "xa",
      session_id: "session-123",
      cwd: "/workspace/codex",
      current_page: "/workspace/inbox",
      dashboard_mode: "operation",
      theme_mode: "dark",
      handoff_prompt: expect.stringContaining(
        "Exited dashboard chat. Continue in this native terminal.",
      ),
      route: {
        airplane_mode: false,
        local_model: null,
      },
    });
    expect(payload.handoff_prompt).toContain("/workspace/inbox");
    expect(mockLaunchNativeTerminal).toHaveBeenCalledWith(
      expect.objectContaining({
        cwd: "/workspace/codex",
        argv: [
          "/repo/augur/scripts/xa-launch.sh",
          "--handoff-file",
          expect.stringContaining("handoff-codex-session-123"),
        ],
      }),
    );
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      cliId: "codex",
      shortcut: "xa",
    });
  });

  it("fails closed when the shortcut adapter is missing", async () => {
    mockExistsSync.mockReturnValue(false);

    const response = await POST(request());

    expect(response.status).toBe(500);
    expect(mockLaunchNativeTerminal).not.toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      code: "TERMINAL_LAUNCH_FAILED",
      error: expect.stringContaining("Missing terminal handoff launcher"),
    });
  });

  it("does not launch terminal when no resumable snapshot exists", async () => {
    mockManager.getTerminalHandoffSnapshot.mockReturnValue(null);

    const response = await POST(request());

    expect(response.status).toBe(409);
    expect(mockManager.exitForTerminalHandoff).not.toHaveBeenCalled();
    expect(mockLaunchNativeTerminal).not.toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      code: "NO_RESUMABLE_SESSION",
    });
  });

  it("does not launch terminal for unsupported clients", async () => {
    mockManager.getTerminalHandoffSnapshot.mockReturnValue({
      cliId: "opencode",
      pid: 1234,
      sessionId: "session-123",
      cwd: "/workspace/opencode",
      airplaneMode: false,
      airplaneLocalModel: null,
      themeMode: "dark",
    });

    const response = await POST(request());

    expect(response.status).toBe(400);
    expect(mockManager.exitForTerminalHandoff).not.toHaveBeenCalled();
    expect(mockLaunchNativeTerminal).not.toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      code: "UNSUPPORTED_CLIENT",
    });
  });

  it("does not exit embedded PTY when another live owner has the session", async () => {
    mockGetSessionOwner.mockResolvedValueOnce({
      session_id: "session-123",
      surface: "native-terminal",
      pid: 9999,
      host: "other-host",
      cli_id: "codex",
    });

    const response = await POST(request());

    expect(response.status).toBe(409);
    expect(mockManager.exitForTerminalHandoff).not.toHaveBeenCalled();
    expect(mockWriteFileSync).not.toHaveBeenCalled();
    expect(mockLaunchNativeTerminal).not.toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      code: "SESSION_OWNED_ELSEWHERE",
      owner: {
        surface: "native-terminal",
        pid: 9999,
        host: "other-host",
      },
    });
  });

  it("does not launch terminal when graceful exit times out", async () => {
    mockManager.exitForTerminalHandoff.mockResolvedValue({
      ok: false,
      reason: "exit_timeout",
    });

    const response = await POST(request());

    expect(response.status).toBe(409);
    expect(mockWriteFileSync).not.toHaveBeenCalled();
    expect(mockLaunchNativeTerminal).not.toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      code: "EXIT_TIMEOUT",
    });
  });

  it("does not launch terminal when the embedded session is gone before exit", async () => {
    mockManager.exitForTerminalHandoff.mockResolvedValue({
      ok: false,
      reason: "no_running_session",
    });

    const response = await POST(request());

    expect(response.status).toBe(409);
    expect(mockWriteFileSync).not.toHaveBeenCalled();
    expect(mockLaunchNativeTerminal).not.toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      code: "NO_RUNNING_SESSION",
    });
  });

  it("refuses airplane handoff when local launch override is not ready", async () => {
    mockManager.getTerminalHandoffSnapshot.mockReturnValue({
      cliId: "claude",
      pid: 1234,
      sessionId: "session-123",
      cwd: "/workspace/claude",
      airplaneMode: true,
      airplaneLocalModel: "qwen3:4b",
      themeMode: "dark",
    });
    mockReadCanonicalAirplaneMode.mockResolvedValue(true);
    mockReadAirplaneLaunchOverrides.mockResolvedValue({
      ready: false,
      error: "Configured model is unavailable",
      reason: "model_missing",
      setup_hint: "ollama pull qwen3:4b",
    });

    const response = await POST(request());

    expect(response.status).toBe(409);
    expect(mockManager.exitForTerminalHandoff).not.toHaveBeenCalled();
    expect(mockLaunchNativeTerminal).not.toHaveBeenCalled();
    await expect(response.json()).resolves.toMatchObject({
      error: "Configured model is unavailable",
      reason: "model_missing",
      setup_hint: "ollama pull qwen3:4b",
    });
  });

  it("includes local launch argv when airplane mode is active", async () => {
    mockReadCanonicalAirplaneMode.mockResolvedValue(true);
    mockReadAirplaneLaunchOverrides.mockResolvedValue({
      ready: true,
      launch_argv: [
        "/opt/homebrew/bin/ollama",
        "launch",
        "codex",
        "--model",
        "qwen3:4b",
        "--",
      ],
    });

    const response = await POST(request());

    expect(response.status).toBe(200);
    const payloadText = mockWriteFileSync.mock.calls[0][1] as string;
    const payload = JSON.parse(payloadText);
    expect(payload.route).toMatchObject({
      airplane_mode: true,
      launch_argv: [
        "/opt/homebrew/bin/ollama",
        "launch",
        "codex",
        "--model",
        "qwen3:4b",
        "--",
      ],
    });
  });
});
