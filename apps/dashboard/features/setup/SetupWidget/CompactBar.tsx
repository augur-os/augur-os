"use client";

import type { SetupStatus } from "../types";

interface CompactBarProps {
  status: SetupStatus;
  onOpen: () => void;
}

export function CompactBar({ status, onOpen }: CompactBarProps) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Setup ${status.pct} percent complete`}
      className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-3 text-left hover:bg-[var(--bg-hover)]"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-[var(--text-primary)]">Setup progress</span>
        <span className="text-xs tabular-nums text-[var(--text-secondary)]">
          {status.completed}/{status.total} - {status.pct}%
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bg-hover)]">
        <div
          className="h-full rounded-full bg-[var(--accent-primary)]"
          style={{ width: `${Math.max(0, Math.min(100, status.pct))}%` }}
        />
      </div>
    </button>
  );
}
