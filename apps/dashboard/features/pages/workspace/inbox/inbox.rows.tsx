"use client";

import {
  FileCheck2,
  FolderOpen,
  Link2,
  Paperclip,
  Play,
  RefreshCw,
  ScanLine,
  Trash2,
} from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";
import {
  ActionButton,
  baseName,
  formatInboxDate,
  formatRunStatus,
  pluralize,
} from "./inbox.helpers";
import type { EmailAction, EmailSource, InboxAction, InboxFolder, InboxRun } from "./types";

export function FolderRow({
  folder,
  activeAction,
  onAction,
}: {
  folder: InboxFolder;
  activeAction: InboxAction | null;
  onAction: (action: InboxAction) => void;
}) {
  const disabled = !folder.enabled || activeAction !== null;
  const impactParts = [
    `scan reviews ${pluralize(folder.counts.new_files, "new file")}`,
    `consume routes ${pluralize(folder.counts.document_candidates, "document candidate")}`,
    `purge moves ${pluralize(folder.counts.trash_candidates, "trash candidate")}`,
  ];

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">{folder.name}</h2>
            <span className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
              {folder.enabled ? "Watching" : "Paused"}
            </span>
          </div>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
            <p className="truncate text-sm text-[var(--text-muted)]" title={folder.path}>
              {folder.path}
            </p>
            <button
              type="button"
              aria-label={`Reveal ${folder.name} in Finder`}
              title="Reveal in Finder"
              onClick={() => {
                void mcpCall("reveal-in-finder", { path: folder.path });
              }}
              className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-2 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              <FolderOpen className="size-3.5" aria-hidden="true" />
              <span>Reveal</span>
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-[var(--text-secondary)]">
            <span>{folder.counts.new_files} new</span>
            <span>{folder.counts.document_candidates} docs</span>
            <span>{folder.counts.trash_candidates} trash</span>
            <span>{folder.counts.failed} failed</span>
          </div>
          <div className="mt-3 grid gap-1 text-xs text-[var(--text-muted)] sm:grid-cols-2">
            <span>Last scan: {formatInboxDate(folder.last_scan_at)}</span>
            <span>Last action: {formatRunStatus(folder.last_run_status)}</span>
          </div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            {folder.name} impact: {impactParts.join("; ")}.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:min-w-[340px]">
          <ActionButton label={`Scan ${folder.name}`} busy={activeAction === "scan"} disabled={disabled} onClick={() => onAction("scan")}>
            <ScanLine className="size-4" aria-hidden="true" />
            <span>Scan</span>
          </ActionButton>
          <ActionButton label={`Consume ${folder.name}`} busy={activeAction === "consume"} disabled={disabled} onClick={() => onAction("consume")}>
            <Play className="size-4" aria-hidden="true" />
            <span>Consume</span>
          </ActionButton>
          <ActionButton label={`Purge ${folder.name} to trash`} busy={activeAction === "purge"} disabled={disabled} onClick={() => onAction("purge")}>
            <Trash2 className="size-4" aria-hidden="true" />
            <span>Purge to Trash</span>
          </ActionButton>
        </div>
      </div>
    </article>
  );
}

export function EmailSourceRow({
  source,
  activeAction,
  onAction,
}: {
  source: EmailSource;
  activeAction: EmailAction | null;
  onAction: (action: EmailAction) => void;
}) {
  const disabled = !source.enabled || activeAction !== null;
  const supportedFormats = source.formats.slice(0, 6).join(", ");
  const latestRun = source.latest_run;

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">{source.name}</h2>
            <span className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
              {source.enabled ? "Mail Drop" : "Paused"}
            </span>
            {source.health_state && (
              <span className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
                {source.health_state}
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-sm text-[var(--text-muted)]" title={source.path}>
            {source.path}
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-[var(--text-secondary)]">
            <span>{pluralize(source.counts.pending_files, "pending file")}</span>
            <span>{pluralize(source.counts.contained_messages, "email packet")}</span>
            <span>{pluralize(source.counts.archives, "archive")}</span>
            <span>{pluralize(source.counts.degraded, "degraded export")}</span>
            <span className="inline-flex items-center gap-1">
              <Paperclip className="size-3" aria-hidden="true" />
              {pluralize(source.counts.attachments, "attachment")}
            </span>
            <span className="inline-flex items-center gap-1">
              <Link2 className="size-3" aria-hidden="true" />
              {pluralize(source.counts.article_links, "article link")}
            </span>
            <span>{pluralize(source.counts.failed, "failed item")}</span>
          </div>
          <div className="mt-3 grid gap-1 text-xs text-[var(--text-muted)] sm:grid-cols-2">
            <span>Last scan: {formatInboxDate(source.last_scan_at)}</span>
            <span>Batch: {pluralize(source.batch_limit, "file")} per consume</span>
            <span>Last consume: {formatRunStatus(source.last_run_status)}</span>
            <span title={source.formats.join(", ")}>Formats: {supportedFormats}</span>
          </div>
          {latestRun && (
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              Last run: {pluralize(latestRun.packets_created ?? 0, "packet")},{" "}
              {pluralize(latestRun.links_seen ?? 0, "link")},{" "}
              {pluralize(latestRun.attachments_seen ?? 0, "attachment")},{" "}
              {pluralize(latestRun.files_moved ?? 0, "file")} moved.
            </p>
          )}
          {source.health_error && (
            <p className="mt-2 text-xs text-[var(--accent-danger)]">{source.health_error}</p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 xl:min-w-[420px]">
          <ActionButton label={`Scan ${source.name}`} busy={activeAction === "scan"} disabled={disabled} onClick={() => onAction("scan")}>
            <ScanLine className="size-4" aria-hidden="true" />
            <span>Scan</span>
          </ActionButton>
          <ActionButton label={`Consume ${source.name}`} busy={activeAction === "consume"} disabled={disabled} onClick={() => onAction("consume")}>
            <Play className="size-4" aria-hidden="true" />
            <span>Consume</span>
          </ActionButton>
          <ActionButton
            label={`Prepare wiki update for ${source.name}`}
            busy={activeAction === "wiki"}
            disabled={disabled}
            onClick={() => onAction("wiki")}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            <span>Wiki Update</span>
          </ActionButton>
        </div>
      </div>
    </article>
  );
}

export function LatestRunList({ runs }: { runs: InboxRun[] }) {
  if (runs.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <FileCheck2 className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Latest runs</h2>
      </div>
      <div className="space-y-3">
        {runs.slice(0, 3).map((run) => (
          <article key={run.id} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold text-[var(--text-primary)]">{run.id}</h3>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
                  <span>{run.status}</span>
                  {run.airplane_mode && <span>Airplane mode</span>}
                  <span>cloud: {run.cloud_calls ?? 0}</span>
                  <span>local: {run.local_agent_calls ?? 0}</span>
                  <span>review: {run.files_needing_review ?? 0}</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-right text-xs text-[var(--text-secondary)] sm:grid-cols-3">
                <span>{run.files_seen ?? 0} seen</span>
                <span>{run.files_moved ?? 0} moved</span>
                <span>{run.files_indexed ?? 0} indexed</span>
              </div>
            </div>
            {run.file_results && run.file_results.length > 0 && (
              <div className="mt-3 space-y-2">
                {run.file_results.map((file) => {
                  const fileName = file.renamed_to || baseName(file.final_path || file.source_path);
                  const extractedName = file.extracted_path ? baseName(file.extracted_path) : null;
                  const cloudEvidence = [file.cloud_provider, file.cloud_model].filter(Boolean).join(" / ");
                  return (
                    <div
                      key={`${file.source_path}-${file.status}`}
                      className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2"
                    >
                      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-[var(--text-primary)]" title={fileName}>
                            {fileName}
                          </div>
                          <div className="mt-1 truncate text-xs text-[var(--text-muted)]" title={file.source_path}>
                            {baseName(file.source_path)}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-[var(--text-secondary)] md:justify-end">
                          <span>{file.extraction_method}</span>
                          <span>{file.hardware_backend}</span>
                          <span>{file.confidence}</span>
                          <span>cloud: {file.cloud_used ? "yes" : "no"}</span>
                          {extractedName && (
                            <span className="max-w-full truncate" title={file.extracted_path ?? undefined}>
                              {extractedName}
                            </span>
                          )}
                          {file.escalation_reason && (
                            <span className="max-w-full truncate" title={file.escalation_reason}>
                              {file.escalation_reason}
                            </span>
                          )}
                          {cloudEvidence && <span>{cloudEvidence}</span>}
                          <span>{file.status}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
