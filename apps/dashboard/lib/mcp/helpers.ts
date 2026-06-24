/**
 * MCP Bridge Helpers
 *
 * Convenience functions for common MCP Bridge operations:
 * - getMCPBridge(): Get the singleton MCPBridge instance
 * - callMCPTool(): Call an MCP tool with automatic connection & retry
 * - extractContextFromRequest(): Extract context from Next.js requests
 */

import type { MCPToolResult, MCPServerContext } from "./types";
import { MCPBridge } from "./connection";

/**
 * Helper function to get MCP bridge singleton
 */
export function getMCPBridge(): MCPBridge {
  return MCPBridge.getInstance();
}

/**
 * Helper function to call MCP tool with automatic connection
 */
export async function callMCPTool(
  toolName: string,
  args: Record<string, unknown> = {},
  context?: MCPServerContext,
): Promise<MCPToolResult> {
  const bridge = getMCPBridge();
  const shouldRetryWithParamsWrapper = (message: string): boolean => {
    if ("params" in args) {
      return false;
    }

    return (
      message.includes("validation error") &&
      message.includes("params") &&
      message.includes("Field required")
    );
  };

  try {
    const result = await bridge.callTool(toolName, args, context);

    // Retry with params wrapper if the tool returned an isError result
    // (not thrown — MCP SDK returns error results, doesn't throw)
    if (result.isError) {
      const errContent = result.content?.[0];
      const errText = typeof errContent === "string"
        ? errContent
        : (errContent as Record<string, unknown>)?.text as string || "";
      if (shouldRetryWithParamsWrapper(errText)) {
        return bridge.callTool(toolName, { params: args }, context);
      }
    }

    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);

    if (shouldRetryWithParamsWrapper(message)) {
      return bridge.callTool(toolName, { params: args }, context);
    }

    const shouldReconnect =
      message.includes("MCP server failed") ||
      message.includes("MCP server disconnected") ||
      message.includes("MCP server not connected") ||
      message.includes("lock contention");

    if (!shouldReconnect) {
      throw error;
    }

    await bridge.reconnect();
    return bridge.callTool(toolName, args, context);
  }
}

/**
 * Call an augur_core MCP tool with automatic connection and retry.
 *
 * Mirrors callMCPTool exactly — same connect+call mechanism, same params-wrapper
 * retry, same reconnect retry — the only difference is the target bridge instance.
 */
export async function callCoreTool(
  toolName: string,
  args: Record<string, unknown> = {},
  context?: MCPServerContext,
): Promise<MCPToolResult> {
  const bridge = MCPBridge.getInstance("augur_core");
  const shouldRetryWithParamsWrapper = (message: string): boolean => {
    if ("params" in args) {
      return false;
    }

    return (
      message.includes("validation error") &&
      message.includes("params") &&
      message.includes("Field required")
    );
  };

  try {
    const result = await bridge.callTool(toolName, args, context);

    // Retry with params wrapper if the tool returned an isError result
    // (not thrown — MCP SDK returns error results, doesn't throw)
    if (result.isError) {
      const errContent = result.content?.[0];
      const errText = typeof errContent === "string"
        ? errContent
        : (errContent as Record<string, unknown>)?.text as string || "";
      if (shouldRetryWithParamsWrapper(errText)) {
        return bridge.callTool(toolName, { params: args }, context);
      }
    }

    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);

    if (shouldRetryWithParamsWrapper(message)) {
      return bridge.callTool(toolName, { params: args }, context);
    }

    const shouldReconnect =
      message.includes("MCP server failed") ||
      message.includes("MCP server disconnected") ||
      message.includes("MCP server not connected") ||
      message.includes("lock contention");

    if (!shouldReconnect) {
      throw error;
    }

    await bridge.reconnect();
    return bridge.callTool(toolName, args, context);
  }
}

/**
 * Helper to extract context from Next.js request
 */
export function extractContextFromRequest(req: Request): MCPServerContext {
  const url = new URL(req.url);
  const referer = req.headers.get("referer") || "";

  // Extract current page from referer
  let currentPage = "";
  if (referer) {
    const refererUrl = new URL(referer);
    currentPage = refererUrl.pathname;
  }

  // Extract sprint from query params or headers
  const activeSprint = url.searchParams.get("sprint") || undefined;

  // Detect if executing chain from URL
  const executingChain =
    url.pathname.includes("/chain") || url.searchParams.has("chain");

  return {
    active_sprint: activeSprint,
    current_page: currentPage,
    executing_chain: executingChain,
  };
}
