/**
 * @jest-environment jsdom
 */
import { describe, it, expect, beforeEach } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";

describe("WebMCP integration", () => {
  beforeEach(() => {
    delete (navigator as any).modelContext;
    delete (window as any).__webmcp;
    delete (window as any).__webmcpRegistry;
    jest.resetModules();
  });

  it("polyfill + registry + tools wire up correctly", async () => {
    // 1. Load polyfill
    await import("@/lib/webmcp/polyfill");
    expect(navigator.modelContext).toBeDefined();

    // 2. Create registry and register tools
    const { registerBlockTools } = await import("@/lib/webmcp/tools/blocks");
    const registry = new StateRegistry();
    registerBlockTools(navigator.modelContext!, registry);

    // 3. List tools via polyfill
    const tools = navigator.modelContext!.listTools!();
    expect(tools.map((t: any) => t.name).sort()).toEqual([
      "blocks.act",
      "blocks.configure",
      "blocks.discover",
      "blocks.read",
    ]);

    // 4. Execute blocks.discover via polyfill
    const result = await navigator.modelContext!.executeTool!("blocks.discover", {});
    expect(result.blocks).toBeDefined();
    expect(Array.isArray(result.blocks)).toBe(true);
  });

  it("state registry is accessible via window.__webmcpRegistry", () => {
    const registry = new StateRegistry();
    (window as any).__webmcpRegistry = registry;

    registry.reportBlock({
      blockId: "test:block",
      instanceId: "i1",
      type: "stat-card",
      mounted: true,
      renderState: "ready",
      config: {},
      data: { value: 42 },
      lastUpdated: Date.now(),
    });

    expect(registry.getBlock("test:block")?.data).toEqual({ value: 42 });
  });
});
