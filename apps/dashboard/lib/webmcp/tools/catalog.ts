import { BLOCK_REGISTRY } from "@/lib/blocks/generated-block-registry";
import type { ModelContext } from "../types";
import type {
  CatalogSearchInput,
  CatalogSearchOutput,
  CatalogSearchResult,
  CatalogPreviewInput,
  CatalogPreviewOutput,
  WebMCPError,
} from "../types";
import type { StateRegistry } from "../state-registry";
import { notFound, fetchFailed } from "./errors";

// --- Relevance scoring ---

function scoreMatch(text: string, query: string): number {
  const t = text.toLowerCase();
  const q = query.toLowerCase();
  if (t === q) return 3; // exact match
  if (t.startsWith(q)) return 2; // starts with
  if (t.includes(q)) return 1; // contains
  return 0;
}

function bestScore(fields: string[], query: string): number {
  return Math.max(...fields.map((f) => scoreMatch(f, query)));
}

// --- Exported execute functions (testable without navigator.modelContext) ---

export async function catalogSearchExecute(
  input: CatalogSearchInput,
  registry: StateRegistry,
): Promise<CatalogSearchOutput | WebMCPError> {
  const { query, types } = input;
  const results: Array<CatalogSearchResult & { _score: number }> = [];

  const includeBlocks = !types || types.includes("block");
  const includePages = !types || types.includes("page");

  // --- Blocks ---
  if (includeBlocks) {
    for (const manifest of Object.values(BLOCK_REGISTRY)) {
      const score = bestScore([manifest.id, manifest.title], query);
      if (score > 0) {
        results.push({
          type: "block",
          id: manifest.id,
          title: manifest.title,
          hub: manifest.hub,
          description: undefined,
          _score: score,
        });
      }
    }
  }

  // --- Pages ---
  if (includePages) {
    for (const page of registry.getAllPages()) {
      const title = page.pageId.split(":")[1] || page.pageId;
      const score = bestScore([page.pageId, title, page.hub], query);
      if (score > 0) {
        results.push({
          type: "page",
          id: page.pageId,
          title,
          hub: page.hub,
          description: undefined,
          _score: score,
        });
      }
    }
  }

  // Sort by descending relevance score, then by type priority
  const TYPE_PRIORITY: Record<string, number> = { block: 0, page: 1, action: 2 };
  results.sort((a, b) => {
    if (b._score !== a._score) return b._score - a._score;
    return (TYPE_PRIORITY[a.type] ?? 9) - (TYPE_PRIORITY[b.type] ?? 9);
  });

  // Strip internal score field
  const cleaned: CatalogSearchResult[] = results.map(({ _score: _s, ...r }) => r);

  return { results: cleaned, total: cleaned.length };
}

export async function catalogPreviewExecute(
  input: CatalogPreviewInput,
): Promise<CatalogPreviewOutput | WebMCPError> {
  const manifest = BLOCK_REGISTRY[input.blockId];
  if (!manifest) return notFound(input.blockId);

  try {
    const response = await fetch("/api/blocks/data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool: manifest.dataSource?.mcpTool,
        args: input.config ?? {},
      }),
    });
    if (!response.ok) {
      return fetchFailed(input.blockId, `${response.status} ${response.statusText}`);
    }
    const json = await response.json();
    const data = json.data ?? json;

    return {
      blockId: input.blockId,
      type: manifest.type,
      title: manifest.title,
      data,
    };
  } catch (err) {
    return fetchFailed(input.blockId, err instanceof Error ? err.message : String(err));
  }
}

// --- Tool registration ---

export function registerCatalogTools(mc: ModelContext, registry: StateRegistry): void {
  mc.registerTool({
    name: "catalog.search",
    description:
      "Search across blocks, pages, and actions by keyword. Returns unified results sorted by relevance (exact match > starts with > contains). Filter by type to narrow scope.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search term" },
        types: {
          type: "array",
          items: { type: "string", enum: ["block", "page", "action"] },
          description: "Limit search to specific entity types (default: all)",
        },
      },
      required: ["query"],
    },
    execute: async (input) => catalogSearchExecute(input as CatalogSearchInput, registry),
    annotations: { readOnlyHint: true },
  });

  mc.registerTool({
    name: "catalog.preview",
    description:
      "Preview a block's data without mounting it. Looks up the block manifest and fetches live data via the block's MCP data source. Useful for inspecting block output before placing it on a view.",
    inputSchema: {
      type: "object",
      properties: {
        blockId: { type: "string", description: "Block ID to preview (e.g., 'career:pipeline')" },
        config: {
          type: "object",
          description: "Optional config arguments forwarded to the data source",
        },
      },
      required: ["blockId"],
    },
    execute: async (input) => catalogPreviewExecute(input as CatalogPreviewInput),
    annotations: { readOnlyHint: true },
  });
}
