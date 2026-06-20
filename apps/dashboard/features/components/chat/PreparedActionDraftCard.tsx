"use client";

import { ChevronDown, Loader2, Send, X } from "lucide-react";
import type { PreparedActionDraft } from "@/lib/actions/preparedActionDraft";

export function PreparedActionDraftCard({
  draft,
  selectedClientLabel,
  userRemarks,
  onUserRemarksChange,
  onSend,
  onCancel,
  canSend,
  isSending,
  error,
}: {
  draft: PreparedActionDraft;
  selectedClientLabel: string;
  userRemarks: string;
  onUserRemarksChange: (value: string) => void;
  onSend: () => void;
  onCancel: () => void;
  canSend: boolean;
  isSending: boolean;
  error: string | null;
}) {
  return (
    // Sizes to its content and is centered by the parent panel — a one-line
    // action no longer stretches the instructions box down the whole window.
    // Body scrolls internally so the header/footer stay anchored when tall.
    <section className="flex max-h-full w-full max-w-md flex-col overflow-hidden rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] shadow-[0_12px_40px_rgba(15,23,42,0.14)]">
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border-color)]/70 px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Prepared action
            </span>
            <span className="rounded-full border border-[var(--accent-primary)]/25 bg-[var(--accent-primary)]/10 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--accent-primary)]">
              AI draft
            </span>
          </div>
          <h3 className="mt-1.5 truncate text-base font-semibold text-[var(--text-primary)]">
            {draft.label}
          </h3>
          {draft.description && (
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-[var(--text-secondary)]">
              {draft.description}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="flex size-7 shrink-0 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          aria-label="Cancel prepared action"
          title="Dismiss"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>

      <div className="flex min-h-0 flex-col gap-3 overflow-y-auto px-4 py-3">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="prepared-action-remarks"
            className="flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)]"
          >
            Instructions
            <span className="font-normal text-[var(--text-muted)]">
              — optional
            </span>
          </label>
          <textarea
            id="prepared-action-remarks"
            aria-label="Prepared action remarks"
            value={userRemarks}
            onChange={(event) => onUserRemarksChange(event.target.value)}
            placeholder="Add context or constraints — or leave blank to run as drafted."
            disabled={isSending}
            rows={4}
            className="max-h-56 min-h-[6rem] w-full resize-y rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm leading-relaxed text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]/30 disabled:opacity-60"
          />
        </div>

        <details className="group">
          <summary className="flex cursor-pointer select-none items-center gap-1 text-xs font-medium text-[var(--text-muted)] transition-colors hover:text-[var(--text-secondary)]">
            <ChevronDown
              className="size-3 transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
            System prompt preview
          </summary>
          <pre className="mt-2 max-h-32 overflow-y-auto whitespace-pre-wrap rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-2 font-mono text-[11px] text-[var(--text-muted)]">
            {draft.prompt}
          </pre>
        </details>

        {error && (
          <div className="rounded-md border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-2 py-1.5 text-xs text-[var(--accent-danger)]">
            {error}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-[var(--border-color)]/70 px-4 py-3">
        <div className="flex min-w-0 items-center gap-1.5 text-xs text-[var(--text-muted)]">
          <span className="shrink-0">Sends to</span>
          <span
            className="size-1.5 shrink-0 rounded-full bg-[var(--accent-primary)]"
            aria-hidden="true"
          />
          <span className="min-w-0 truncate font-medium capitalize text-[var(--text-secondary)]">
            {selectedClientLabel}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSending}
            className="rounded-md px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSend}
            disabled={!canSend || isSending}
            className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--accent-foreground)] transition-opacity hover:opacity-90 disabled:opacity-40"
            aria-label="Send prepared action"
          >
            {isSending ? (
              <Loader2
                className="size-3.5 animate-spin"
                aria-hidden="true"
              />
            ) : (
              <Send className="size-3.5" aria-hidden="true" />
            )}
            Send
          </button>
        </div>
      </div>
    </section>
  );
}
