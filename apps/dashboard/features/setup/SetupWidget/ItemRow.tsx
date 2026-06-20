"use client";

import { CheckCircle2, Circle, Copy, ExternalLink, MinusCircle, RotateCcw, XCircle } from "lucide-react";
import type { ItemStatus } from "../types";

interface ItemRowProps {
  item: ItemStatus;
  onAction: (item: ItemStatus) => void;
  onSkip: (item: ItemStatus, skipped: boolean) => void;
}

function StatusIcon({ status }: { status: ItemStatus["status"] }) {
  if (status === "done") return <CheckCircle2 className="size-4 text-emerald-600" />;
  if (status === "skipped") return <MinusCircle className="size-4 text-[var(--text-muted)]" />;
  if (status === "regressed") return <XCircle className="size-4 text-amber-600" />;
  return <Circle className="size-4 text-[var(--text-muted)]" />;
}

function ActionIcon({ type }: { type: ItemStatus["action"]["type"] }) {
  if (type === "route") return <ExternalLink className="size-3.5" />;
  if (type === "command") return <Copy className="size-3.5" />;
  return <RotateCcw className="size-3.5" />;
}

export function ItemRow({ item, onAction, onSkip }: ItemRowProps) {
  const actionable = item.status === "pending" || item.status === "regressed";
  const skipped = item.status === "skipped";

  return (
    <div className="flex gap-2 rounded-md p-2 hover:bg-[var(--bg-hover)]">
      <div className="mt-0.5 shrink-0">
        <StatusIcon status={item.status} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-col items-start gap-2">
          <div className="min-w-0">
            <div className="text-sm font-medium leading-snug text-[var(--text-primary)]">
              {item.label}
            </div>
            <div className="mt-0.5 text-xs leading-snug text-[var(--text-secondary)]">
              {item.details || item.description}
            </div>
          </div>
          {actionable && (
            <button
              type="button"
              onClick={() => onAction(item)}
              className="inline-flex min-h-7 shrink-0 items-center gap-1 rounded-md border border-[var(--border-color)] px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
            >
              <ActionIcon type={item.action.type} />
              <span>{item.action.label}</span>
            </button>
          )}
        </div>
        {(actionable || skipped) && (
          <button
            type="button"
            onClick={() => onSkip(item, !skipped)}
            className="mt-1 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            aria-label={`${skipped ? "Unskip" : "Skip"} ${item.label}`}
          >
            {skipped ? "Unskip" : "Skip"}
          </button>
        )}
      </div>
    </div>
  );
}
