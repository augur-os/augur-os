/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";
import type { BlockState } from "@/lib/webmcp/types";

const makeBlock = (overrides: Partial<BlockState> = {}): BlockState => ({
  blockId: "career:pipeline",
  instanceId: "inst-1",
  type: "data-table",
  mounted: true,
  renderState: "ready",
  config: { stage_filter: "all" },
  data: [{ company: "Acme" }],
  lastUpdated: Date.now(),
  ...overrides,
});

describe("StateRegistry", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("reports and retrieves a block", () => {
    registry.reportBlock(makeBlock());
    expect(registry.getBlock("career:pipeline")).toBeDefined();
    expect(registry.getBlock("career:pipeline")!.renderState).toBe("ready");
  });

  it("updates an existing block", () => {
    registry.reportBlock(makeBlock());
    registry.reportBlock(makeBlock({ renderState: "loading" }));
    expect(registry.getBlock("career:pipeline")!.renderState).toBe("loading");
  });

  it("removes a block", () => {
    registry.reportBlock(makeBlock());
    registry.removeBlock("career:pipeline", "inst-1");
    expect(registry.getBlock("career:pipeline")).toBeUndefined();
  });

  it("lists all blocks", () => {
    registry.reportBlock(makeBlock({ blockId: "a:1", instanceId: "i1" }));
    registry.reportBlock(makeBlock({ blockId: "b:2", instanceId: "i2" }));
    expect(registry.getAllBlocks()).toHaveLength(2);
  });

  it("filters blocks by predicate", () => {
    registry.reportBlock(makeBlock({ blockId: "a:1", instanceId: "i1", type: "stat-card" }));
    registry.reportBlock(makeBlock({ blockId: "b:2", instanceId: "i2", type: "data-table" }));
    const tables = registry.filterBlocks((b) => b.type === "data-table");
    expect(tables).toHaveLength(1);
    expect(tables[0].blockId).toBe("b:2");
  });

  it("waitForSettle resolves when block state changes to ready", async () => {
    registry.reportBlock(makeBlock({ renderState: "loading" }));
    const promise = registry.waitForSettle("career:pipeline", 1000);
    registry.reportBlock(makeBlock({ renderState: "ready" }));
    const result = await promise;
    expect(result.renderState).toBe("ready");
  });

  it("waitForSettle resolves immediately if already settled", async () => {
    registry.reportBlock(makeBlock({ renderState: "ready" }));
    const result = await registry.waitForSettle("career:pipeline", 1000);
    expect(result.renderState).toBe("ready");
  });

  it("waitForSettle times out", async () => {
    registry.reportBlock(makeBlock({ renderState: "loading" }));
    await expect(registry.waitForSettle("career:pipeline", 50)).rejects.toThrow("timed out");
  });

  it("config change listeners are notified", () => {
    const calls: Record<string, unknown>[] = [];
    registry.onConfigChange("career:pipeline", (config) => calls.push(config));
    registry.setConfig("career:pipeline", { stage_filter: "active" });
    expect(calls).toHaveLength(1);
    expect(calls[0]).toEqual({ stage_filter: "active" });
  });

  it("refresh listeners are notified", () => {
    let called = false;
    registry.onRefresh("career:pipeline", () => { called = true; });
    registry.triggerRefresh("career:pipeline");
    expect(called).toBe(true);
  });

  it("removes listeners on unsubscribe", () => {
    const calls: unknown[] = [];
    const unsub = registry.onConfigChange("career:pipeline", (c) => calls.push(c));
    unsub();
    registry.setConfig("career:pipeline", { x: 1 });
    expect(calls).toHaveLength(0);
  });
});

describe("Page state", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("reports and retrieves a page", () => {
    registry.reportPage({
      pageId: "career:companies",
      skillId: "career",
      hub: "career",
      path: "/career/career/companies",
      mounted: true,
      renderState: "ready",
      blocks: ["career:companies"],
      lastUpdated: Date.now(),
    });
    expect(registry.getPage("career:companies")).toBeDefined();
    expect(registry.getPage("career:companies")!.mounted).toBe(true);
  });

  it("removes a page", () => {
    registry.reportPage({
      pageId: "career:companies",
      skillId: "career",
      hub: "career",
      path: "/career/career/companies",
      mounted: true,
      renderState: "ready",
      blocks: [],
      lastUpdated: Date.now(),
    });
    registry.removePage("career:companies");
    expect(registry.getPage("career:companies")).toBeUndefined();
  });
});
