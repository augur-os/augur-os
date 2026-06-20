"use client";

import { Monitor } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { keyedRenderItems } from "@/lib/stable-render-key";
import { BlockShell } from "../BlockShell";

interface OpsBoardConfig {
  title?: string;
}
interface OpsItem {
  label: string;
  status: string;
  detail?: string;
}

const STATUS_COLORS: Record<string, string> = {
  healthy: "bg-emerald-500",
  warning: "bg-amber-500 animate-pulse",
  error: "bg-red-500",
  idle: "bg-[var(--border-color)]",
};

export default function OpsBoardBlock(props: BlockProps<OpsBoardConfig>) {
  const { config, dataSource, mode, onExpand } = props;
  const { title = "Ops Board" } = config;
  const selfFetched = useBlockData<OpsItem[]>(
    dataSource,
    config,
    "ops-board",
  );
  const data = (props.data as OpsItem[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const items = Array.isArray(data) ? data : [];

  return (
    <BlockShell
      title={title}
      icon={Monitor}
      color="amber"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4 space-y-2">
        {loading &&
          ["ops-board-skeleton-a", "ops-board-skeleton-b", "ops-board-skeleton-c"].map((key) => (
            <div key={key} className="flex items-center gap-2">
              <div className="size-2 rounded-full bg-[var(--bg-hover)] animate-pulse" />
              <div className="flex-1 h-3 rounded bg-[var(--bg-hover)] animate-pulse" />
            </div>
          ))}

        {!loading && items.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center">
            No status data
          </p>
        )}
        {!loading && items.length === 0 && error && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading &&
          keyedRenderItems(items).map(({ item, key }) => (
            <div key={key} className="flex items-center gap-2">
              <div
                className={`size-2 rounded-full ${STATUS_COLORS[item.status] || STATUS_COLORS.idle}`}
              />
              <span className="text-xs text-[var(--text-secondary)]">
                {item.label}
              </span>
              {item.detail && (
                <span className="text-xs text-[var(--text-muted)] ml-auto">
                  {item.detail}
                </span>
              )}
            </div>
          ))}
      </div>
    </BlockShell>
  );
}
