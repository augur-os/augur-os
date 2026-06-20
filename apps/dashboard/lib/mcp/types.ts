/**
 * MCP Bridge Types
 *
 * Shared type definitions for MCP Bridge communication.
 */

export interface MCPToolCall {
  name: string;
  arguments: Record<string, unknown>;
}

export interface MCPToolResult {
  content: Array<{
    type: string;
    text: string;
  }>;
  isError?: boolean;
}

export interface MCPServerContext {
  active_sprint?: string;
  current_page?: string;
  executing_chain?: boolean;
  workflow_phase?: string;
}

export interface PendingRequest {
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
  timeout: NodeJS.Timeout;
}

export interface ContextSwitchResult {
  success?: boolean;
  error?: string;
  active_count?: number;
  removed?: unknown[];
  added?: unknown[];
}

// Re-exported from pluginFallback — single source of truth
export { isFallbackResponse } from "./pluginFallback";
export type { FallbackResponse } from "./pluginFallback";
