// apps/dashboard/lib/webmcp/tools/errors.ts
import type { WebMCPError, WebMCPErrorCode } from "../types";

export function mcpError(
  code: WebMCPErrorCode,
  message: string,
  blockId?: string,
  details?: Record<string, unknown>,
): WebMCPError {
  return { error: true, code, message, ...(blockId && { blockId }), ...(details && { details }) };
}

export function notFound(blockId: string): WebMCPError {
  return mcpError("NOT_FOUND", `Block "${blockId}" not found in registry`, blockId);
}

export function unmounted(blockId: string): WebMCPError {
  return mcpError("UNMOUNTED", `Block "${blockId}" is not mounted`, blockId);
}

function invalidConfig(blockId: string, details: Record<string, unknown>): WebMCPError {
  return mcpError("INVALID_CONFIG", `Invalid config for block "${blockId}"`, blockId, details);
}

export function invalidAction(blockId: string, action: string, validActions: string[]): WebMCPError {
  return mcpError(
    "INVALID_ACTION",
    `Unknown action "${action}" for block "${blockId}"`,
    blockId,
    { validActions },
  );
}

export function fetchFailed(blockId: string, upstream: string): WebMCPError {
  return mcpError("FETCH_FAILED", `Data fetch failed for "${blockId}": ${upstream}`, blockId);
}
