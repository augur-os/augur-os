/**
 * Universal MCP tool caller for dashboard client code.
 *
 * Replaces all ad-hoc fetch('/api/...') calls with a single function
 * that routes through the universal MCP proxy at /api/mcp/tool.
 */

export interface McpCallOptions {
  /** Return this value instead of throwing on MCP errors */
  fallback?: unknown;
  /** AbortController signal for cancellation */
  signal?: AbortSignal;
}

export async function mcpCall<T = unknown>(
  tool: string,
  args: Record<string, unknown> = {},
  options: McpCallOptions = {},
): Promise<T> {
  const { fallback, signal } = options;

  const res = await fetch("/api/mcp/tool", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool, args }),
    signal,
  });

  if (!res.ok) {
    if (fallback !== undefined) return fallback as T;
    const body = await res.json().catch(() => ({ error: `MCP call failed (${res.status})` }));
    throw new Error(body.error || `MCP tool "${tool}" failed`);
  }

  return res.json() as Promise<T>;
}
