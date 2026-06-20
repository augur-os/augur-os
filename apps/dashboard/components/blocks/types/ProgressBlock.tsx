"use client";

import { Target } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import { ProgressListRenderer } from "@/components/plugin/sections/ProgressListRenderer";
import type { ProgressDefinition } from "@/components/plugin/sections/types";

interface ProgressConfig {
  title?: string;
  value?: number;
  max?: number;
  /** ADR-274 D6 progress list configuration — if present, renders ProgressListRenderer */
  progress?: ProgressDefinition;
}

interface ProgressData {
  value: number;
  max?: number;
}

export default function ProgressBlock(props: BlockProps<ProgressConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Progress", progress } = config;
  const selfFetched = useBlockData<ProgressData | Record<string, unknown>[]>(
    dataSource,
    config,
    "progress",
  );
  const data = props.data ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  // If ADR-274 progress list config is present and data is an array, use ProgressListRenderer
  if (progress && progress.value_field && progress.max_field && progress.label_field) {
    const listData = Array.isArray(data) ? data as Record<string, unknown>[] : [];

    return (
      <BlockShell
        title={title}
        icon={Target}
        color="emerald"
        onExpand={onExpand}
        expandLabel="Details"
        staleError={error}
      >
        <div className="p-4">
          {loading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }, (_, i) => (
                <div
                  key={i}
                  className="h-16 rounded-lg bg-[var(--bg-hover)] animate-pulse"
                />
              ))}
            </div>
          )}

          {!loading && listData.length === 0 && !error && (
            <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
              No progress data available
            </p>
          )}
          {!loading && listData.length === 0 && error && (
            <div className="text-center py-6">
              <p className="text-xs text-red-400/80">Failed to load data</p>
              <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
            </div>
          )}
          {!loading && listData.length > 0 && (
            <ProgressListRenderer data={listData} progress={progress} />
          )}
        </div>
      </BlockShell>
    );
  }

  // Legacy fallback: single progress bar
  const singleData = data as ProgressData | null;
  const value = singleData?.value ?? config.value ?? 0;
  const max = singleData?.max ?? config.max ?? 100;
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;

  return (
    <BlockShell
      title={title}
      icon={Target}
      color="emerald"
      onExpand={onExpand}
      expandLabel="Details"
      staleError={error}
    >
      <div className="p-4 flex flex-col justify-center gap-3">
        {loading ? (
          <div className="h-12 rounded bg-[var(--bg-hover)] animate-pulse" />
        ) : !singleData && config.value === undefined ? (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No progress data available
          </p>
        ) : (
          <>
            <div className="text-center">
              <span className="text-2xl font-bold text-[var(--text-primary)]">
                {pct}%
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-[var(--bg-hover)]">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="text-xs text-[var(--text-muted)] text-center">
              {value} / {max}
            </p>
          </>
        )}
      </div>
    </BlockShell>
  );
}
