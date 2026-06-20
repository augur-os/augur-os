"use client";

import { useRef } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { useRouter } from "next/navigation";
import { Settings, X, GripVertical } from "lucide-react";
import {
  BLOCK_COMPONENTS,
  getBlockManifest,
} from "@/lib/blocks/block-resolver";
import { useBlockData } from "@/lib/blocks/useBlockData";
import type { BlockInstance } from "@/lib/blocks/types";
import { useWebMCPReport, useWebMCPSubscribe } from "@/lib/webmcp/useWebMCPReport";
import { SeedBadge } from "@/components/ui/SeedBadge";

interface BlockRendererProps {
  instance: BlockInstance;
  editing: boolean;
  onRemove?: (instanceId: string) => void;
  onConfigure?: (instanceId: string) => void;
}

function BlockError({
  error,
  resetErrorBoundary,
}: {
  error: unknown;
  resetErrorBoundary: (...args: unknown[]) => void;
}) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 rounded-xl bg-red-500/10 border border-red-500/20 p-4">
      <p className="text-xs text-red-400">Block failed to render</p>
      <p className="text-xs text-[var(--text-muted)] max-w-48 text-center break-words">
        {message}
      </p>
      <button type="button"
        onClick={() => resetErrorBoundary()}
        className="px-3 py-1 text-xs rounded-lg bg-[var(--bg-hover)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border border-[var(--border-color)] transition-colors"
      >
        Reload block
      </button>
    </div>
  );
}

export function BlockRenderer({
  instance,
  editing,
  onRemove,
  onConfigure,
}: BlockRendererProps) {
  const { push } = useRouter();
  const manifest = getBlockManifest(instance.blockId);

  // Subscribe to WebMCP config/refresh events from agent tool calls
  const { configOverride, refetchSignal } = useWebMCPSubscribe(instance.blockId);

  // Merge agent config override with instance config
  const effectiveConfig = configOverride
    ? { ...instance.config, ...configOverride }
    : instance.config;

  // Lift data fetching to renderer level
  const { data, loading, error, meta } = useBlockData(
    manifest?.dataSource,
    effectiveConfig,
    manifest?.type,
    refetchSignal,
  );

  // Report block state to WebMCP registry
  useWebMCPReport({
    blockId: instance.blockId,
    instanceId: instance.instanceId,
    type: manifest?.type ?? "stat-card",
    config: effectiveConfig,
    dataSource: manifest?.dataSource,
    data,
    loading,
    error,
  });

  const blockRef = useRef<HTMLDivElement>(null);

  const handleExpand = () => {
    if (manifest?.expandTo) {
      push(manifest.expandTo);
    }
  };

  return (
    <div className={`relative h-full z-[1] transition-shadow duration-200 ${!editing ? "hover:shadow-md hover:shadow-black/5 rounded-xl" : ""}`} data-instance-id={instance.instanceId}>
      {editing && (
        <div className="absolute top-1 right-1 z-10 flex gap-1">
          <button type="button"
            onClick={() => onConfigure?.(instance.instanceId)}
            aria-label="Configure block"
            className="p-1 rounded bg-[var(--bg-primary)]/80 hover:bg-[var(--bg-primary)] border border-[var(--border-primary)] cursor-pointer transition-colors"
          >
            <Settings className="size-3 text-[var(--text-secondary)]" />
          </button>
          <button type="button"
            onClick={() => onRemove?.(instance.instanceId)}
            aria-label="Remove block"
            className="p-1 rounded bg-[var(--bg-primary)]/80 hover:bg-red-500/20 border border-[var(--border-primary)] cursor-pointer transition-colors"
          >
            <X className="size-3 text-[var(--text-secondary)]" />
          </button>
        </div>
      )}
      {editing && (
        <div className="absolute top-1 left-1 z-10 cursor-grab drag-handle">
          <GripVertical className="size-4 text-[var(--text-secondary)]/70" />
        </div>
      )}
      <ErrorBoundary FallbackComponent={BlockError}>
        <div ref={blockRef}>
        {manifest && BLOCK_COMPONENTS[manifest.type] ? (
          (() => {
            const Block = BLOCK_COMPONENTS[manifest.type];
            return (
              <>
                <Block
                  instanceId={instance.instanceId}
                  config={{
                    title: manifest.title,
                    ...(manifest.action ? { action: manifest.action } : {}),
                    ...instance.config,
                  }}
                  dataSource={manifest?.dataSource}
                  mode="compact"
                  onExpand={manifest?.expandTo ? handleExpand : undefined}
                  data={data}
                  loading={loading}
                  error={error}
                  rowActions={manifest?.rowActions}
                  editableFields={manifest?.editableFields}
                  search={manifest?.search}
                  filters={manifest?.filters}
                  quickAdd={manifest?.quickAdd}
                  groupBy={manifest?.groupBy}
                  viewModes={manifest?.viewModes}
                  defaultView={manifest?.defaultView}
                  exportEnabled={manifest?.exportEnabled}
                />
                <SeedBadge source={meta?.source} vaultStatus={meta?.vaultStatus} />
              </>
            );
          })()
        ) : (
          <div className="h-full flex items-center justify-center rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
            <p className="text-xs text-[var(--text-secondary)]">
              Unknown block: {instance.blockId}
            </p>
          </div>
        )}
        </div>
      </ErrorBoundary>
    </div>
  );
}
