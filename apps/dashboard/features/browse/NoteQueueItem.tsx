"use client";

import { Circle, CheckCircle2, XCircle, Loader2, RotateCw } from "lucide-react";

export interface NoteQueueItemData {
  jobId: string;
  name: string;
  status: "pending" | "processing" | "completed" | "failed";
  stage?: string;
  destination?: string;
  error?: string;
}

const STATUS_ICONS = {
  pending: <Circle className="size-4 text-muted-foreground" />,
  processing: <Loader2 className="size-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle2 className="size-4 text-green-500" />,
  failed: <XCircle className="size-4 text-red-500" />,
} as const;

const URL_PATTERN = /^https?:\/\//i;

interface NoteQueueItemProps {
  item: NoteQueueItemData;
  onRetry?: (item: NoteQueueItemData) => void;
}

export function NoteQueueItem({ item, onRetry }: NoteQueueItemProps) {
  const canRetry =
    item.status === "failed" && onRetry !== undefined && URL_PATTERN.test(item.name);

  return (
    <div className="flex items-center gap-2 px-3 py-2 text-sm border-b border-border last:border-0">
      {STATUS_ICONS[item.status]}
      <div className="flex-1 min-w-0">
        <div className="truncate font-medium">{item.name}</div>
        {item.stage && item.status === "processing" && (
          <div className="text-xs text-muted-foreground">{item.stage}...</div>
        )}
        {item.destination && item.status === "completed" && (
          <div className="text-xs text-muted-foreground truncate">
            &rarr; {item.destination}
          </div>
        )}
        {item.error && (
          <div className="text-xs text-red-400 truncate">{item.error}</div>
        )}
      </div>
      {canRetry && (
        <button
          type="button"
          onClick={() => onRetry?.(item)}
          className="inline-flex min-h-[28px] items-center gap-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          aria-label={`Retry ingest of ${item.name}`}
        >
          <RotateCw className="size-3" />
          Retry
        </button>
      )}
    </div>
  );
}
