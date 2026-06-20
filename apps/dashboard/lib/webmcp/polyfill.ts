import type { ModelContextTool, ModelContext } from "./types";

/**
 * Polyfill for navigator.modelContext (W3C WebMCP API).
 * When Chrome 146+ has the "WebMCP for testing" flag enabled,
 * navigator.modelContext exists natively and this is a no-op.
 */

declare global {
  interface Navigator {
    modelContext?: ModelContext;
  }
  interface Window {
    __webmcp?: ModelContext;
  }
}

if (typeof navigator !== "undefined" && !navigator.modelContext) {
  const toolMap = new Map<string, ModelContextTool>();

  const noopClient = {
    requestUserInteraction: async (cb: () => Promise<unknown>) => cb(),
  };

  const polyfill: ModelContext = {
    registerTool(tool: ModelContextTool) {
      if (!tool.name || !tool.description) {
        throw new DOMException("Tool name and description required", "InvalidStateError");
      }
      if (toolMap.has(tool.name)) {
        throw new DOMException(`Tool "${tool.name}" already registered`, "InvalidStateError");
      }
      toolMap.set(tool.name, tool);
    },

    unregisterTool(name: string) {
      if (!toolMap.has(name)) {
        throw new DOMException(`Tool "${name}" not registered`, "InvalidStateError");
      }
      toolMap.delete(name);
    },

    async executeTool(name: string, input: unknown) {
      const tool = toolMap.get(name);
      if (!tool) {
        throw new DOMException(`Tool "${name}" not registered`, "InvalidStateError");
      }
      return await tool.execute(input, noopClient);
    },

    listTools() {
      return Array.from(toolMap.values()).map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: t.inputSchema,
        annotations: t.annotations,
      }));
    },

    __polyfill: true,
  };

  navigator.modelContext = polyfill;
}

// Always expose for extensions (Claude-in-Chrome, etc.)
if (typeof window !== "undefined" && navigator.modelContext) {
  window.__webmcp = navigator.modelContext;
}
