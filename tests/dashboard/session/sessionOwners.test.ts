/** @jest-environment node */

const mockCallMCPTool = jest.fn();

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: (...args: unknown[]) => mockCallMCPTool(...args),
  MCPBridge: {
    extractText: (result: { content?: Array<{ type: string; text: string }> }) =>
      result.content
        ?.filter((item) => item.type === "text")
        .map((item) => item.text)
        .join("\n") ?? "",
  },
}));

import {
  SessionOwnerConflictError,
  claimDashboardSessionOwner,
  releaseDashboardSessionOwner,
} from "@/lib/session/sessionOwners";

function mcpJson(value: unknown) {
  return {
    content: [{ type: "text", text: JSON.stringify(value) }],
  };
}

describe("dashboard session owner helpers", () => {
  beforeEach(() => {
    mockCallMCPTool.mockReset();
  });

  it("claims dashboard PTY ownership through the MCP tool", async () => {
    mockCallMCPTool.mockResolvedValueOnce(
      mcpJson({
        ok: true,
        owner: {
          session_id: "session-123",
          surface: "dashboard-pty",
          pid: 2468,
        },
      }),
    );

    await expect(
      claimDashboardSessionOwner({
        cliId: "claude",
        pid: 2468,
        sessionId: "session-123",
      }),
    ).resolves.toMatchObject({
      session_id: "session-123",
      surface: "dashboard-pty",
      pid: 2468,
    });
    expect(mockCallMCPTool).toHaveBeenCalledWith("session-claim", {
      cli_id: "claude",
      pid: 2468,
      session_id: "session-123",
      surface: "dashboard-pty",
    });
  });

  it("throws a typed conflict when another owner has the session", async () => {
    mockCallMCPTool.mockResolvedValueOnce(
      mcpJson({
        ok: false,
        conflict: {
          session_id: "session-123",
          surface: "native-terminal",
          pid: 9999,
          host: "other-host",
        },
      }),
    );

    await expect(
      claimDashboardSessionOwner({
        cliId: "claude",
        pid: 2468,
        sessionId: "session-123",
      }),
    ).rejects.toMatchObject({
      name: "SessionOwnerConflictError",
      owner: {
        surface: "native-terminal",
        pid: 9999,
      },
    } satisfies Partial<SessionOwnerConflictError>);
  });

  it("releases dashboard PTY ownership with the matching PID", async () => {
    mockCallMCPTool.mockResolvedValueOnce(mcpJson({ ok: true, released: true }));

    await expect(
      releaseDashboardSessionOwner({
        pid: 2468,
        sessionId: "session-123",
      }),
    ).resolves.toBe(true);
    expect(mockCallMCPTool).toHaveBeenCalledWith("session-release", {
      pid: 2468,
      session_id: "session-123",
      surface: "dashboard-pty",
    });
  });
});
