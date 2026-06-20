/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";
import { pagesDiscoverExecute, pagesReadExecute } from "@/lib/webmcp/tools/pages";

const makePage = (overrides = {}) => ({
  pageId: "career:companies",
  skillId: "career",
  hub: "career",
  path: "/career/career/companies",
  mounted: true,
  renderState: "ready" as const,
  blocks: ["career:companies"],
  lastUpdated: Date.now(),
  ...overrides,
});

describe("pages.discover", () => {
  let registry: StateRegistry;
  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns mounted pages", async () => {
    registry.reportPage(makePage());
    registry.reportPage(makePage({ pageId: "finance:accounts", hub: "finance", mounted: true }));
    const result = await pagesDiscoverExecute({}, registry);
    expect(result.pages).toHaveLength(2);
  });

  it("filters by hub", async () => {
    registry.reportPage(makePage());
    registry.reportPage(makePage({ pageId: "finance:accounts", hub: "finance" }));
    const result = await pagesDiscoverExecute({ hub: "career" }, registry);
    expect(result.pages).toHaveLength(1);
    expect(result.pages[0].id).toBe("career:companies");
  });

  it("filters by mounted", async () => {
    registry.reportPage(makePage());
    registry.reportPage(makePage({ pageId: "finance:accounts", hub: "finance", mounted: false }));
    const result = await pagesDiscoverExecute({ mounted: true }, registry);
    expect(result.pages).toHaveLength(1);
  });
});

describe("pages.read", () => {
  let registry: StateRegistry;
  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("reads a mounted page", async () => {
    registry.reportPage(makePage());
    const result = await pagesReadExecute({ pageId: "career:companies" }, registry);
    expect(result.pageId).toBe("career:companies");
    expect(result.mounted).toBe(true);
  });

  it("returns NOT_FOUND for unknown pageId", async () => {
    const result = await pagesReadExecute({ pageId: "nope:nope" }, registry);
    expect(result.error).toBe(true);
    expect(result.code).toBe("NOT_FOUND");
  });

  it("includes block states when includeBlocks is true", async () => {
    registry.reportPage(makePage({ blocks: ["career:companies"] }));
    registry.reportBlock({
      blockId: "career:companies",
      instanceId: "i1",
      type: "card-grid",
      mounted: true,
      renderState: "ready",
      config: {},
      data: [{ name: "Acme" }],
      lastUpdated: Date.now(),
    });
    const result = await pagesReadExecute(
      { pageId: "career:companies", includeBlocks: true },
      registry,
    );
    expect(result.blocks).toHaveLength(1);
    expect(result.blocks[0].renderState).toBe("ready");
  });
});
