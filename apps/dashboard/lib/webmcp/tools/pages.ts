import type { ModelContext } from "../types";
import type {
  PagesDiscoverInput,
  PagesDiscoverOutput,
  PagesReadInput,
  PagesReadOutput,
  WebMCPError,
} from "../types";
import type { StateRegistry } from "../state-registry";
import { mcpError } from "./errors";

export async function pagesDiscoverExecute(
  input: PagesDiscoverInput,
  registry: StateRegistry,
): Promise<PagesDiscoverOutput> {
  let pages = registry.getAllPages().map((p) => ({
    id: p.pageId,
    hub: p.hub,
    title: p.pageId.split(":")[1] || p.pageId,
    path: p.path,
    mounted: p.mounted,
    blocks: p.blocks,
  }));

  if (input.hub) pages = pages.filter((p) => p.hub === input.hub);
  if (input.mounted) pages = pages.filter((p) => p.mounted);

  return { pages };
}

export async function pagesReadExecute(
  input: PagesReadInput,
  registry: StateRegistry,
): Promise<PagesReadOutput | WebMCPError> {
  const page = registry.getPage(input.pageId);
  if (!page) {
    return mcpError("NOT_FOUND", `Page "${input.pageId}" not found`, input.pageId);
  }

  const result: PagesReadOutput = {
    pageId: page.pageId,
    mounted: page.mounted,
    path: page.path,
  };

  if (input.includeBlocks && page.blocks.length > 0) {
    result.blocks = page.blocks.map((blockId) => {
      const blockState = registry.getBlock(blockId);
      return {
        blockId,
        renderState: blockState?.renderState ?? "empty",
        ...(blockState?.data !== undefined && { data: blockState.data }),
      };
    });
  }

  return result;
}

export function registerPageTools(mc: ModelContext, registry: StateRegistry): void {
  mc.registerTool({
    name: "pages.discover",
    description:
      "List auto-pages. Filter by hub or mounted status. Returns page manifests with block composition.",
    inputSchema: {
      type: "object",
      properties: {
        hub: { type: "string", description: "Filter by hub" },
        mounted: { type: "boolean", description: "Only mounted pages" },
      },
    },
    execute: async (input) => pagesDiscoverExecute(input as PagesDiscoverInput, registry),
    annotations: { readOnlyHint: true },
  });

  mc.registerTool({
    name: "pages.read",
    description:
      "Read page state with optional batch block read. Returns page metadata and optionally all block states.",
    inputSchema: {
      type: "object",
      properties: {
        pageId: { type: "string", description: "Page ID (e.g., 'career:companies')" },
        includeBlocks: { type: "boolean", description: "Include block states" },
      },
      required: ["pageId"],
    },
    execute: async (input) => pagesReadExecute(input as PagesReadInput, registry),
    annotations: { readOnlyHint: true },
  });
}
