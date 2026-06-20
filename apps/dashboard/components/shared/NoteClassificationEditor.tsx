"use client";

import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";
import {
  noteClassificationForItem,
  noteDomainOptions,
  noteDomainLabel,
  noteSourceLabel,
  noteSourceOptions,
  noteStatusLabel,
  noteStatusOptionsForDomain,
} from "@/lib/browse/noteClassification";
import type {
  BrowseItem,
  NoteDomain,
  NoteSource,
  NoteStatus,
} from "@/lib/browse/types";

type NoteClassificationUpdateBody = {
  note_path: string;
  domain: string;
  source: string;
  status: string;
  classification_confidence: string;
};

type NoteClassificationUpdateResult = {
  success?: boolean;
  error?: string;
};

export function NoteClassificationEditor({ item }: { item: BrowseItem }) {
  const classification = noteClassificationForItem(item);
  const initialDomain = classification.domain ?? "research";
  const initialSource = classification.source ?? "website";
  const initialStatus = classification.status ?? "";
  const path = item.path || item.primaryAction.target || "";

  return (
    <NoteClassificationEditorForm
      key={`${path}:${initialDomain}:${initialSource}:${initialStatus}`}
      path={path}
      initialDomain={initialDomain}
      initialSource={initialSource}
      initialStatus={initialStatus}
    />
  );
}

function NoteClassificationEditorForm({
  path,
  initialDomain,
  initialSource,
  initialStatus,
}: {
  path: string;
  initialDomain: NoteDomain;
  initialSource: NoteSource;
  initialStatus: NoteStatus | "";
}) {
  const [domain, setDomain] = useState<NoteDomain>(initialDomain);
  const [source, setSource] = useState<NoteSource>(initialSource);
  const [status, setStatus] = useState<NoteStatus | "">(initialStatus);
  const [saved, setSaved] = useState(false);
  const domainOptions = useMemo(
    () => withCurrentOption(noteDomainOptions(), domain, noteDomainLabel),
    [domain],
  );
  const sourceOptions = useMemo(
    () => withCurrentOption(noteSourceOptions(), source, noteSourceLabel),
    [source],
  );
  const statusOptions = useMemo(
    () =>
      status
        ? withCurrentOption(noteStatusOptionsForDomain(domain), status, noteStatusLabel)
        : noteStatusOptionsForDomain(domain),
    [domain, status],
  );
  const { mutate, loading, error } = useMcpMutation<
    NoteClassificationUpdateResult,
    NoteClassificationUpdateBody
  >("note-classification-update", {
    invalidates: ["browse-index"],
    onSuccess: (result) => {
      if (result?.success === false) {
        throw new Error(result.error || "Classification update failed");
      }
      setSaved(true);
    },
  });

  const save = async () => {
    setSaved(false);
    try {
      await mutate({
        note_path: path,
        domain,
        source,
        status: statusOptions.some((option) => option.id === status) ? status : "",
        classification_confidence: "high",
      });
    } catch {
      // useMcpMutation owns the user-visible error state.
    }
  };

  return (
    <section>
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Classification
      </h3>
      <div className="space-y-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
            Domain
            <select
              value={domain}
              onChange={(event) => {
                const nextDomain = event.target.value as NoteDomain;
                const allowed = noteStatusOptionsForDomain(nextDomain);
                setDomain(nextDomain);
                setStatus((current) =>
                  allowed.some((option) => option.id === current) ? current : "",
                );
              }}
              className="min-h-[40px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)]"
            >
              {domainOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
            Source
            <select
              value={source}
              onChange={(event) => setSource(event.target.value as NoteSource)}
              className="min-h-[40px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)]"
            >
              {sourceOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
            Status
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as NoteStatus | "")}
              disabled={statusOptions.length === 0}
              className="min-h-[40px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] disabled:opacity-50"
            >
              <option value="">None</option>
              {statusOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void save()}
            disabled={loading || !path}
            className="inline-flex min-h-[34px] cursor-pointer items-center gap-2 rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 text-xs font-semibold text-[var(--accent-primary)] transition-colors hover:bg-[var(--accent-primary)]/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : null}
            Save classification
          </button>
          {saved ? <span className="text-xs text-[var(--accent-success)]">Saved</span> : null}
          {error ? <span className="text-xs text-[var(--accent-danger)]">{error}</span> : null}
        </div>
      </div>
    </section>
  );
}

function withCurrentOption<T extends string>(
  options: Array<{ id: T; label: string }>,
  current: T,
  labelForValue: (value: T) => string,
): Array<{ id: T; label: string }> {
  if (options.some((option) => option.id === current)) return options;
  return [{ id: current, label: labelForValue(current) }, ...options];
}
