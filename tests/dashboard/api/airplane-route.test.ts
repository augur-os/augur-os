/**
 * @jest-environment node
 */

import { POST } from "@/app/api/airplane/route";

jest.mock("@/lib/mcp/MCPBridge", () => ({
  callMCPTool: jest.fn().mockResolvedValue({
    isError: false,
    content: [
      { type: "text", text: JSON.stringify({ success: true, enabled: true }) },
    ],
  }),
  extractContextFromRequest: jest
    .fn()
    .mockReturnValue({ current_page: "/command/airplane" }),
  MCPBridge: {
    extractText: jest.fn(
      (r: { content?: Array<{ type?: string; text?: string }> }) =>
        r.content?.[0]?.text ?? "",
    ),
  },
}));

function requestWithBody(body: string): Request {
  return new Request("http://localhost/api/airplane", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}

describe("POST /api/airplane", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("calls toggle-airplane-mode with action on", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = requestWithBody(JSON.stringify({ action: "on" }));

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual({ success: true, enabled: true });
    expect(callMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "on" },
      { current_page: "/command/airplane" },
    );
  });

  it("accepts action off", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = requestWithBody(JSON.stringify({ action: "off" }));

    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(callMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "off" },
      { current_page: "/command/airplane" },
    );
  });

  it("accepts action toggle", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = requestWithBody(JSON.stringify({ action: "toggle" }));

    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(callMCPTool).toHaveBeenCalledWith(
      "toggle-airplane-mode",
      { action: "toggle" },
      { current_page: "/command/airplane" },
    );
  });

  it("returns 400 for invalid action without calling MCP", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = requestWithBody(JSON.stringify({ action: "sleep" }));

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body).toEqual({ error: "action must be one of: on, off, toggle" });
    expect(callMCPTool).not.toHaveBeenCalled();
  });

  it("returns 400 for invalid JSON", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    const req = requestWithBody("{");

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body).toEqual({ error: "invalid JSON body" });
    expect(callMCPTool).not.toHaveBeenCalled();
  });

  it("returns 500 when MCP reports an error", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    callMCPTool.mockResolvedValueOnce({
      isError: true,
      content: [{ type: "text", text: "permission denied" }],
    });
    const req = requestWithBody(JSON.stringify({ action: "toggle" }));

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(500);
    expect(body).toEqual({ error: "permission denied" });
  });

  it("returns raw text when MCP returns non-JSON text", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    callMCPTool.mockResolvedValueOnce({
      isError: false,
      content: [{ type: "text", text: "airplane mode toggled" }],
    });
    const req = requestWithBody(JSON.stringify({ action: "toggle" }));

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual({ raw: "airplane mode toggled" });
  });

  it("returns an empty object when MCP returns empty text", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    callMCPTool.mockResolvedValueOnce({
      isError: false,
      content: [{ type: "text", text: "   " }],
    });
    const req = requestWithBody(JSON.stringify({ action: "toggle" }));

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual({});
  });

  it("returns 500 JSON when callMCPTool throws", async () => {
    const { callMCPTool } = require("@/lib/mcp/MCPBridge");
    callMCPTool.mockRejectedValueOnce(new Error("MCP unavailable"));
    const req = requestWithBody(JSON.stringify({ action: "toggle" }));

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(500);
    expect(body.error).toContain("MCP unavailable");
  });

  it("returns 500 JSON when context extraction throws", async () => {
    const {
      callMCPTool,
      extractContextFromRequest,
    } = require("@/lib/mcp/MCPBridge");
    extractContextFromRequest.mockImplementationOnce(() => {
      throw new Error("bad request context");
    });
    const req = requestWithBody(JSON.stringify({ action: "toggle" }));

    const res = await POST(req);
    const body = await res.json();

    expect(res.status).toBe(500);
    expect(body.error).toContain("bad request context");
    expect(callMCPTool).not.toHaveBeenCalled();
  });
});
