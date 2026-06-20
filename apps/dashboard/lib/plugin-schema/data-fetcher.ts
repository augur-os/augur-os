/**
 * Data source resolver for plugin dashboards.
 *
 * Handles fetching data from various source formats:
 * - mcp://skill/tool - Calls MCP tool directly
 * - /api/path - Calls dashboard API route
 * - static:{"key":"value"} - Returns inline static data
 *
 * NOTE: This file is safe to import from client components.
 * MCP calls are routed through server actions to avoid bundling
 * Node.js-only code (child_process) into the client bundle.
 */

import { fetchMCPData } from "./actions";

/**
 * Fetch data from a source string.
 *
 * @param source - Data source in one of the supported formats
 * @param params - Optional parameters to pass to the source
 * @returns Parsed data from the source
 * @throws Error if source format is unknown or fetch fails
 */
export async function fetchFromSource(
  source: string,
  params?: Record<string, unknown>,
): Promise<unknown> {
  // Bare tool names are treated as MCP sources for compatibility with
  // generated skill configs that emit `source: finance-summary` instead
  // of `source: mcp://finance-summary`.
  if (isBareMcpToolName(source)) {
    return fetchFromMCP(`mcp://${source}`, params);
  }

  // MCP tool source: mcp://skill/tool or mcp://tool
  if (source.startsWith("mcp://")) {
    return fetchFromMCP(source, params);
  }

  // API route source: /api/path
  if (source.startsWith("/api/")) {
    return fetchFromAPI(source, params);
  }

  // Static source: static:{"key":"value"}
  if (source.startsWith("static:")) {
    return parseStaticSource(source);
  }

  throw new Error(`Unknown source format: ${source}`);
}

function isBareMcpToolName(source: string): boolean {
  return (
    source.length > 0 &&
    !source.includes("://") &&
    !source.startsWith("/api/") &&
    !source.startsWith("static:")
  );
}

/**
 * Fetch data from an MCP tool.
 *
 * Format: mcp://skill/tool or mcp://tool-name
 */
async function fetchFromMCP(
  source: string,
  params?: Record<string, unknown>,
): Promise<unknown> {
  const toolPath = source.slice(6); // Remove 'mcp://'

  // Handle both mcp://skill/tool and mcp://tool formats
  let toolName: string;
  if (toolPath.includes("/")) {
    // mcp://skill/tool -> use the tool name after the slash
    toolName = toolPath.split("/").pop() || toolPath;
  } else {
    // mcp://tool-name -> use as-is
    toolName = toolPath;
  }

  try {
    const result = await fetchMCPData(toolName, params || {});

    // MCP tools typically return JSON strings
    if (typeof result === "string") {
      try {
        return JSON.parse(result);
      } catch {
        return result;
      }
    }

    // Server actions or mocks may return the raw MCP content envelope.
    if (
      typeof result === "object" &&
      result !== null &&
      "content" in result &&
      Array.isArray((result as { content: unknown[] }).content)
    ) {
      const text = (result as { content: Array<{ type?: string; text?: string }> }).content
        .flatMap((item) =>
          item?.type === "text" && typeof item.text === "string"
            ? [item.text]
            : [],
        )
        .join("\n");

      if (!text) return result;

      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    }

    return result;
  } catch (error) {
    console.error(`Failed to fetch from MCP tool ${toolName}:`, error);
    throw error;
  }
}

/**
 * Fetch data from a dashboard API route.
 */
async function fetchFromAPI(
  source: string,
  params?: Record<string, unknown>,
): Promise<unknown> {
  const url = new URL(source, window.location.origin);

  // Add params as query string for GET requests
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(
      `API request failed: ${response.status} ${response.statusText}`,
    );
  }

  return response.json();
}

/**
 * Parse a static source string.
 *
 * Format: static:{"key":"value"}
 */
function parseStaticSource(source: string): unknown {
  const jsonStr = source.slice(7); // Remove 'static:'
  try {
    return JSON.parse(jsonStr);
  } catch (error) {
    throw new Error(`Invalid static source JSON: ${jsonStr}`);
  }
}

/**
 * Apply a transform expression to data using safe property traversal.
 *
 * Transform expressions are dot-separated property paths prefixed with "data.".
 * No code evaluation — only property access is supported.
 *
 * Examples:
 * - "data.length" -> returns array length
 * - "data.total" -> returns total property
 * - "data.documents.length" -> returns nested property
 *
 * @param transform - Dot-path expression string (e.g. "data.items.length")
 * @param data - Data to transform
 * @returns Transformed value
 */
function applyTransform(transform: string, data: unknown): unknown {
  // Handle null/undefined data gracefully
  if (data === null || data === undefined) {
    console.warn(
      `Transform "${transform}" received null/undefined data, returning 0`,
    );
    return 0;
  }

  try {
    // Validate transform is a safe dot-path starting with "data."
    if (!/^data(\.[a-zA-Z_$][a-zA-Z0-9_$]*)*$/.test(transform)) {
      console.error(`Unsafe transform rejected: ${transform}`);
      return 0;
    }

    // Traverse the property path safely (skip the leading "data" segment)
    const parts = transform.split(".").slice(1);
    let current: unknown = data;
    for (const part of parts) {
      if (current === null || current === undefined) return 0;
      current = (current as Record<string, unknown>)[part];
    }
    return current ?? 0;
  } catch (error) {
    console.error(`Transform failed: ${transform}`, error);
    return 0;
  }
}

/**
 * Fetch and optionally transform data from a source.
 *
 * Convenience function that combines fetchFromSource and applyTransform.
 *
 * @param source - Data source string
 * @param params - Optional parameters
 * @param transform - Optional transform expression
 * @returns Fetched and transformed data
 */
async function fetchData(
  source: string,
  params?: Record<string, unknown>,
  transform?: string,
): Promise<unknown> {
  const data = await fetchFromSource(source, params);

  if (transform) {
    return applyTransform(transform, data);
  }

  return data;
}

/**
 * Batch fetch multiple sources in parallel.
 *
 * @param sources - Array of source configs
 * @returns Object mapping source IDs to their data
 */
async function fetchMultiple(
  sources: Array<{
    id: string;
    source: string;
    params?: Record<string, unknown>;
    transform?: string;
  }>,
): Promise<Record<string, unknown>> {
  const results = await Promise.allSettled(
    sources.map(async (s) => ({
      id: s.id,
      data: await fetchData(s.source, s.params, s.transform),
    })),
  );

  const output: Record<string, unknown> = {};

  for (const result of results) {
    if (result.status === "fulfilled") {
      output[result.value.id] = result.value.data;
    } else {
      // Include error info for failed fetches
      console.error("Fetch failed:", result.reason);
    }
  }

  return output;
}
