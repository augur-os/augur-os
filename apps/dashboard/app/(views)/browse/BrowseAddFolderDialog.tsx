"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";

type BrowseAddFolderDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onScan: (path: string) => Promise<any>;
  onInitialize: (path: string) => Promise<any>;
};

type ScanSummary = {
  project_root?: string;
  artifactCount: number;
  warningCount: number;
  metadataWritten: boolean | null;
  raw: any;
};

export function BrowseAddFolderDialog({
  open,
  onOpenChange,
  onScan,
  onInitialize,
}: BrowseAddFolderDialogProps) {
  const [path, setPath] = useState("");
  const [scanResult, setScanResult] = useState<ScanSummary | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [initializeError, setInitializeError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"scan" | "initialize" | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const pathInputRef = useRef<HTMLInputElement>(null);
  const requestVersionRef = useRef(0);
  const trimmedPath = path.trim();
  const canScan = trimmedPath.length > 0 && busy === null;
  const metadataStatus = useMemo(() => metadataWriteStatus(scanResult), [scanResult]);

  useEffect(() => {
    if (!open) {
      requestVersionRef.current += 1;
      resetDialogState({
        setPath,
        setScanResult,
        setScanError,
        setInitializeError,
        setBusy,
      });
      return;
    }
    window.requestAnimationFrame(() => pathInputRef.current?.focus());
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onOpenChange(false);
        return;
      }
      if (event.key === "Tab") {
        trapDialogFocus(event, dialogRef.current);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onOpenChange, open]);

  if (!open) return null;

  const handleScan = async () => {
    if (!trimmedPath || busy) return;
    setBusy("scan");
    setScanError(null);
    setInitializeError(null);
    setScanResult(null);
    const requestVersion = requestVersionRef.current + 1;
    requestVersionRef.current = requestVersion;
    try {
      const result = await onScan(trimmedPath);
      if (requestVersionRef.current !== requestVersion) return;
      if (result && typeof result === "object" && result.success === false) {
        throw new Error(readString(result.error) || "Folder scan failed.");
      }
      setScanResult(normalizeScanResult(result));
    } catch (error) {
      if (requestVersionRef.current !== requestVersion) return;
      setScanError(error instanceof Error ? error.message : "Folder scan failed.");
    } finally {
      if (requestVersionRef.current === requestVersion) setBusy(null);
    }
  };

  const handleInitialize = async () => {
    if (!scanResult || busy) return;
    setBusy("initialize");
    setInitializeError(null);
    const requestVersion = requestVersionRef.current + 1;
    requestVersionRef.current = requestVersion;
    try {
      const result = await onInitialize(scanResult.project_root || trimmedPath);
      if (requestVersionRef.current !== requestVersion) return;
      if (result && typeof result === "object" && result.success === false) {
        throw new Error(readString(result.error) || "Folder initialization failed.");
      }
      onOpenChange(false);
    } catch (error) {
      if (requestVersionRef.current !== requestVersion) return;
      setInitializeError(error instanceof Error ? error.message : "Folder initialization failed.");
    } finally {
      if (requestVersionRef.current === requestVersion) setBusy(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Add folder"
        className="w-full max-w-lg overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] shadow-2xl shadow-black/25"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-color)] px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Add folder</h2>
            <p className="mt-0.5 text-xs text-[var(--text-muted)]">
              Scan first, then initialize after review.
            </p>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={() => onOpenChange(false)}
            className="inline-flex size-8 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-4 px-4 py-4">
          <label className="block text-xs font-semibold text-[var(--text-secondary)]">
            Folder path
            <input
              ref={pathInputRef}
              type="text"
              value={path}
              disabled={busy === "initialize"}
              onChange={(event) => {
                requestVersionRef.current += 1;
                setPath(event.target.value);
                setScanResult(null);
                setScanError(null);
                setInitializeError(null);
                if (busy === "scan") setBusy(null);
              }}
              className="mt-1.5 h-10 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm text-[var(--text-primary)] outline-none transition-colors placeholder:text-[var(--text-muted)] focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]/20 disabled:cursor-not-allowed disabled:opacity-60"
              placeholder="/Users/name/Projects/example"
            />
          </label>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              disabled={!canScan}
              onClick={handleScan}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy === "scan" && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              Scan folder
            </button>
            {scanResult && (
              <span className="text-xs text-[var(--text-muted)]">
                Review complete. Initialization is approval-gated.
              </span>
            )}
          </div>

          {scanError && (
            <p className="rounded-md border border-[var(--accent-danger)]/40 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--accent-danger)]">
              {scanError}
            </p>
          )}

          {scanResult && (
            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
              <dl className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-3">
                <div>
                  <dt className="text-[var(--text-muted)]">Artifacts</dt>
                  <dd className="mt-0.5 font-semibold text-[var(--text-primary)]">
                    {scanResult.artifactCount.toLocaleString()} {pluralize("artifact", scanResult.artifactCount)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[var(--text-muted)]">Warnings</dt>
                  <dd className="mt-0.5 font-semibold text-[var(--text-primary)]">
                    {scanResult.warningCount.toLocaleString()} {pluralize("warning", scanResult.warningCount)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[var(--text-muted)]">Metadata write</dt>
                  <dd className="mt-0.5 font-semibold text-[var(--text-primary)]">{metadataStatus}</dd>
                </div>
              </dl>
              {scanResult.project_root && (
                <p className="mt-3 truncate border-t border-[var(--border-color)] pt-2 text-xs text-[var(--text-muted)]">
                  Project root: <span className="text-[var(--text-secondary)]">{scanResult.project_root}</span>
                </p>
              )}
            </div>
          )}

          {initializeError && (
            <p className="rounded-md border border-[var(--accent-danger)]/40 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--accent-danger)]">
              {initializeError}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--border-color)] px-4 py-3">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="inline-flex h-9 items-center rounded-md px-3 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          >
            Cancel
          </button>
          {scanResult && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={handleInitialize}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-[var(--accent-primary)] px-3 text-sm font-semibold text-white transition-colors hover:bg-[var(--accent-primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy === "initialize" && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              Initialize folder
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function normalizeScanResult(result: any): ScanSummary {
  const artifacts = Array.isArray(result?.artifacts) ? result.artifacts : null;
  const warnings = Array.isArray(result?.warnings) ? result.warnings : null;
  return {
    project_root: readString(result?.project_root),
    artifactCount: readNumber(
      result?.inventory_count
        ?? result?.artifact_count
        ?? result?.artifacts_count
        ?? result?.artifactCount,
    ) ?? artifacts?.length ?? 0,
    warningCount: readNumber(
      result?.inventory_warning_count
        ?? result?.warning_count
        ?? result?.warnings_count
        ?? result?.warningCount,
    ) ?? warnings?.length ?? 0,
    metadataWritten: readBoolean(
      result?.writes_metadata
        ?? result?.metadata_written
        ?? result?.metadataWrite
        ?? result?.metadata_write,
    ),
    raw: result,
  };
}

function metadataWriteStatus(scanResult: ScanSummary | null): string {
  if (!scanResult) return "";
  if (scanResult.metadataWritten === true) return "Written";
  if (scanResult.metadataWritten === false) return "Not written";
  return "Not reported";
}

function pluralize(label: string, count: number): string {
  return count === 1 ? label : `${label}s`;
}

function readNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function readBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    if (value.toLowerCase() === "true") return true;
    if (value.toLowerCase() === "false") return false;
  }
  return null;
}

function readString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function resetDialogState({
  setPath,
  setScanResult,
  setScanError,
  setInitializeError,
  setBusy,
}: {
  setPath: (value: string) => void;
  setScanResult: (value: ScanSummary | null) => void;
  setScanError: (value: string | null) => void;
  setInitializeError: (value: string | null) => void;
  setBusy: (value: "scan" | "initialize" | null) => void;
}) {
  setPath("");
  setScanResult(null);
  setScanError(null);
  setInitializeError(null);
  setBusy(null);
}

function trapDialogFocus(event: KeyboardEvent, container: HTMLElement | null) {
  if (!container) return;
  const focusable = Array.from(
    container.querySelectorAll<HTMLElement>(
      [
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "a[href]",
        "[tabindex]:not([tabindex='-1'])",
      ].join(","),
    ),
  );
  if (focusable.length === 0) return;

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;
  if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
    return;
  }
  if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}
