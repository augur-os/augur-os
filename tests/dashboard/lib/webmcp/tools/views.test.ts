/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach, afterEach, jest } from "@jest/globals";
import { viewsManageExecute, viewsComposeExecute } from "@/lib/webmcp/tools/views";

// Mock global fetch
const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch;

const makeView = (overrides: Record<string, unknown> = {}) => ({
  id: "view-1",
  title: "My Dashboard",
  icon: "LayoutDashboard",
  pinned: false,
  createdAt: "2026-03-14T00:00:00.000Z",
  updatedAt: "2026-03-14T00:00:00.000Z",
  layout: { columns: 12, rowHeight: 80 },
  blocks: [],
  ...overrides,
});

function mockResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : status === 404 ? "Not Found" : "Error",
    json: () => Promise.resolve(body),
  } as Response);
}

beforeEach(() => {
  mockFetch.mockClear();
});

afterEach(() => {
  mockFetch.mockReset();
});

// ─── views.manage ─────────────────────────────────────────────────────────────

describe("viewsManageExecute — list", () => {
  it("calls GET /api/views and returns views array", async () => {
    const views = [makeView(), makeView({ id: "view-2", title: "Work" })];
    mockFetch.mockReturnValueOnce(mockResponse(views));

    const result = await viewsManageExecute({ action: "list" });

    expect(mockFetch).toHaveBeenCalledWith("/api/views");
    expect(result.success).toBe(true);
    expect(result.views).toHaveLength(2);
  });

  it("returns FETCH_FAILED when API responds with error", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({ error: "Server error" }, 500));

    const result = await viewsManageExecute({ action: "list" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("FETCH_FAILED");
  });
});

describe("viewsManageExecute — create", () => {
  it("calls POST /api/views with title and returns created view", async () => {
    const view = makeView({ id: "view-new", title: "New View" });
    mockFetch.mockReturnValueOnce(mockResponse(view));

    const result = await viewsManageExecute({ action: "create", title: "New View" });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/views",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.title).toBe("New View");
    expect(result.success).toBe(true);
    expect(result.view).toEqual(view);
  });

  it("returns INVALID_CONFIG when title is missing", async () => {
    const result = await viewsManageExecute({ action: "create" });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });

  it("passes optional fields (layout, icon, pinned) to POST body", async () => {
    mockFetch.mockReturnValueOnce(mockResponse(makeView()));

    await viewsManageExecute({
      action: "create",
      title: "Pinned",
      layout: { columns: 6, rowHeight: 60 },
      icon: "Star",
      pinned: true,
    });

    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.layout).toEqual({ columns: 6, rowHeight: 60 });
    expect(body.icon).toBe("Star");
    expect(body.pinned).toBe(true);
  });
});

describe("viewsManageExecute — read", () => {
  it("calls GET /api/views/{viewId} and returns view", async () => {
    const view = makeView();
    mockFetch.mockReturnValueOnce(mockResponse(view));

    const result = await viewsManageExecute({ action: "read", viewId: "view-1" });

    expect(mockFetch).toHaveBeenCalledWith("/api/views/view-1");
    expect(result.success).toBe(true);
    expect(result.view).toEqual(view);
  });

  it("returns INVALID_CONFIG when viewId is missing", async () => {
    const result = await viewsManageExecute({ action: "read" });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });

  it("returns NOT_FOUND on 404 response", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({ error: "not found" }, 404));

    const result = await viewsManageExecute({ action: "read", viewId: "view-ghost" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("NOT_FOUND");
  });
});

describe("viewsManageExecute — update", () => {
  it("calls PUT /api/views/{viewId} with updates and returns view", async () => {
    const view = makeView({ title: "Renamed" });
    mockFetch.mockReturnValueOnce(mockResponse(view));

    const result = await viewsManageExecute({
      action: "update",
      viewId: "view-1",
      title: "Renamed",
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/views/view-1",
      expect.objectContaining({ method: "PUT" }),
    );
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.title).toBe("Renamed");
    expect(result.success).toBe(true);
    expect(result.view).toEqual(view);
  });

  it("returns INVALID_CONFIG when viewId is missing", async () => {
    const result = await viewsManageExecute({ action: "update", title: "X" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });

  it("returns NOT_FOUND on 404 response", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({ error: "not found" }, 404));

    const result = await viewsManageExecute({ action: "update", viewId: "view-ghost", title: "X" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("NOT_FOUND");
  });
});

describe("viewsManageExecute — delete", () => {
  it("calls DELETE /api/views/{viewId} and returns success", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({}));

    const result = await viewsManageExecute({ action: "delete", viewId: "view-1" });

    expect(mockFetch).toHaveBeenCalledWith("/api/views/view-1", { method: "DELETE" });
    expect(result.success).toBe(true);
    expect(result.view).toBeUndefined();
  });

  it("returns INVALID_CONFIG when viewId is missing", async () => {
    const result = await viewsManageExecute({ action: "delete" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });

  it("returns NOT_FOUND on 404 response", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({ error: "not found" }, 404));

    const result = await viewsManageExecute({ action: "delete", viewId: "view-ghost" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("NOT_FOUND");
  });
});

describe("viewsManageExecute — fetch throws", () => {
  it("returns FETCH_FAILED when fetch rejects", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error") as never);

    const result = await viewsManageExecute({ action: "list" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("FETCH_FAILED");
    expect(result.message).toContain("Network error");
  });
});

// ─── views.compose ────────────────────────────────────────────────────────────

describe("viewsComposeExecute — add", () => {
  it("calls POST /api/views/{viewId}/blocks and returns view", async () => {
    const view = makeView({
      blocks: [{ instanceId: "inst-1", blockId: "career:pipeline", config: {}, position: { x: 0, y: 0, w: 4, h: 3 } }],
    });
    mockFetch.mockReturnValueOnce(mockResponse(view));

    const result = await viewsComposeExecute({
      viewId: "view-1",
      action: "add",
      blockId: "career:pipeline",
      instanceId: "inst-1",
      position: { x: 0, y: 0, w: 4, h: 3 },
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/views/view-1/blocks",
      expect.objectContaining({ method: "POST" }),
    );
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.blockId).toBe("career:pipeline");
    expect(body.instanceId).toBe("inst-1");
    expect(result.success).toBe(true);
    expect(result.view).toEqual(view);
  });

  it("returns INVALID_CONFIG when blockId is missing", async () => {
    const result = await viewsComposeExecute({ viewId: "view-1", action: "add" });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });

  it("returns NOT_FOUND on 404 response", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({ error: "not found" }, 404));

    const result = await viewsComposeExecute({
      viewId: "view-ghost",
      action: "add",
      blockId: "career:pipeline",
    });

    expect(result.error).toBe(true);
    expect(result.code).toBe("NOT_FOUND");
  });
});

describe("viewsComposeExecute — remove", () => {
  it("calls DELETE /api/views/{viewId}/blocks/{instanceId} and returns view", async () => {
    const view = makeView({ blocks: [] });
    mockFetch.mockReturnValueOnce(mockResponse(view));

    const result = await viewsComposeExecute({
      viewId: "view-1",
      action: "remove",
      instanceId: "inst-1",
    });

    expect(mockFetch).toHaveBeenCalledWith("/api/views/view-1/blocks/inst-1", { method: "DELETE" });
    expect(result.success).toBe(true);
    expect(result.view).toEqual(view);
  });

  it("returns INVALID_CONFIG when instanceId is missing", async () => {
    const result = await viewsComposeExecute({ viewId: "view-1", action: "remove" });

    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });
});

describe("viewsComposeExecute — move", () => {
  it("calls PUT /api/views/{viewId} with blockPositions and returns view", async () => {
    const view = makeView();
    mockFetch.mockReturnValueOnce(mockResponse(view));

    const result = await viewsComposeExecute({
      viewId: "view-1",
      action: "move",
      instanceId: "inst-1",
      position: { x: 4, y: 2, w: 6, h: 4 },
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/views/view-1",
      expect.objectContaining({ method: "PUT" }),
    );
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.blockPositions).toEqual([
      { instanceId: "inst-1", position: { x: 4, y: 2, w: 6, h: 4 } },
    ]);
    expect(result.success).toBe(true);
  });

  it("returns INVALID_CONFIG when instanceId is missing", async () => {
    const result = await viewsComposeExecute({
      viewId: "view-1",
      action: "move",
      position: { x: 0, y: 0, w: 4, h: 3 },
    });

    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });

  it("returns INVALID_CONFIG when position is missing", async () => {
    const result = await viewsComposeExecute({
      viewId: "view-1",
      action: "move",
      instanceId: "inst-1",
    });

    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_CONFIG");
  });
});

describe("viewsComposeExecute — fetch throws", () => {
  it("returns FETCH_FAILED when fetch rejects", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Connection refused") as never);

    const result = await viewsComposeExecute({
      viewId: "view-1",
      action: "add",
      blockId: "career:pipeline",
    });

    expect(result.error).toBe(true);
    expect(result.code).toBe("FETCH_FAILED");
    expect(result.message).toContain("Connection refused");
  });
});
