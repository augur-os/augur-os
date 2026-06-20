/**
 * @jest-environment node
 */

import { GET, POST } from "@/app/api/mcp/tool/route";

const mockReconnect = jest.fn();

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: jest.fn().mockResolvedValue({
    isError: false,
    content: [{ type: "text", text: JSON.stringify({ count: 42 }) }],
  }),
  extractContextFromRequest: jest.fn().mockReturnValue({}),
  MCPBridge: {
    getInstance: jest.fn(() => ({ reconnect: mockReconnect })),
    extractText: jest.fn((r: { content?: Array<{ type?: string; text?: string }> }) => r.content?.[0]?.text ?? ""),
  },
}));

describe("GET /api/mcp/tool", () => {
  it("calls MCP tool with query params", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = new Request("http://localhost/api/mcp/tool?tool=get-count&limit=10");
    const res = await GET(req);
    const body = await res.json();
    expect(callMCPTool).toHaveBeenCalledWith("get-count", { limit: "10" }, {});
    expect(body.count).toBe(42);
  });

  it("returns 400 when tool param is missing", async () => {
    const req = new Request("http://localhost/api/mcp/tool?limit=10");
    const res = await GET(req);
    expect(res.status).toBe(400);
  });
});

describe("POST /api/mcp/tool", () => {
  it("calls wiki-report-data with JSON body args", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    callMCPTool.mockResolvedValueOnce({
      isError: false,
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: true,
            stats: { avg_quality_score: 98.81, rewrite_candidates: 0 },
          }),
        },
      ],
    });

    const req = new Request("http://localhost/api/mcp/tool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool: "wiki-report-data",
        args: {},
      }),
    });

    const res = await POST(req);
    const body = await res.json();

    expect(callMCPTool).toHaveBeenCalledWith("wiki-report-data", {}, {});
    expect(body).toEqual({
      success: true,
      stats: { avg_quality_score: 98.81, rewrite_candidates: 0 },
    });
  });

  it("returns a fallback envelope for missing optional plugin tools", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    callMCPTool.mockResolvedValueOnce({
      isError: true,
      content: [{ type: "text", text: "Unknown tool: plugin-events-list" }],
    });

    const req = new Request("http://localhost/api/mcp/tool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool: "plugin-events-list",
        args: {},
      }),
    });

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual({
      _fallback: true,
      _plugin: "daemon",
      _reason: "plugin_tool_unavailable",
      _error: "Unknown tool: plugin-events-list",
    });
  });

  it("reconnects once before failing a stale unknown core tool", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    callMCPTool.mockReset();
    mockReconnect.mockClear();
    callMCPTool
      .mockResolvedValueOnce({
        isError: true,
        content: [{ type: "text", text: "Unknown tool: check-system-permissions" }],
      })
      .mockResolvedValueOnce({
        isError: false,
        content: [{ type: "text", text: JSON.stringify({ ok: true }) }],
      });

    const req = new Request("http://localhost/api/mcp/tool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool: "check-system-permissions",
        args: {},
      }),
    });

    const res = await POST(req);
    const body = await res.json();

    expect(mockReconnect).toHaveBeenCalledTimes(1);
    expect(callMCPTool).toHaveBeenCalledTimes(2);
    expect(body).toEqual({ ok: true });
  });
});
