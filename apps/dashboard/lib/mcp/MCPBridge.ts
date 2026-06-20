/**
 * MCP Bridge for TypeScript UI Server
 *
 * Provides stdio-based communication with the MCP server.
 * Replaces subprocess spawning (execFile, spawn, inline Python) with MCP protocol.
 *
 * Architecture:
 * - Single persistent MCP server process per session
 * - JSON-RPC 2.0 over stdio
 * - Request/response pattern with correlation IDs
 * - Automatic reconnection on failure
 *
 * This file is a backward-compatible barrel that re-exports all public API
 * from focused sub-modules:
 *   - types.ts: MCPToolCall, MCPToolResult, MCPServerContext
 *   - preflight.ts: PreflightContract, resolveMcpClientId, resolvePreflightContract
 *   - connection.ts: MCPBridge class
 *   - helpers.ts: getMCPBridge, callMCPTool, extractContextFromRequest
 */

// Types
export type {
  MCPToolCall,
  MCPToolResult,
  MCPServerContext,
} from "./types";

// Connection (MCPBridge class)
export { MCPBridge } from "./connection";

// Helpers
export {
  getMCPBridge,
  callMCPTool,
  extractContextFromRequest,
} from "./helpers";
