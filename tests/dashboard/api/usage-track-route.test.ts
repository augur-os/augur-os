/**
 * @jest-environment node
 */

import { POST } from "@/app/api/usage/track/route";

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

describe("POST /api/usage/track", () => {
  it("persists usage telemetry via set-config", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = new Request("http://localhost/api/usage/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        page: "/life/apple",
        action: "view",
        timestamp: "2026-04-07T11:00:00.000Z",
      }),
    });

    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(callMCPTool).toHaveBeenCalledWith(
      "set-config",
      {
        scope: "usage-stats",
        page: "/life/apple",
        action: "view",
        timestamp: "2026-04-07T11:00:00.000Z",
      },
      { clientId: "test" },
    );
  });

  it("returns 400 when page is missing", async () => {
    const req = new Request("http://localhost/api/usage/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "view" }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
  });
});
