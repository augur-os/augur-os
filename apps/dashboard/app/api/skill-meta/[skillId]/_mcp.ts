/**
 * MCP file helpers for the Skill Meta API route.
 *
 * Extracted from route.ts (WS5 decomposition). All file operations go through
 * MCP tools (file-read, file-list). No direct fs imports.
 */

import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

/** Read a file via MCP file-read tool. Returns content string or null on failure. */
export async function mcpReadFile(
  filePath: string,
  repo: "code" | "data" | "runtime" | "auto" = "auto",
): Promise<string | null> {
  try {
    const result = await callMCPTool("file-read", { path: filePath, repo });
    if (result.isError) return null;
    const data = MCPBridge.parseJSON(result) as Record<string, any>;
    if (data.status === "error") return null;
    return data.content ?? null;
  } catch {
    return null;
  }
}

/** List a directory via MCP file-list tool. Returns entries or empty array. */
export async function mcpListDir(
  dirPath: string,
  opts: {
    repo?: "code" | "data" | "runtime" | "auto";
    pattern?: string;
    recursive?: boolean;
    limit?: number;
  } = {},
): Promise<Array<Record<string, any>>> {
  try {
    const result = await callMCPTool("file-list", {
      path: dirPath,
      repo: opts.repo ?? "auto",
      pattern: opts.pattern ?? "*",
      recursive: opts.recursive ?? false,
      limit: opts.limit ?? 500,
    });
    if (result.isError) return [];
    const data = MCPBridge.parseJSON(result) as Record<string, any>;
    if (data.status === "error") return [];
    return data.entries ?? [];
  } catch {
    return [];
  }
}
