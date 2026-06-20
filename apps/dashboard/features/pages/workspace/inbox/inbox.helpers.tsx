"use client";

import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { FOLDER_PRESETS } from "./inbox.types";
import type { EmailAction, InboxAction } from "./types";

export function CountTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-h-[76px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-3">
      <div className="text-xs font-medium uppercase text-[var(--text-muted)]">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

export function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function formatInboxDate(value?: string | null) {
  if (!value) {
    return "Never";
  }
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function formatRunStatus(status?: string | null) {
  return status?.trim() || "No previous action";
}

export function baseName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}

export function asInboxAction(action: InboxAction | EmailAction): InboxAction | null {
  return action === "scan" || action === "consume" || action === "purge" ? action : null;
}

export function ActionButton({
  label,
  busy,
  disabled,
  onClick,
  children,
}: {
  label: string;
  busy: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={busy || disabled}
      onClick={onClick}
      className="inline-flex min-h-[44px] min-w-[104px] items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
    >
      {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : children}
    </button>
  );
}

export function FolderPresetButtons({
  onSelect,
}: {
  onSelect: (preset: { name: string; path: string }) => void;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[360px]">
      {FOLDER_PRESETS.map((preset) => {
        const Icon = preset.icon;
        return (
          <button
            key={preset.name}
            type="button"
            onClick={() => onSelect(preset)}
            className="flex min-h-[72px] items-start gap-3 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-3 text-left transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            aria-label={`Use ${preset.name}`}
          >
            <Icon className="mt-0.5 size-4 shrink-0 text-[var(--text-secondary)]" aria-hidden="true" />
            <span className="min-w-0">
              <span className="block text-sm font-medium text-[var(--text-primary)]">{preset.name}</span>
              <span className="mt-1 block text-xs leading-4 text-[var(--text-muted)]">{preset.detail}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
