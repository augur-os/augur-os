"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { NoteQueueItem, type NoteQueueItemData } from "./NoteQueueItem";

interface NoteFABProps {
  queue: NoteQueueItemData[];
  onAddClick: () => void;
  onRetry?: (item: NoteQueueItemData) => void;
  suppress?: boolean;
}

export function NoteFAB({ queue, onAddClick, onRetry, suppress = false }: NoteFABProps) {
  const [expanded, setExpanded] = useState(false);
  const activeCount = queue.filter(
    (q) => q.status === "pending" || q.status === "processing"
  ).length;

  if (suppress) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2 md:hidden">
      {expanded && queue.length > 0 && (
        <div className="max-h-64 w-[calc(100vw-3rem)] max-w-80 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="text-sm font-medium">Processing ({activeCount})</span>
            <button type="button"
              onClick={() => setExpanded(false)}
              className="cursor-pointer text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
              aria-label="Close note queue"
            >
              <X className="size-4" />
            </button>
          </div>
          {queue.map((item) => (
            <NoteQueueItem key={item.jobId} item={item} onRetry={onRetry} />
          ))}
        </div>
      )}

      <button type="button"
        aria-label={activeCount > 0 ? "Show note queue" : "Add note"}
        onClick={() => {
          if (activeCount > 0) {
            setExpanded(!expanded);
          } else {
            onAddClick();
          }
        }}
        className="relative flex size-12 cursor-pointer items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2"
      >
        <Plus className="size-5" />
        {activeCount > 0 && (
          <span className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold text-white">
            {activeCount}
          </span>
        )}
      </button>
    </div>
  );
}
