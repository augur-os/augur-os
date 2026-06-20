"use client";

import { Activity } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";

interface ActivityConfig {
  limit?: number;
}
interface FeedItem {
  id?: string;
  message?: string;
  title?: string;
  timestamp?: string;
}

export default function ActivityFeedBlock(props: BlockProps<ActivityConfig>) {
  const { config, dataSource, mode, onExpand } = props;
  const { limit = 5 } = config;
  const selfFetched = useBlockData<FeedItem[]>(
    dataSource,
    config,
    "activity-feed",
  );
  const data = (props.data as FeedItem[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const items = Array.isArray(data) ? data : [];

  return (
    <BlockShell
      title="Activity"
      icon={Activity}
      color="emerald"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4 space-y-2">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="flex gap-2">
              <div className="size-1.5 mt-1.5 rounded-full bg-emerald-500/40 shrink-0" />
              <div className="flex-1 h-3 rounded bg-[var(--bg-hover)] animate-pulse" />
            </div>
          ))}

        {!loading && items.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No recent activity
          </p>
        )}
        {!loading && items.length === 0 && error && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading &&
          items.slice(0, limit).map((item, i) => (
            <div key={item.id || i} className="flex gap-2">
              <div className="size-1.5 mt-1.5 rounded-full bg-emerald-500/60 shrink-0" />
              <div className="flex-1">
                <p className="text-xs text-[var(--text-primary)]">
                  {item.message || item.title}
                </p>
                {item.timestamp && (
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {item.timestamp}
                  </p>
                )}
              </div>
            </div>
          ))}
      </div>
    </BlockShell>
  );
}
