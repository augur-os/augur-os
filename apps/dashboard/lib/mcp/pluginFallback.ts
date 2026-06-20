/**
 * Plugin fallback utilities
 *
 * Extracted from the proxy handler so that pages calling plugin tools
 * directly via mcpCall can detect "plugin not installed" errors and
 * show appropriate UI.
 */

/** Shape of a fallback response injected when a plugin tool is unavailable. */
export interface FallbackResponse {
  _fallback: true;
  _reason: string;
  _plugin: string | null;
  _error?: string;
}

/**
 * Maps MCP tool names to the plugin that provides them.
 * Extracted from the catch-all proxy handler.
 */
const PLUGIN_TOOL_SOURCES: Record<string, string> = {
  "get-attention-items": "attention",
  "get-attention-summary": "attention",
  "get-agent-telemetry": "advisor",
  "get-agent-weights": "advisor",
  "update-agent-weights": "advisor",
  "verify-changes": "advisor",
  "get-daemon-status": "daemon",
  "insights-pending": "daemon",
  "plugin-events-list": "daemon",
  "plugin-events-acknowledge": "daemon",
  "scan-file-organizer": "file-manager",
  "get-context-files": "file-manager",
  "manage-cli-agents": "ai",
  "manage-tools-catalog": "ai",
  "run-adaptive-growth": "platform-admin",
  "generate-ide-instructions": "ai",
  "validate-agent-wizard": "ai",
  "unified-search": "knowledge",
  "knowledge-project-index-rebuild": "knowledge",
  "knowledge-summarize-url": "knowledge",
  "knowledge-summarize-file": "knowledge",
  "start-rag-indexing": "knowledge",
  "search-skill-knowledge": "rag",
};

/**
 * Returns the plugin name that provides the given tool,
 * or null if the tool is a core tool (not plugin-provided).
 */
export function pluginForTool(toolName: string): string | null {
  return PLUGIN_TOOL_SOURCES[toolName] ?? null;
}

/**
 * Returns true if the tool belongs to an optional plugin.
 */
export function isPluginTool(toolName: string): boolean {
  return toolName in PLUGIN_TOOL_SOURCES;
}

/**
 * Type guard: returns true if the data looks like a FallbackResponse.
 */
export function isFallbackResponse(
  data: unknown,
): data is FallbackResponse {
  return (
    typeof data === "object" &&
    data !== null &&
    "_fallback" in data &&
    (data as Record<string, unknown>)._fallback === true
  );
}
