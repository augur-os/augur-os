/**
 * @jest-environment node
 */

import { POST } from "@/app/api/session/continue/route";
import { getSessionManager } from "@/lib/session/SessionManager";

const mockManager = {
  isRunning: jest.fn(),
  hasActiveConversation: jest.fn(),
  getLastSessionId: jest.fn(),
  saveSessionId: jest.fn(),
  initialize: jest.fn(),
  sendMessage: jest.fn(),
  terminate: jest.fn(),
  terminateActiveConversations: jest.fn(),
  getCliId: jest.fn(),
  getPid: jest.fn(),
};

jest.mock("@/lib/session/SessionManager", () => ({
  getSessionManager: jest.fn(() => mockManager),
}));

describe("POST /api/session/continue", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockManager.isRunning.mockReturnValue(false);
    mockManager.hasActiveConversation.mockReturnValue(false);
    mockManager.getLastSessionId.mockReturnValue(null);
    mockManager.initialize.mockResolvedValue(undefined);
    mockManager.getCliId.mockReturnValue("claude");
    mockManager.getPid.mockReturnValue(1234);
  });

  it("blocks remote requests before touching the CLI session", async () => {
    const response = await POST(
      new Request("http://localhost/api/session/continue", {
        method: "POST",
        headers: { "x-remote-user": "true" },
        body: JSON.stringify({ sessionId: "session-1", answer: "done" }),
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

  it("returns a collision when a conversation is already active", async () => {
    mockManager.hasActiveConversation.mockReturnValue(true);

    const response = await POST(
      new Request("http://localhost/api/session/continue", {
        method: "POST",
        body: JSON.stringify({ sessionId: "session-1", answer: "done" }),
      }) as never,
    );

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({
      collision: true,
      message: "Session already active",
    });
    expect(mockManager.initialize).not.toHaveBeenCalled();
    expect(mockManager.sendMessage).not.toHaveBeenCalled();
  });

  it("saves the session id, initializes, and sends the exact continuation prompt", async () => {
    const response = await POST(
      new Request("http://localhost/api/session/continue", {
        method: "POST",
        body: JSON.stringify({
          sessionId: "session-42",
          answer: "  The prior answer\nwith spacing  ",
        }),
      }) as never,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      cliId: "claude",
      pid: 1234,
    });
    expect(mockManager.saveSessionId).toHaveBeenCalledWith("session-42");
    expect(mockManager.initialize).toHaveBeenCalledTimes(1);
    expect(mockManager.sendMessage).toHaveBeenCalledWith(
      "Previous result:\n  The prior answer\nwith spacing  \n\nContinue from here.",
    );
    expect(mockManager.saveSessionId.mock.invocationCallOrder[0]).toBeLessThan(
      mockManager.initialize.mock.invocationCallOrder[0],
    );
  });

  it("forces through an active conversation without returning a collision", async () => {
    mockManager.isRunning.mockReturnValue(false);
    mockManager.hasActiveConversation.mockReturnValue(true);
    mockManager.getLastSessionId.mockReturnValue("old-session");

    const response = await POST(
      new Request("http://localhost/api/session/continue", {
        method: "POST",
        body: JSON.stringify({
          sessionId: "new-session",
          answer: "New answer",
          force: true,
        }),
      }) as never,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      cliId: "claude",
      pid: 1234,
    });
    expect(mockManager.terminate).toHaveBeenCalledTimes(1);
    expect(mockManager.terminateActiveConversations).toHaveBeenCalledTimes(1);
    expect(mockManager.saveSessionId).toHaveBeenCalledWith("new-session");
    expect(mockManager.initialize).toHaveBeenCalledTimes(1);
    expect(mockManager.sendMessage).toHaveBeenCalledWith(
      "Previous result:\nNew answer\n\nContinue from here.",
    );
  });

  it("replaces an active conversation even when the requested session is already saved", async () => {
    mockManager.isRunning.mockReturnValue(false);
    mockManager.hasActiveConversation.mockReturnValue(true);
    mockManager.getLastSessionId.mockReturnValue("same-session");

    const response = await POST(
      new Request("http://localhost/api/session/continue", {
        method: "POST",
        body: JSON.stringify({
          sessionId: "same-session",
          answer: "Replacement answer",
          force: true,
        }),
      }) as never,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      cliId: "claude",
      pid: 1234,
    });
    expect(mockManager.terminate).not.toHaveBeenCalled();
    expect(mockManager.terminateActiveConversations).toHaveBeenCalledTimes(1);
    expect(mockManager.saveSessionId).not.toHaveBeenCalled();
    expect(mockManager.initialize).toHaveBeenCalledTimes(1);
    expect(mockManager.sendMessage).toHaveBeenCalledWith(
      "Previous result:\nReplacement answer\n\nContinue from here.",
    );
  });

  it("reinitializes after force-replacing a running saved session", async () => {
    let running = true;
    mockManager.isRunning.mockImplementation(() => running);
    mockManager.terminateActiveConversations.mockImplementation(() => {
      running = false;
    });
    mockManager.hasActiveConversation.mockReturnValue(true);
    mockManager.getLastSessionId.mockReturnValue("same-session");

    const response = await POST(
      new Request("http://localhost/api/session/continue", {
        method: "POST",
        body: JSON.stringify({
          sessionId: "same-session",
          answer: "Replacement answer",
          force: true,
        }),
      }) as never,
    );

    expect(response.status).toBe(200);
    expect(mockManager.terminateActiveConversations).toHaveBeenCalledTimes(1);
    expect(mockManager.initialize).toHaveBeenCalledTimes(1);
    expect(mockManager.sendMessage).toHaveBeenCalledWith(
      "Previous result:\nReplacement answer\n\nContinue from here.",
    );
  });
});
