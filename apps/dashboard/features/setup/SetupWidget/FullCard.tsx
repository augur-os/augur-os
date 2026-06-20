"use client";

import { AlertTriangle, Minimize2, RefreshCw } from "lucide-react";
import type { ItemStatus, SetupStatus } from "../types";
import { PhaseSection } from "./PhaseSection";

interface FullCardProps {
  status: SetupStatus;
  variant: "sidebar" | "settings" | "page";
  busy: boolean;
  onAction: (item: ItemStatus) => void;
  onSkip: (item: ItemStatus, skipped: boolean) => void;
  onRefresh: () => void;
  onCollapse?: () => void;
}

export function FullCard({ status, variant, busy, onAction, onSkip, onRefresh, onCollapse }: FullCardProps) {
  const alert = status.state === "alert";
  const complete = status.state === "chip";
  const phases = Array.isArray(status.phases) ? status.phases : [];
  const completed = Number.isFinite(status.completed) ? status.completed : 0;
  const total = Number.isFinite(status.total) ? status.total : phases.length;
  const pct = Number.isFinite(status.pct) ? status.pct : 0;
  const subtitle = alert
    ? "Some setup evidence changed. Review the highlighted items."
    : complete
      ? "All setup checks are complete. Reopen this when your environment changes."
      : "Finish the remaining setup checks that unlock daily value.";

  return (
    <div
      data-testid="setup-full-card"
      className={`rounded-lg border ${
        alert ? "border-amber-500/60 bg-amber-500/10" : "border-[var(--border-color)] bg-[var(--bg-primary)]"
      } ${variant === "sidebar" ? "p-3" : "p-4"}`}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            {alert && <AlertTriangle className="size-4 text-amber-600" />}
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Setup progress</h2>
          </div>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {subtitle}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 text-right">
          <div className="text-sm font-semibold tabular-nums text-[var(--text-primary)]">
            {completed}/{total}
          </div>
          <div className="flex flex-wrap justify-end gap-1">
            <button
              type="button"
              onClick={onRefresh}
              disabled={busy}
              className="inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-xs text-[var(--text-muted)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
            >
              <RefreshCw className={`size-3.5 ${busy ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
            {variant === "sidebar" && onCollapse && (
              <button
                type="button"
                onClick={onCollapse}
                className="inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-xs text-[var(--text-muted)] hover:bg-[var(--bg-hover)]"
              >
                <Minimize2 className="size-3.5" />
                <span>Minimize</span>
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-[var(--bg-hover)]">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${alert ? "bg-amber-500" : complete ? "bg-[var(--accent-success)]" : "bg-[var(--accent-primary)]"}`}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
      <div className="space-y-4">
        {phases.map((phase) => (
          <PhaseSection key={phase.id} phase={phase} onAction={onAction} onSkip={onSkip} />
        ))}
      </div>
    </div>
  );
}
