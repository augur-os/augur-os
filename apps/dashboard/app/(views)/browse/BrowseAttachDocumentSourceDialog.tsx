"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { mcpCall } from "@/lib/mcp/client";

type BrowseAttachDocumentSourceDialogProps = {
  open: boolean;
  brainId: string;
  brainLabel: string;
  onOpenChange: (open: boolean) => void;
  onAttached: () => void;
};

const PROVIDERS = [
  { value: "google-drive", label: "Google Drive" },
  { value: "sharepoint", label: "SharePoint" },
  { value: "onedrive", label: "OneDrive" },
  { value: "github", label: "GitHub" },
  { value: "notion", label: "Notion" },
  { value: "confluence", label: "Confluence" },
  { value: "shared-folder", label: "Shared folder" },
];

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function BrowseAttachDocumentSourceDialog({
  open,
  brainId,
  brainLabel,
  onOpenChange,
  onAttached,
}: BrowseAttachDocumentSourceDialogProps) {
  const [provider, setProvider] = useState("google-drive");
  const [name, setName] = useState("");
  const [remoteId, setRemoteId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [summary, setSummary] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const effectiveSourceId = useMemo(() => sourceId.trim() || slugify(name), [name, sourceId]);

  if (!open) return null;

  async function submit() {
    const trimmedName = name.trim();
    const trimmedRemoteId = remoteId.trim();
    const trimmedSummary = summary.trim();
    if (!brainId || !trimmedName || !trimmedRemoteId || !effectiveSourceId) {
      toast.error("Source name and shared id are required");
      return;
    }

    setSubmitting(true);
    try {
      const result = await mcpCall<{ success?: boolean; error?: string }>("attach-project-document-source", {
        source_id: effectiveSourceId,
        name: trimmedName,
        provider,
        remote_id: trimmedRemoteId,
        attached_brain_ids: [brainId],
        catalog_summary: trimmedSummary,
        summary_status: trimmedSummary ? "human" : "",
      });
      if (result.success === false) {
        toast.error(result.error || "Could not attach source");
        return;
      }
      toast.success("Document source attached");
      onAttached();
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not attach source");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Attach shared document source"
    >
      <div className="w-full max-w-lg rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-4 shadow-xl shadow-black/25">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Attach shared source</h2>
          <p className="mt-1 text-xs text-[var(--text-muted)]">{brainLabel}</p>
        </div>
        <div className="space-y-3">
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Provider
            <select
              aria-label="Provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
              className="mt-1 h-9 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              {PROVIDERS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Source name
            <input
              aria-label="Source name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-1 h-9 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            />
          </label>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Shared URL or remote id
            <input
              aria-label="Shared URL or remote id"
              value={remoteId}
              onChange={(event) => setRemoteId(event.target.value)}
              className="mt-1 h-9 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            />
          </label>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Source id
            <input
              aria-label="Source id"
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              placeholder={effectiveSourceId || "project-source-id"}
              className="mt-1 h-9 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            />
          </label>
          <label className="block text-xs font-medium text-[var(--text-secondary)]">
            Summary
            <textarea
              aria-label="Summary"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              rows={3}
              className="mt-1 w-full resize-none rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            />
          </label>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="h-9 rounded-md border border-[var(--border-color)] px-3 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => {
              void submit();
            }}
            className="h-9 rounded-md bg-[var(--accent-primary)] px-3 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          >
            {submitting ? "Attaching..." : "Attach source"}
          </button>
        </div>
      </div>
    </div>
  );
}
