"use client";

import type { ItemStatus, PhaseStatus } from "../types";
import { ItemRow } from "./ItemRow";

interface PhaseSectionProps {
  phase: PhaseStatus;
  onAction: (item: ItemStatus) => void;
  onSkip: (item: ItemStatus, skipped: boolean) => void;
}

export function PhaseSection({ phase, onAction, onSkip }: PhaseSectionProps) {
  const phaseComplete = phase.total > 0 && phase.completed >= phase.total;
  return (
    <section className="border-t border-[var(--border-color)] pt-3 first:border-t-0 first:pt-0">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">{phase.label}</h3>
        <span className="text-xs tabular-nums text-[var(--text-secondary)]">
          {phase.completed}/{phase.total}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bg-hover)]">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${phaseComplete ? "bg-[var(--accent-success)]" : "bg-[var(--accent-primary)]"}`}
          style={{ width: `${Math.max(0, Math.min(100, phase.pct))}%` }}
        />
      </div>
      <div className="mt-2 space-y-1">
        {phase.items.map((item) => (
          <ItemRow key={item.id} item={item} onAction={onAction} onSkip={onSkip} />
        ))}
      </div>
    </section>
  );
}
