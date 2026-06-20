/**
 * @jest-environment node
 */

import { POST } from "@/app/api/focus-state/route";

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: jest.fn().mockResolvedValue({
    isError: false,
    content: [{ type: "text", text: JSON.stringify({ success: true }) }],
  }),
  extractContextFromRequest: jest.fn().mockReturnValue({ clientId: "test" }),
  MCPBridge: {
    extractText: jest.fn(
      (r: { content?: Array<{ type?: string; text?: string }> }) =>
        r.content?.[0]?.text ?? "",
    ),
  },
}));

describe("POST /api/focus-state", () => {
  it("persists focus state via set-config", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = new Request("http://localhost/api/focus-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_page: "/brain",
        skill_name: "brain",
        bundle: "brain",
        session_id: "dashboard-main",
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(callMCPTool).toHaveBeenCalledWith(
      "set-config",
      {
        scope: "focus-state",
        current_page: "/brain",
        skill_name: "brain",
        bundle: "brain",
        session_id: "dashboard-main",
        source: "dashboard",
      },
      { clientId: "test" },
    );
  });

  it("returns 400 when required fields are missing", async () => {
    const req = new Request("http://localhost/api/focus-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_page: "/brain" }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
  });
});
