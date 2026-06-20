"use client";

import { resolveIcon } from "@/lib/icon-map";
import type { SelectionAction } from "@/lib/browse/selectionActions";

interface SelectionActionBarProps {
  count: number;
  actions: SelectionAction[];
  onAction: (action: SelectionAction) => void;
  onSelectAllVisible: () => void;
  onClear: () => void;
}

export function SelectionActionBar({
  count,
  actions,
  onAction,
  onSelectAllVisible,
  onClear,
}: SelectionActionBarProps) {
  return (
    <div
      data-testid="selection-action-bar"
      // Viewport-fixed so the bar floats at the bottom on long lists too — a
      // sticky bar would be trapped inside Browse's overflow-hidden container
      // and only surface at the very end of the card list.
      // z-[80] keeps the bar above the floating chat window and note FAB
      // (both z-50) so an active selection is never occluded, while staying
      // below the chat launcher (z-90) which the user may still need.
      className="fixed bottom-6 left-1/2 z-[80] flex max-w-[calc(100vw-2rem)] -translate-x-1/2 flex-wrap items-center gap-2 rounded-xl border border-[var(--accent-primary)]/30 bg-[var(--bg-card)]/95 p-3 shadow-2xl backdrop-blur"
    >
      <span className="text-sm font-semibold text-[var(--text-primary)] tabular-nums">
        {count} selected
      </span>
      <div className="flex flex-wrap items-center gap-2">
        {actions.map((action) => {
          const Icon = resolveIcon(action.icon);
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onAction(action)}
              className="inline-flex min-h-[36px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 py-2 text-xs font-semibold text-[var(--accent-primary)] transition-colors hover:bg-[var(--accent-primary)]/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              <Icon className="size-4" />
              {action.label}
            </button>
          );
        })}
      </div>
      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onSelectAllVisible}
          className="inline-flex min-h-[36px] cursor-pointer items-center rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          Select all visible
        </button>
        <button
          type="button"
          onClick={onClear}
          className="inline-flex min-h-[36px] cursor-pointer items-center rounded-lg px-3 py-2 text-xs font-medium text-[var(--text-secondary)] underline-offset-2 transition-colors hover:text-[var(--text-primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
