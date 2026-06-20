"use client";

import React, { createElement, useMemo, useCallback, createContext, use, useSyncExternalStore } from "react";
import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import { LayoutDashboard } from "lucide-react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { resolveIcon as resolveIconFromMap } from "@/lib/icon-map";
import type { LucideIcon } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { FlowLayout } from "@/lib/blocks/flow-layout";
import { BLOCK_COMPONENTS } from "@/lib/blocks/block-resolver";
import { CUSTOM_BLOCK_COMPONENTS } from "@/lib/blocks/custom-block-registry";
import { useBlockData } from "@/lib/blocks/useBlockData";
import type { PageConfig, BlockConfig, BlockSize, ShowIfExpression } from "@/lib/blocks/flow-types";
import type { DataSource } from "@/lib/blocks/types";
import { useModeStore } from "@/lib/stores/modeStore";

// ---------------------------------------------------------------------------
// Custom block props — passed to dynamically loaded custom components
// ---------------------------------------------------------------------------
export interface CustomBlockProps {
  skillId?: string;
  config: BlockConfig;
}

// ---------------------------------------------------------------------------
// Lazy-loaded custom component cache — avoids calling dynamic() during render
// ---------------------------------------------------------------------------
const customComponentCache = new Map<string, ComponentType<CustomBlockProps>>();

function getCustomComponent(componentName: string): ComponentType<CustomBlockProps> | null {
  const cached = customComponentCache.get(componentName);
  if (cached) return cached;

  const factory = CUSTOM_BLOCK_COMPONENTS[componentName];
  if (!factory) return null;

  const DynamicComponent = dynamic(factory, {
    loading: () => (
      <div className="h-full flex items-center justify-center rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] p-4">
        <p className="text-xs text-[var(--text-muted)]">Loading {componentName}...</p>
      </div>
    ),
  });

  customComponentCache.set(componentName, DynamicComponent as ComponentType<CustomBlockProps>);
  return DynamicComponent as ComponentType<CustomBlockProps>;
}

// ---------------------------------------------------------------------------
// Icon resolver — string name to LucideIcon component
// ---------------------------------------------------------------------------
function resolveIcon(name?: string): LucideIcon {
  return resolveIconFromMap(name, LayoutDashboard);
}

function ResolvedIcon({ name, className }: { name?: string; className?: string }) {
  return createElement(resolveIcon(name), { className });
}

function renderCustomComponent(
  componentName: string,
  props: CustomBlockProps,
): React.ReactNode | null {
  const CustomComponent = getCustomComponent(componentName);
  if (!CustomComponent) return null;
  return createElement(CustomComponent, props);
}

// ---------------------------------------------------------------------------
// showIf — conditional block visibility via shared data status context
// ---------------------------------------------------------------------------

/** Map of block id → whether that block has non-empty data */
const BlockDataMapCtx = createContext<Record<string, boolean>>({});

interface FlowBlockRuntime {
  config: Record<string, unknown>;
  dataSource?: DataSource;
}

interface CachedBlockDataResult {
  data?: unknown;
}

function buildFlowBlockRuntime(
  block: BlockConfig,
  skillId?: string,
): FlowBlockRuntime {
  const {
    type: _type,
    mcp_tool,
    component: _component,
    size: _size,
    scope: _scope,
    skill_id,
    manifest_id: _manifestId,
    search: _search,
    filters: _filters,
    row_actions: _rowActions,
    quick_add: _quickAdd,
    group_by: _groupBy,
    view_modes: _viewModes,
    default_view: _defaultView,
    export_enabled: _exportEnabled,
    config_schema: _configSchema,
    id: _id,
    showIf: _showIf,
    ...rest
  } = block;
  return {
    config: { ...rest, skillId: skill_id ?? skillId },
    dataSource: mcp_tool ? { mcpTool: mcp_tool } : undefined,
  };
}

function getBlockQueryKey(runtime: FlowBlockRuntime): unknown[] | null {
  const sourceKey = runtime.dataSource?.mcpTool || "";
  if (!sourceKey) {
    return null;
  }
  return ["block-data", sourceKey, JSON.stringify(runtime.config), 0];
}

function createBlockDataMapSnapshotter(
  queryClient: QueryClient,
  blocks: BlockConfig[],
  skillId?: string,
): () => Record<string, boolean> {
  let lastKey = "";
  let lastSnapshot: Record<string, boolean> = {};

  return () => {
    const entries: Array<readonly [string, boolean]> = [];
    for (const block of blocks) {
      if (typeof block.id !== "string" || block.id.length === 0) {
        continue;
      }
      const runtime = buildFlowBlockRuntime(block, skillId);
      const queryKey = getBlockQueryKey(runtime);
      const cached = queryKey
        ? queryClient.getQueryData<CachedBlockDataResult>(queryKey)
        : undefined;
      entries.push([block.id, hasNonEmptyData(cached?.data)] as const);
    }
    const snapshotKey = JSON.stringify(entries);
    if (snapshotKey === lastKey) {
      return lastSnapshot;
    }
    lastKey = snapshotKey;
    lastSnapshot = Object.fromEntries(entries);
    return lastSnapshot;
  };
}

function useFlowBlockDataMap(
  blocks: BlockConfig[],
  skillId?: string,
): Record<string, boolean> {
  const queryClient = useQueryClient();
  const getSnapshot = useMemo(
    () => createBlockDataMapSnapshotter(queryClient, blocks, skillId),
    [queryClient, blocks, skillId],
  );
  const subscribe = useCallback(
    (listener: () => void) => queryClient.getQueryCache().subscribe(listener),
    [queryClient],
  );
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/** Check if data is non-empty (array with items, object with keys, or truthy scalar) */
export function hasNonEmptyData(data: unknown): boolean {
  if (data == null) return false;
  if (Array.isArray(data)) return data.length > 0;
  if (typeof data === "object") return Object.keys(data as Record<string, unknown>).length > 0;
  return true;
}

/** Evaluate a showIf expression against the block data map */
function evaluateShowIf(
  expr: ShowIfExpression,
  blockDataMap: Record<string, boolean>,
): boolean {
  if ("blockHasData" in expr) {
    return blockDataMap[expr.blockHasData] === true;
  }
  // configFlag is reserved for future use — always show for now
  return true;
}

// ---------------------------------------------------------------------------
// FlowBlockRenderer — bridges BlockConfig (from flow-types) to block components
// ---------------------------------------------------------------------------
interface FlowBlockRendererProps {
  block: BlockConfig;
  index: number;
  skillId?: string;
}

function FlowBlockRenderer({ block, index, skillId }: FlowBlockRendererProps) {
  const {
    type,
    component,
    manifest_id,
    search,
    filters,
    row_actions,
    quick_add,
    group_by,
    view_modes,
    default_view,
    export_enabled,
    showIf,
  } = block;
  const { config, dataSource } = buildFlowBlockRuntime(block, skillId);

  // Construct a BlockInstance-compatible shape from BlockConfig
  const blockId = manifest_id ?? type;
  const instanceId = `flow-${blockId}-${index}`;

  const { data, loading, error } = useBlockData(dataSource, config, type === "custom" ? undefined : type);

  // Evaluate showIf — return null when condition fails (FlowLayout skips nulls)
  const blockDataMap = use(BlockDataMapCtx);
  if (showIf && !evaluateShowIf(showIf, blockDataMap)) {
    return null;
  }

  // Resolve custom blocks via the generated registry
  if (type === "custom") {
    if (!component) {
      return (
        <div className="h-full flex items-center justify-center rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] p-4">
          <p className="text-xs text-red-400">
            Custom block missing &quot;component&quot; field
          </p>
        </div>
      );
    }

    const customComponent = renderCustomComponent(component, {
      skillId,
      config: block,
    });
    if (!customComponent) {
      return (
        <div className="h-full flex items-center justify-center rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] p-4">
          <p className="text-xs text-red-400">
            Custom component &apos;{component}&apos; not found in registry
          </p>
        </div>
      );
    }

    return customComponent;
  }

  const BlockComponent = BLOCK_COMPONENTS[type];

  if (!BlockComponent) {
    return (
      <div className="h-full flex items-center justify-center rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] p-4">
        <p className="text-xs text-[var(--text-secondary)]">
          Unknown block type: {type}
        </p>
      </div>
    );
  }

  return (
    <BlockComponent
      instanceId={instanceId}
      config={config}
      dataSource={dataSource}
      mode="compact"
      data={data}
      loading={loading}
      error={error}
      search={search}
      filters={filters}
      rowActions={row_actions}
      quickAdd={quick_add}
      groupBy={group_by}
      viewModes={view_modes}
      defaultView={default_view}
      exportEnabled={export_enabled}
    />
  );
}

// Re-export for convenience — the implementation lives in a shared module so
// server components (e.g. Browse detail) can also import it without pulling in
// client-only code.
export { buildDefaultPageConfig } from "@/lib/blocks/build-default-page-config";

// ---------------------------------------------------------------------------
// ConfigPage — renders a PageConfig as an ordered list of blocks in FlowLayout
// ---------------------------------------------------------------------------
export interface ConfigPageProps {
  config: PageConfig;
  skillId?: string;
}

export function ConfigPage({ config, skillId }: ConfigPageProps) {
  const mode = useModeStore((s) => s.mode);

  // Build the block list — append dev-only blocks when in development mode
  const blocks = useMemo(() => {
    const base = [...config.blocks];
    if (mode === "development" && skillId) {
      base.push({
        type: "data-table" as const,
        mcp_tool: "get-skill-health",
        size: "full",
        skill_id: skillId,
        title: "Skill Health (dev)",
      } satisfies BlockConfig);
    }
    return base;
  }, [config.blocks, mode, skillId]);
  const blockDataMap = useFlowBlockDataMap(blocks, skillId);

  const sizes: BlockSize[] = blocks.map((b) => b.size ?? "full");

  const children = blocks.map((block, i) => (
    <ErrorBoundary
      key={`${block.type}-${i}`}
      fallback={
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-center">
          <p className="text-xs text-red-400">Block failed to render</p>
          <p className="text-xs text-[var(--text-muted)] mt-1">{block.type}</p>
        </div>
      }
    >
      <FlowBlockRenderer block={block} index={i} skillId={skillId} />
    </ErrorBoundary>
  ));

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-3">
        <div className="rounded-xl border border-[var(--accent-primary)]/25 bg-[var(--accent-primary)]/10 p-3">
          <ResolvedIcon
            name={config.icon}
            className="size-5 text-[var(--accent-primary)]"
          />
        </div>
        <div className="min-w-0">
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">{config.title}</h2>
          {config.description ? (
            <p className="mt-1 text-sm text-[var(--text-muted)]">{config.description}</p>
          ) : null}
        </div>
      </header>
      <BlockDataMapCtx.Provider value={blockDataMap}>
        <FlowLayout sizes={sizes}>{children}</FlowLayout>
      </BlockDataMapCtx.Provider>
    </div>
  );
}
