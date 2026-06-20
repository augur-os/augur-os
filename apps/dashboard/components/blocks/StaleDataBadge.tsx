"use client";

import { AlertTriangle } from "lucide-react";

interface StaleDataBadgeProps {
  error: string;
}

/**
 * Small amber warning indicator shown in block header when data is stale
 * (fetch failed but cached data is still displayed).
 */
export function StaleDataBadge({ error }: StaleDataBadgeProps) {
  return (
    <div className="group/badge relative" title={error}>
      <AlertTriangle className="size-3.5 text-amber-500/80" />
      <div className="absolute right-0 top-5 z-50 hidden group-hover/badge:block min-w-48 max-w-64 p-2 rounded-lg bg-[var(--bg-primary)] border border-amber-500/30 shadow-lg">
        <p className="text-xs text-amber-400">Data may be stale</p>
        <p className="text-xs text-[var(--text-muted)] mt-1 break-words">
          {error}
        </p>
      </div>
    </div>
  );
}
