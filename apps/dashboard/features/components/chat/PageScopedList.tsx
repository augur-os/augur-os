"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { keyedRenderItems } from "@/lib/stable-render-key";

export interface PageScopedListProps<T, P extends object = Record<string, never>> {
  items: T[];
  hubItems: T[];
  hubName: string;
  ItemComponent: React.ComponentType<{ item: T; index: number } & P>;
  itemProps: P;
  emptyMessage?: string;
  hubEmptyMessage?: string;
}

export function PageScopedList<T, P extends object = Record<string, never>>({
  items,
  hubItems,
  hubName,
  ItemComponent,
  itemProps,
  emptyMessage = "No items available",
  hubEmptyMessage = "No additional items in this hub",
}: PageScopedListProps<T, P>) {
  const [hubExpanded, setHubExpanded] = useState(false);

  return (
    <div className="flex flex-col">
      {/* Primary items scoped to current skill */}
      <div className="flex flex-col">
        {items.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
            {emptyMessage}
          </div>
        ) : (
          keyedRenderItems(items).map(({ item, key }, index) => (
            <div key={key}>
              <ItemComponent item={item} index={index} {...itemProps} />
            </div>
          ))
        )}
      </div>

      {/* Hub section separator — only show when hub has items */}
      {hubItems.length > 0 && (
        <div className="border-t border-[var(--border-color)]">
          <button
            type="button"
            onClick={() => setHubExpanded(!hubExpanded)}
            aria-expanded={hubExpanded}
            aria-label={`${hubExpanded ? "Collapse" : "Expand"} items from ${hubName}`}
            className="w-full flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
          >
            {hubExpanded ? (
              <ChevronDown className="size-3 shrink-0" />
            ) : (
              <ChevronRight className="size-3 shrink-0" />
            )}
            <span>More from {hubName}</span>
            <span className="ml-auto px-1 py-px rounded bg-[var(--accent-primary)]/10 text-[10px] text-[var(--text-muted)] font-semibold">
              {hubItems.length}
            </span>
          </button>

          {hubExpanded && (
            <div className="flex flex-col">
              {keyedRenderItems(hubItems).map(({ item, key }, index) => (
                <div key={key}>
                  <ItemComponent item={item} index={index} {...itemProps} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
