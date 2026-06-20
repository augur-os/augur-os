import { mcpCall } from "@/lib/mcp/client";

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("mcpCall", () => {
  beforeEach(() => mockFetch.mockReset());

  it("calls /api/mcp/tool with tool and args", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ count: 42 }),
    });

    const result = await mcpCall("get-count", { limit: 10 });
    expect(result).toEqual({ count: 42 });
    expect(mockFetch).toHaveBeenCalledWith("/api/mcp/tool", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool: "get-count", args: { limit: 10 } }),
      signal: undefined,
    });
  });

  it("defaults args to empty object", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    await mcpCall("health");
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.args).toEqual({});
  });

  it("throws on error response when no fallback", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: "tool failed" }),
    });

    await expect(mcpCall("bad-tool")).rejects.toThrow("tool failed");
  });

  it("returns fallback on error when fallback provided", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: "tool failed" }),
    });

    const result = await mcpCall("bad-tool", {}, { fallback: { data: null } });
    expect(result).toEqual({ data: null });
  });

  it("passes abort signal", async () => {
    const controller = new AbortController();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    await mcpCall("tool", {}, { signal: controller.signal });
    expect(mockFetch.mock.calls[0][1].signal).toBe(controller.signal);
  });
});
