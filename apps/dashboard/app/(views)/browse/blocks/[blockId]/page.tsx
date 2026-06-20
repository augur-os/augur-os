"use client";

import React from "react";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import Link from "next/link";
import { ChevronRight, ExternalLink, AlertCircle } from "lucide-react";
import { resolveIcon } from "@/lib/icon-map";
import { ErrorBoundary } from "react-error-boundary";
import {
  getBlockManifest,
  BLOCK_COMPONENTS,
} from "@/lib/blocks/block-resolver";
import type { ConfigSchema } from "@/lib/blocks/types";

function ResolvedIcon({ name, className }: { name: string; className?: string }) {
  return React.createElement(resolveIcon(name), { className });
}

function defaultsFromSchema(schema: ConfigSchema): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  for (const [key, field] of Object.entries(schema)) {
    if (field.default !== undefined) {
      defaults[key] = field.default;
    }
  }
  return defaults;
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
    <div className="flex flex-col items-center justify-center gap-3 p-8">
      <p className="text-xs text-[var(--accent-danger)]">Block failed to render</p>
      <p className="text-xs text-[var(--text-muted)] max-w-md text-center break-words">
        {message}
      </p>
      <button type="button"
        onClick={() => resetErrorBoundary()}
        className="px-3 py-1.5 text-xs rounded-lg bg-[var(--bg-hover)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border border-[var(--border-color)] transition-colors duration-200 cursor-pointer"
      >
        Reload block
      </button>
    </div>
  );
}

export default function BlockViewPage() {
  const params = useParams();
  const blockId = decodeURIComponent(params.blockId as string);

  const manifest = getBlockManifest(blockId);

  const config = useMemo(() => {
    if (!manifest?.configSchema) return {};
    return defaultsFromSchema(manifest.configSchema);
  }, [manifest]);

  if (!manifest) {
    return (
      <div className="space-y-6">
        <Link
          href="/browse"
          className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          &larr; Back to Browse
        </Link>
        <div className="text-center py-16">
          <AlertCircle className="size-8 text-[var(--text-muted)] mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] break-all">
            Block not found: {blockId}
          </p>
        </div>
      </div>
    );
  }

  const hubLabel =
    manifest.hub.charAt(0).toUpperCase() + manifest.hub.slice(1);

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm">
        <Link
          href="/browse"
          className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          Browse
        </Link>
        <ChevronRight className="size-3 text-[var(--text-muted)]" />
        <span className="text-[var(--text-secondary)]">Blocks</span>
        <ChevronRight className="size-3 text-[var(--text-muted)]" />
        <div className="flex items-center gap-1.5">
          <ResolvedIcon name={manifest.icon} className="size-4 text-[var(--accent-primary)]" />
          <span className="text-[var(--text-primary)] font-medium">
            {manifest.title}
          </span>
        </div>
      </div>

      {/* Block render area */}
      <div className="min-h-[400px] rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] overflow-hidden">
        <ErrorBoundary FallbackComponent={BlockError}>
          {BLOCK_COMPONENTS[manifest.type] ? (
            (() => {
              const Block = BLOCK_COMPONENTS[manifest.type];
              return (
                <Block
                  instanceId={`preview-${blockId}`}
                  config={config}
                  dataSource={manifest.dataSource}
                  mode="full"
                />
              );
            })()
          ) : (
            <div className="flex flex-col items-center justify-center p-8 min-h-[400px]">
              <AlertCircle className="size-8 text-[var(--text-muted)] mb-3" />
              <p className="text-sm text-[var(--text-secondary)]">
                No renderer for block type: <code className="font-mono">{manifest.type}</code>
              </p>
            </div>
          )}
        </ErrorBoundary>
      </div>

      {/* Metadata bar */}
      <div className="flex items-center gap-3 px-1 text-xs text-[var(--text-secondary)] min-w-0">
        <span className="px-2 py-0.5 rounded-lg bg-[var(--bg-secondary)] font-medium shrink-0">
          {manifest.type}
        </span>
        <span className="shrink-0">{hubLabel}</span>
        <span className="shrink-0">&middot;</span>
        <span className="truncate" title={manifest.skill}>{manifest.skill}</span>
        {manifest.expandTo && (
          <Link
            href={manifest.expandTo}
            className="ml-auto inline-flex items-center gap-1 text-[var(--accent-primary)] hover:underline"
          >
            View full page
            <ExternalLink className="size-3" />
          </Link>
        )}
      </div>
    </div>
  );
}
