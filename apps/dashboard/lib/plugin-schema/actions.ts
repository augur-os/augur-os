"use server";

/**
 * Server actions for plugin schema data fetching.
 *
 * This file is marked 'use server' to ensure Node.js-only code
 * (like MCPBridge which uses child_process) is not bundled into
 * the client-side code.
 */

import { callMCPTool } from "@/lib/mcp/MCPBridge";
import { MCPBridge } from "@/lib/mcp/MCPBridge";
import { auth } from "@/lib/auth/server-action";

/**
 * Fetch data from an MCP tool via server action.
 *
 * @param toolName - The MCP tool name to call
 * @param params - Parameters to pass to the tool
 * @returns Tool result (typically a JSON string or object)
 */
export async function fetchMCPData(
  toolName: string,
  params: Record<string, unknown>,
): Promise<unknown> {
  await auth();

  const result = await callMCPTool(toolName, params);

  try {
    return MCPBridge.parseJSON(result);
  } catch {
    return MCPBridge.extractText(result);
  }
}
