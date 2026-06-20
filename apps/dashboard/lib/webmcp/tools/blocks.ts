import { BLOCK_REGISTRY } from "@/lib/blocks/generated-block-registry";
import type { ModelContext } from "../types";
import type {
  BlocksDiscoverInput,
  BlocksDiscoverOutput,
  BlocksReadInput,
  BlocksReadOutput,
  BlocksConfigureInput,
  BlocksConfigureOutput,
  BlocksActInput,
  BlocksActOutput,
  WebMCPError,
} from "../types";
import type { StateRegistry } from "../state-registry";
import { notFound, unmounted, invalidAction, fetchFailed } from "./errors";

const STANDARD_ACTIONS = ["refresh", "expand"];

function buildRenderInfo(data: unknown): { rowCount?: number; visibleColumns?: string[] } {
  if (!Array.isArray(data)) return {};
  const rowCount = data.length;
  if (rowCount > 0 && typeof data[0] === "object" && data[0] !== null) {
    const visibleColumns = Object.keys(data[0]).filter((k) => k !== "id").slice(0, 6);
    return { rowCount, visibleColumns };
  }
  return { rowCount };
}

// --- Exported execute functions (testable without navigator.modelContext) ---

export async function blocksDiscoverExecute(
  input: BlocksDiscoverInput,
  registry: StateRegistry,
): Promise<BlocksDiscoverOutput> {
  let blocks = Object.values(BLOCK_REGISTRY).map((manifest) => {
    const state = registry.getBlock(manifest.id);
    return {
      id: manifest.id,
      type: manifest.type,
      title: manifest.title,
      hub: manifest.hub,
      configSchema: manifest.configSchema,
      mounted: state?.mounted ?? false,
      actions: [...STANDARD_ACTIONS],
    };
  });

  if (input.hub) blocks = blocks.filter((b) => b.hub === input.hub);
  if (input.type) blocks = blocks.filter((b) => b.type === input.type);
  if (input.mounted) blocks = blocks.filter((b) => b.mounted);
  if (input.search) {
    const q = input.search.toLowerCase();
    blocks = blocks.filter(
      (b) => b.id.toLowerCase().includes(q) || b.title.toLowerCase().includes(q),
    );
  }

  return { blocks };
}

export async function blocksReadExecute(
  input: BlocksReadInput,
  registry: StateRegistry,
): Promise<BlocksReadOutput | WebMCPError> {
  const manifest = BLOCK_REGISTRY[input.blockId];
  if (!manifest) return notFound(input.blockId);

  const state = registry.getBlock(input.blockId);

  if (!state && !input.config) return unmounted(input.blockId);

  if (state) {
    const result: BlocksReadOutput = {
      blockId: state.blockId,
      mounted: state.mounted,
      renderState: state.renderState,
      config: state.config,
      data: state.data,
      lastUpdated: state.lastUpdated,
      error: state.error,
    };
    if (input.includeState) {
      result.renderInfo = buildRenderInfo(state.data);
    }
    return result;
  }

  // Unmounted but config override provided — fetch directly
  try {
    const response = await fetch("/api/blocks/data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tool: manifest.dataSource?.mcpTool,
        args: input.config || {},
      }),
    });
    if (!response.ok) {
      return fetchFailed(input.blockId, `${response.status} ${response.statusText}`);
    }
    const json = await response.json();
    const data = json.data ?? json;

    return {
      blockId: input.blockId,
      mounted: false,
      renderState: "ready",
      config: input.config || {},
      data,
      lastUpdated: Date.now(),
      ...(input.includeState && { renderInfo: buildRenderInfo(data) }),
    };
  } catch (err) {
    return fetchFailed(input.blockId, err instanceof Error ? err.message : String(err));
  }
}

export async function blocksConfigureExecute(
  input: BlocksConfigureInput,
  registry: StateRegistry,
): Promise<BlocksConfigureOutput | WebMCPError> {
  const manifest = BLOCK_REGISTRY[input.blockId];
  if (!manifest) return notFound(input.blockId);

  const state = registry.getBlock(input.blockId);
  if (!state) return unmounted(input.blockId);

  const previousConfig = { ...state.config };
  const newConfig = { ...state.config, ...input.config };

  registry.reportBlock({ ...state, config: newConfig, renderState: "loading" });
  registry.setConfig(input.blockId, newConfig);

  const waitForSettle = input.waitForSettle !== false;
  if (waitForSettle) {
    try {
      const settled = await registry.waitForSettle(input.blockId, 10_000);
      return {
        success: true,
        blockId: input.blockId,
        previousConfig,
        newConfig,
        renderState: settled.renderState,
        settled: true,
      };
    } catch {
      const current = registry.getBlock(input.blockId);
      return {
        success: true,
        blockId: input.blockId,
        previousConfig,
        newConfig,
        renderState: current?.renderState ?? "loading",
        settled: false,
      };
    }
  }

  return {
    success: true,
    blockId: input.blockId,
    previousConfig,
    newConfig,
    renderState: "loading",
    settled: false,
  };
}

export async function blocksActExecute(
  input: BlocksActInput,
  registry: StateRegistry,
): Promise<BlocksActOutput | WebMCPError> {
  const manifest = BLOCK_REGISTRY[input.blockId];
  if (!manifest) return notFound(input.blockId);

  const state = registry.getBlock(input.blockId);
  if (!state) return unmounted(input.blockId);

  const validActions = [...STANDARD_ACTIONS];
  if (!validActions.includes(input.action)) {
    return invalidAction(input.blockId, input.action, validActions);
  }

  if (input.action === "refresh") {
    registry.reportBlock({ ...state, renderState: "loading" });
    registry.triggerRefresh(input.blockId);
    return { success: true, action: "refresh", blockId: input.blockId };
  }

  if (input.action === "expand") {
    return {
      success: true,
      action: "expand",
      blockId: input.blockId,
      result: { expandTo: manifest.expandTo },
    };
  }

  return { success: true, action: input.action, blockId: input.blockId };
}

// --- Tool registration ---

export function registerBlockTools(mc: ModelContext, registry: StateRegistry): void {
  mc.registerTool({
    name: "blocks.discover",
    description:
      "List available dashboard blocks. Filter by hub, type, search term, or mounted status. Returns block manifests with config schemas and available actions.",
    inputSchema: {
      type: "object",
      properties: {
        hub: { type: "string", description: "Filter by hub (e.g., 'career', 'finance')" },
        type: { type: "string", description: "Filter by block type (e.g., 'data-table')" },
        search: { type: "string", description: "Text search in block ID and title" },
        mounted: { type: "boolean", description: "Only return currently visible blocks" },
      },
    },
    execute: async (input) => blocksDiscoverExecute(input as BlocksDiscoverInput, registry),
    annotations: { readOnlyHint: true },
  });

  mc.registerTool({
    name: "blocks.read",
    description:
      "Read a block's data and UI state. Returns the block's current data, render state (loading/ready/error/empty), config, and optional render info.",
    inputSchema: {
      type: "object",
      properties: {
        blockId: { type: "string", description: "Block ID (e.g., 'career:pipeline')" },
        config: { type: "object", description: "Optional config override for data fetch" },
        includeState: { type: "boolean", description: "Include renderInfo (rowCount, columns)" },
      },
      required: ["blockId"],
    },
    execute: async (input) => blocksReadExecute(input as BlocksReadInput, registry),
    annotations: { readOnlyHint: true },
  });

  mc.registerTool({
    name: "blocks.configure",
    description:
      "Update a mounted block's configuration. Changes config values and optionally waits for re-render.",
    inputSchema: {
      type: "object",
      properties: {
        blockId: { type: "string", description: "Block ID" },
        instanceId: { type: "string", description: "Specific instance (if multiple)" },
        config: { type: "object", description: "Config values to set" },
        waitForSettle: { type: "boolean", description: "Wait for re-render (default: true)" },
      },
      required: ["blockId", "config"],
    },
    execute: async (input) => blocksConfigureExecute(input as BlocksConfigureInput, registry),
    annotations: { readOnlyHint: false },
  });

  mc.registerTool({
    name: "blocks.act",
    description:
      "Trigger an action on a mounted block. Supported actions: 'refresh', 'expand'.",
    inputSchema: {
      type: "object",
      properties: {
        blockId: { type: "string", description: "Block ID" },
        action: { type: "string", description: "Action name (refresh, expand)" },
        args: { type: "object", description: "Action-specific arguments" },
      },
      required: ["blockId", "action"],
    },
    execute: async (input) => blocksActExecute(input as BlocksActInput, registry),
    annotations: { readOnlyHint: false },
  });
}
