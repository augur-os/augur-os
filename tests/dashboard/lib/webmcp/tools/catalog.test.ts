/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach, afterEach, jest } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";
import type { PageState } from "@/lib/webmcp/types";

// Mock the block registry (same fixture as blocks.test.ts)
jest.mock("@/lib/blocks/generated-block-registry", () => ({
  BLOCK_REGISTRY: {
    "career:pipeline": {
      id: "career:pipeline",
      type: "data-table",
      title: "Job Pipeline",
      icon: "Briefcase",
      configSchema: {
        stage_filter: { type: "enum", options: ["all", "inbox", "active"], default: "all" },
      },
      dataSource: { mcpTool: "get-career-jobs" },
      hub: "career",
      skill: "career",
    },
    "finance:budget": {
      id: "finance:budget",
      type: "progress",
      title: "Budget",
      icon: "DollarSign",
      configSchema: { period: { type: "enum", options: ["Q1", "Q2", "Q3", "Q4"], default: "Q1" } },
      dataSource: { mcpTool: "get-finance-budget" },
      hub: "finance",
      skill: "finance",
    },
  },
}));

import {
  catalogSearchExecute,
  catalogPreviewExecute,
} from "@/lib/webmcp/tools/catalog";

// --- Fixtures ---
//
// ADR-806 retired the FILE-actions pipeline: catalog.search no longer fetches
// `list-action-buttons` and never returns `type: "action"` results. The catalog
// is now blocks + pages only, so there is no actions fixture and no actions
// fetch path to exercise here.

const makePage = (overrides: Partial<PageState> = {}): PageState => ({
  pageId: "career:companies",
  skillId: "career",
  hub: "career",
  path: "/career/companies",
  mounted: true,
  renderState: "ready",
  blocks: ["career:pipeline"],
  lastUpdated: Date.now(),
  ...overrides,
});

// --- catalog.search tests ---

describe("catalog.search", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  afterEach(() => {
    delete (global as any).fetch;
  });

  it("finds blocks by title keyword", async () => {
    const result = await catalogSearchExecute({ query: "agents" }, registry);
    expect("error" in result).toBe(false);
    if ("results" in result) {
      expect(result.results.some((r) => r.id === "ai:agents")).toBe(true);
      expect(result.results.every((r) => r.type === "block")).toBe(true);
    }
  });

  it("finds blocks by id keyword", async () => {
    const result = await catalogSearchExecute({ query: "knowledge:documents" }, registry);
    if ("results" in result) {
      expect(result.results.some((r) => r.id === "knowledge:documents")).toBe(true);
    }
  });

  it("finds pages by pageId keyword", async () => {
    registry.reportPage(makePage());
    const result = await catalogSearchExecute({ query: "companies" }, registry);
    if ("results" in result) {
      expect(result.results.some((r) => r.id === "career:companies" && r.type === "page")).toBe(
        true,
      );
    }
  });

  it("limits to specified types — blocks only", async () => {
    const result = await catalogSearchExecute({ query: "career", types: ["block"] }, registry);
    if ("results" in result) {
      expect(result.results.every((r) => r.type === "block")).toBe(true);
    }
  });

  it("limits to specified types — pages only", async () => {
    registry.reportPage(makePage());
    const result = await catalogSearchExecute(
      { query: "career", types: ["page"] },
      registry,
    );
    if ("results" in result) {
      expect(result.results.every((r) => r.type === "page")).toBe(true);
    }
  });

  it("exact matches rank above starts-with rank above contains", async () => {
    registry.reportPage(makePage({ pageId: "ai:agents", hub: "workspace", path: "/workspace/agents", skillId: "ai" }));
    // "agents" exactly matches a page title and is contained in the block title; use the id
    // which exactly matches the block id
    const result = await catalogSearchExecute({ query: "ai:agents", types: ["block", "page"] }, registry);
    if ("results" in result) {
      // Block id "ai:agents" is an exact match (score 3) — should come first
      expect(result.results[0].id).toBe("ai:agents");
      expect(result.results[0].type).toBe("block");
    }
  });

  it("returns total matching results count", async () => {
    const result = await catalogSearchExecute({ query: "budget" }, registry);
    if ("results" in result) {
      expect(result.total).toBe(result.results.length);
    }
  });

  it("returns empty results for no match", async () => {
    const result = await catalogSearchExecute({ query: "zzznomatch" }, registry);
    if ("results" in result) {
      expect(result.results).toHaveLength(0);
      expect(result.total).toBe(0);
    }
  });

  it("result items include hub for blocks", async () => {
    const result = await catalogSearchExecute({ query: "agents", types: ["block"] }, registry);
    if ("results" in result) {
      const block = result.results.find((r) => r.id === "ai:agents");
      expect(block?.hub).toBe("workspace");
    }
  });
});

// --- catalog.preview tests ---

describe("catalog.preview", () => {
  afterEach(() => {
    delete (global as any).fetch;
  });

  it("returns block metadata and data on success", async () => {
    const mockData = [{ name: "Claude", status: "running" }];
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: mockData }),
    } as Response);

    const result = await catalogPreviewExecute({ blockId: "ai:agents" });
    expect("error" in result).toBe(false);
    if ("blockId" in result) {
      expect(result.blockId).toBe("ai:agents");
      expect(result.type).toBe("ops-board");
      expect(result.title).toBe("Agents");
      expect(result.data).toEqual(mockData);
    }
  });

  it("POSTs to /api/blocks/data with correct payload", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: [] }),
    } as Response);
    (global as any).fetch = mockFetch;

    await catalogPreviewExecute({ blockId: "ai:agents", config: { show_offline: false } });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/blocks/data",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          tool: "manage-cli-agents",
          args: { show_offline: false },
        }),
      }),
    );
  });

  it("uses empty args when config is not provided", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    } as Response);
    (global as any).fetch = mockFetch;

    await catalogPreviewExecute({ blockId: "ai:agents" });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/blocks/data",
      expect.objectContaining({
        body: JSON.stringify({ tool: "manage-cli-agents", args: {} }),
      }),
    );
  });

  it("unwraps data from { data: ... } response envelope", async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: [1, 2, 3] }),
    } as Response);

    const result = await catalogPreviewExecute({ blockId: "ai:agents" });
    if ("data" in result) {
      expect(result.data).toEqual([1, 2, 3]);
    }
  });

  it("uses raw response when no data envelope", async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ total: 5, items: [] }),
    } as Response);

    const result = await catalogPreviewExecute({ blockId: "ai:agents" });
    if ("data" in result) {
      expect(result.data).toEqual({ total: 5, items: [] });
    }
  });

  it("returns NOT_FOUND for unknown blockId", async () => {
    const result = await catalogPreviewExecute({ blockId: "unknown:nope" });
    expect(result).toMatchObject({ error: true, code: "NOT_FOUND" });
  });

  it("returns FETCH_FAILED when API returns error status", async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      json: async () => ({}),
    } as Response);

    const result = await catalogPreviewExecute({ blockId: "ai:agents" });
    expect(result).toMatchObject({ error: true, code: "FETCH_FAILED" });
  });

  it("returns FETCH_FAILED when fetch throws", async () => {
    (global as any).fetch = jest.fn().mockRejectedValue(new Error("timeout"));

    const result = await catalogPreviewExecute({ blockId: "ai:agents" });
    expect(result).toMatchObject({
      error: true,
      code: "FETCH_FAILED",
      message: expect.stringContaining("timeout"),
    });
  });
});
