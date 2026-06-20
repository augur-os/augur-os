import {
  pluginForTool,
  isPluginTool,
  isFallbackResponse,
} from "@/lib/mcp/pluginFallback";

describe("pluginFallback", () => {
  describe("pluginForTool", () => {
    it("returns the plugin name for a known plugin tool", () => {
      expect(pluginForTool("get-attention-items")).toBe("attention");
      expect(pluginForTool("get-agent-telemetry")).toBe("advisor");
      expect(pluginForTool("get-daemon-status")).toBe("daemon");
      expect(pluginForTool("unified-search")).toBe("knowledge");
      expect(pluginForTool("search-skill-knowledge")).toBe("rag");
    });

    it("returns null for unknown / core tools", () => {
      expect(pluginForTool("list-skills")).toBeNull();
      expect(pluginForTool("get-config")).toBeNull();
      expect(pluginForTool("check-system-permissions")).toBeNull();
      expect(pluginForTool("")).toBeNull();
      expect(pluginForTool("nonexistent-tool")).toBeNull();
    });

    it("covers all 21 mapped entries", () => {
      const knownTools = [
        "get-attention-items",
        "get-attention-summary",
        "get-agent-telemetry",
        "get-agent-weights",
        "update-agent-weights",
        "verify-changes",
        "get-daemon-status",
        "insights-pending",
        "plugin-events-list",
        "plugin-events-acknowledge",
        "scan-file-organizer",
        "get-context-files",
        "manage-cli-agents",
        "manage-tools-catalog",
        "run-adaptive-growth",
        "generate-ide-instructions",
        "validate-agent-wizard",
        "unified-search",
        "knowledge-project-index-rebuild",
        "knowledge-summarize-url",
        "knowledge-summarize-file",
        "start-rag-indexing",
        "search-skill-knowledge",
      ];
      for (const tool of knownTools) {
        expect(pluginForTool(tool)).not.toBeNull();
      }
    });
  });

  describe("isPluginTool", () => {
    it("returns true for plugin tools", () => {
      expect(isPluginTool("get-attention-items")).toBe(true);
      expect(isPluginTool("get-daemon-status")).toBe(true);
      expect(isPluginTool("unified-search")).toBe(true);
    });

    it("returns false for core tools", () => {
      expect(isPluginTool("list-skills")).toBe(false);
      expect(isPluginTool("get-config")).toBe(false);
      expect(isPluginTool("")).toBe(false);
    });
  });

  describe("isFallbackResponse", () => {
    it("returns true for a valid fallback response", () => {
      const data = {
        _fallback: true,
        _reason: "plugin not installed",
        _plugin: "attention",
      };
      expect(isFallbackResponse(data)).toBe(true);
    });

    it("returns true when _error is present", () => {
      const data = {
        _fallback: true,
        _reason: "plugin not installed",
        _plugin: "attention",
        _error: "Connection refused",
      };
      expect(isFallbackResponse(data)).toBe(true);
    });

    it("returns true when _plugin is null", () => {
      const data = {
        _fallback: true,
        _reason: "unknown error",
        _plugin: null,
      };
      expect(isFallbackResponse(data)).toBe(true);
    });

    it("returns false when _fallback is not true", () => {
      expect(isFallbackResponse({ _fallback: false, _reason: "x", _plugin: null })).toBe(false);
      expect(isFallbackResponse({ _fallback: "true", _reason: "x", _plugin: null })).toBe(false);
    });

    it("returns false for non-object values", () => {
      expect(isFallbackResponse(null)).toBe(false);
      expect(isFallbackResponse(undefined)).toBe(false);
      expect(isFallbackResponse("string")).toBe(false);
      expect(isFallbackResponse(42)).toBe(false);
      expect(isFallbackResponse(true)).toBe(false);
    });

    it("returns false for objects without _fallback", () => {
      expect(isFallbackResponse({})).toBe(false);
      expect(isFallbackResponse({ data: [] })).toBe(false);
    });
  });
});
