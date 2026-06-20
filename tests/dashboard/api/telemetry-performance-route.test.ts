/**
 * @jest-environment node
 */

import { POST } from "@/app/api/telemetry/performance/route";

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

describe("POST /api/telemetry/performance", () => {
  it("persists performance telemetry via save-performance-metric", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = new Request("http://localhost/api/telemetry/performance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: "/life/apple",
        metric: "load",
        duration: 1.25,
        timestamp: "2026-04-07T11:00:00.000Z",
      }),
    });

    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(callMCPTool).toHaveBeenCalledWith(
      "save-performance-metric",
      {
        path: "/life/apple",
        metric: "load",
        duration: 1.25,
        timestamp: "2026-04-07T11:00:00.000Z",
      },
      { clientId: "test" },
    );
  });

  it("returns 400 when required fields are missing", async () => {
    const req = new Request("http://localhost/api/telemetry/performance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: "/life/apple", metric: "load" }),
    });

    const res = await POST(req);
    expect(res.status).toBe(400);
  });
});
