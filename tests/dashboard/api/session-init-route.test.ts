/** @jest-environment node */

import { POST } from "@/app/api/session/init/route";
import { getSessionManager } from "@/lib/session/SessionManager";
import { SessionOwnerConflictError } from "@/lib/session/sessionOwners";

const mockManager = {
  isRunning: jest.fn(),
  shouldRestartForOptions: jest.fn(),
  terminate: jest.fn(),
  initialize: jest.fn(),
  getCliId: jest.fn(),
  getPid: jest.fn(),
  getLastSessionId: jest.fn(),
};

jest.mock("@/lib/session/SessionManager", () => ({
  getSessionManager: jest.fn(() => mockManager),
}));

describe("POST /api/session/init", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockManager.isRunning.mockReturnValue(false);
    mockManager.shouldRestartForOptions.mockResolvedValue(false);
    mockManager.initialize.mockResolvedValue(undefined);
    mockManager.getCliId.mockReturnValue("claude");
    mockManager.getPid.mockReturnValue(1234);
    mockManager.getLastSessionId.mockReturnValue("session-1");
  });

  it("blocks remote requests before touching the CLI session", async () => {
    const response = await POST(
      new Request("http://localhost/api/session/init", {
        method: "POST",
        headers: { "x-remote-user": "true" },
      }) as never,
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error:
        "CLI terminal is not available for remote access. Use your local Claude Desktop with MCP connection instead.",
      code: "REMOTE_BLOCKED",
    });
    expect(getSessionManager).not.toHaveBeenCalled();
  });

  it("initializes the default session when it is not running", async () => {
    const response = await POST(
      new Request("http://localhost/api/session/init", {
        method: "POST",
        body: JSON.stringify({
          airplaneMode: true,
          airplaneLocalModel: "qwen3.5:9b",
          currentPage: "/browse",
          themeMode: "light",
        }),
      }) as never,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      alreadyRunning: false,
      restarted: false,
      cliId: "claude",
      pid: 1234,
      lastSessionId: "session-1",
    });
    expect(mockManager.initialize).toHaveBeenCalledWith({
      airplaneMode: true,
      airplaneLocalModel: "qwen3.5:9b",
      currentPage: "/browse",
      themeMode: "light",
    });
  });

  it("returns running metadata without reinitializing an active prewarm", async () => {
    mockManager.isRunning.mockReturnValue(true);
    mockManager.shouldRestartForOptions.mockResolvedValue(false);

    const response = await POST(
      new Request("http://localhost/api/session/init", {
        method: "POST",
      }) as never,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      alreadyRunning: true,
      cliId: "claude",
      pid: 1234,
      lastSessionId: "session-1",
    });
    expect(mockManager.initialize).not.toHaveBeenCalled();
  });

  it("restarts an idle prewarm when startup options change", async () => {
    let running = true;
    mockManager.isRunning.mockImplementation(() => running);
    mockManager.shouldRestartForOptions.mockResolvedValue(true);
    mockManager.terminate.mockImplementation(() => {
      running = false;
    });

    const response = await POST(
      new Request("http://localhost/api/session/init", {
        method: "POST",
        body: JSON.stringify({
          airplaneMode: true,
          currentPage: "/browse",
          themeMode: "dark",
        }),
      }) as never,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      alreadyRunning: false,
      restarted: true,
      cliId: "claude",
      pid: 1234,
      lastSessionId: "session-1",
    });
    expect(mockManager.terminate).toHaveBeenCalledTimes(1);
    expect(mockManager.initialize).toHaveBeenCalledWith({
      airplaneMode: true,
      airplaneLocalModel: null,
      currentPage: "/browse",
      themeMode: "dark",
    });
  });

  it("returns JSON 500 when restart reconciliation fails", async () => {
    mockManager.isRunning.mockReturnValue(true);
    mockManager.shouldRestartForOptions.mockRejectedValue(
      new Error("canonical airplane status failed"),
    );

    const response = await POST(
      new Request("http://localhost/api/session/init", {
        method: "POST",
      }) as never,
    );

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      error: "canonical airplane status failed",
    });
    expect(mockManager.terminate).not.toHaveBeenCalled();
    expect(mockManager.initialize).not.toHaveBeenCalled();
  });

  it("returns a session-owner conflict response when prewarm is owned elsewhere", async () => {
    mockManager.initialize.mockRejectedValue(
      new SessionOwnerConflictError("session-1", {
        session_id: "session-1",
        surface: "dashboard-pty",
        pid: 26006,
        host: "Gurs-MacBook-Air.local",
        cli_id: "claude",
      }),
    );

    const response = await POST(
      new Request("http://localhost/api/session/init", {
        method: "POST",
      }) as never,
    );

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "SESSION_OWNED_ELSEWHERE",
      sessionId: "session-1",
      owner: {
        surface: "dashboard-pty",
        pid: 26006,
      },
    });
  });
});
