/**
 * @jest-environment jsdom
 */
import { describe, it, expect, beforeEach, jest } from "@jest/globals";

// Clear navigator.modelContext and reset module cache before each test
// so the polyfill side-effect re-executes on each dynamic import.
beforeEach(() => {
  jest.resetModules();
  delete (navigator as any).modelContext;
  delete (window as any).__webmcp;
});

describe("WebMCP polyfill", () => {
  it("installs navigator.modelContext when missing", async () => {
    await import("@/lib/webmcp/polyfill");
    expect(navigator.modelContext).toBeDefined();
    expect(navigator.modelContext.__polyfill).toBe(true);
  });

  it("exposes window.__webmcp", async () => {
    await import("@/lib/webmcp/polyfill");
    expect((window as any).__webmcp).toBe(navigator.modelContext);
  });

  it("registers and lists tools", async () => {
    await import("@/lib/webmcp/polyfill");
    const mc = navigator.modelContext!;
    mc.registerTool({
      name: "test.tool",
      description: "A test tool",
      inputSchema: { type: "object" },
      execute: async () => ({ result: "ok" }),
    });
    const tools = mc.listTools!();
    expect(tools).toHaveLength(1);
    expect(tools[0].name).toBe("test.tool");
  });

  it("executes a registered tool", async () => {
    await import("@/lib/webmcp/polyfill");
    const mc = navigator.modelContext!;
    mc.registerTool({
      name: "echo",
      description: "Echoes input",
      execute: async (input: any) => ({ echo: input.msg }),
    });
    const result = await mc.executeTool!("echo", { msg: "hello" });
    expect(result).toEqual({ echo: "hello" });
  });

  it("throws InvalidStateError on duplicate register", async () => {
    await import("@/lib/webmcp/polyfill");
    const mc = navigator.modelContext!;
    const tool = { name: "dup", description: "dup", execute: async () => null };
    mc.registerTool(tool);
    expect(() => mc.registerTool(tool)).toThrow();
  });

  it("unregisters a tool", async () => {
    await import("@/lib/webmcp/polyfill");
    const mc = navigator.modelContext!;
    mc.registerTool({ name: "rm", description: "rm", execute: async () => null });
    mc.unregisterTool("rm");
    expect(mc.listTools!()).toHaveLength(0);
  });

  it("throws on unregister of unknown tool", async () => {
    await import("@/lib/webmcp/polyfill");
    expect(() => navigator.modelContext!.unregisterTool("nope")).toThrow();
  });

  it("throws on executeTool of unknown tool", async () => {
    await import("@/lib/webmcp/polyfill");
    await expect(navigator.modelContext!.executeTool!("nope", {})).rejects.toThrow();
  });
});
