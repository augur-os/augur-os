/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";
import {
  blocksDiscoverExecute,
  blocksReadExecute,
  blocksConfigureExecute,
  blocksActExecute,
} from "@/lib/webmcp/tools/blocks";
import type { BlockState } from "@/lib/webmcp/types";

// Mock the block registry
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

const makeBlock = (overrides: Partial<BlockState> = {}): BlockState => ({
  blockId: "career:pipeline",
  instanceId: "inst-1",
  type: "data-table",
  mounted: true,
  renderState: "ready",
  config: { stage_filter: "all" },
  data: [{ company: "Acme", stage: "active" }],
  lastUpdated: Date.now(),
  ...overrides,
});

describe("blocks.discover", () => {
  let registry: StateRegistry;
  beforeEach(() => { registry = new StateRegistry(); });

  it("returns all blocks from registry", async () => {
    const result = await blocksDiscoverExecute({}, registry);
    expect(result.blocks).toHaveLength(2);
  });

  it("filters by hub", async () => {
    const result = await blocksDiscoverExecute({ hub: "career" }, registry);
    expect(result.blocks).toHaveLength(1);
    expect(result.blocks[0].id).toBe("career:pipeline");
  });

  it("filters by type", async () => {
    const result = await blocksDiscoverExecute({ type: "progress" }, registry);
    expect(result.blocks).toHaveLength(1);
    expect(result.blocks[0].id).toBe("finance:budget");
  });

  it("filters by mounted — only shows mounted blocks", async () => {
    registry.reportBlock(makeBlock());
    const result = await blocksDiscoverExecute({ mounted: true }, registry);
    expect(result.blocks).toHaveLength(1);
    expect(result.blocks[0].mounted).toBe(true);
  });

  it("search filters by title", async () => {
    const result = await blocksDiscoverExecute({ search: "pipeline" }, registry);
    expect(result.blocks).toHaveLength(1);
  });
});

describe("blocks.read", () => {
  let registry: StateRegistry;
  beforeEach(() => { registry = new StateRegistry(); });

  it("reads mounted block state", async () => {
    registry.reportBlock(makeBlock());
    const result = await blocksReadExecute({ blockId: "career:pipeline" }, registry);
    expect(result.blockId).toBe("career:pipeline");
    expect(result.mounted).toBe(true);
    expect(result.renderState).toBe("ready");
    expect(result.data).toEqual([{ company: "Acme", stage: "active" }]);
  });

  it("returns NOT_FOUND for unknown blockId", async () => {
    const result = await blocksReadExecute({ blockId: "x:nope" }, registry);
    expect(result.error).toBe(true);
    expect(result.code).toBe("NOT_FOUND");
  });

  it("returns UNMOUNTED for unmounted block without config override", async () => {
    const result = await blocksReadExecute({ blockId: "career:pipeline" }, registry);
    expect(result.error).toBe(true);
    expect(result.code).toBe("UNMOUNTED");
  });

  it("includes renderInfo when includeState is true", async () => {
    registry.reportBlock(makeBlock({ data: [{ a: 1 }, { a: 2 }] }));
    const result = await blocksReadExecute(
      { blockId: "career:pipeline", includeState: true },
      registry,
    );
    expect(result.renderInfo).toBeDefined();
    expect(result.renderInfo.rowCount).toBe(2);
  });
});

describe("blocks.configure", () => {
  let registry: StateRegistry;
  beforeEach(() => { registry = new StateRegistry(); });

  it("updates block config", async () => {
    registry.reportBlock(makeBlock());
    const result = await blocksConfigureExecute(
      { blockId: "career:pipeline", config: { stage_filter: "active" }, waitForSettle: false },
      registry,
    );
    expect(result.success).toBe(true);
    expect(result.previousConfig).toEqual({ stage_filter: "all" });
    expect(result.newConfig).toEqual({ stage_filter: "active" });
  });

  it("returns UNMOUNTED for unmounted block", async () => {
    const result = await blocksConfigureExecute(
      { blockId: "career:pipeline", config: { stage_filter: "active" } },
      registry,
    );
    expect(result.error).toBe(true);
    expect(result.code).toBe("UNMOUNTED");
  });
});

describe("blocks.act", () => {
  let registry: StateRegistry;
  beforeEach(() => { registry = new StateRegistry(); });

  it("handles refresh action", async () => {
    registry.reportBlock(makeBlock());
    const result = await blocksActExecute(
      { blockId: "career:pipeline", action: "refresh" },
      registry,
    );
    expect(result.success).toBe(true);
    expect(result.action).toBe("refresh");
  });

  it("returns UNMOUNTED for unmounted block", async () => {
    const result = await blocksActExecute(
      { blockId: "career:pipeline", action: "refresh" },
      registry,
    );
    expect(result.error).toBe(true);
    expect(result.code).toBe("UNMOUNTED");
  });

  it("returns INVALID_ACTION for unknown action", async () => {
    registry.reportBlock(makeBlock());
    const result = await blocksActExecute(
      { blockId: "career:pipeline", action: "teleport" },
      registry,
    );
    expect(result.error).toBe(true);
    expect(result.code).toBe("INVALID_ACTION");
  });
});
