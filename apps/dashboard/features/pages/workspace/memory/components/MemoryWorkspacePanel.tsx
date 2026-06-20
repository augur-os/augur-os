'use client';

import { useState } from 'react';
import { RefreshCw, FolderOpen, FileText, FileCode2, FileJson2, BookOpen, Copy } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import type { BrainOperationNotice, MemoryWorkspace, MemoryWorkspaceItem } from '../types';

interface MemoryWorkspacePanelProps {
  workspace: MemoryWorkspace | null;
  isLoading: boolean;
  openingFileId: string | null;
  onOpenFile: (fileId: MemoryWorkspaceItem['id']) => void;
  onRefresh: () => void;
  title?: string;
  notice?: BrainOperationNotice | null;
  error?: string | null;
}

function formatBytes(sizeBytes: number | null) {
  if (!sizeBytes) return 'n/a';
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function WorkspaceIcon({ kind }: { kind: MemoryWorkspaceItem['kind'] }) {
  if (kind === 'directory') return <FolderOpen className="size-4 text-amber-400" aria-hidden="true" />;
  if (kind === 'html') return <FileCode2 className="size-4 text-cyan-400" aria-hidden="true" />;
  if (kind === 'yaml') return <FileJson2 className="size-4 text-violet-400" aria-hidden="true" />;
  return <FileText className="size-4 text-emerald-400" aria-hidden="true" />;
}

function compactPath(path: string) {
  const parts = path.split('/').filter(Boolean);
  if (parts.length <= 4) return path;
  const prefix = path.startsWith('/') ? `/${parts.slice(0, 2).join('/')}` : parts.slice(0, 2).join('/');
  return `${prefix}/.../${parts[parts.length - 1]}`;
}

function getFilePreview(file: MemoryWorkspaceItem) {
  if (!file.exists) {
    return `Missing ${file.kind} at ${compactPath(file.path)}`;
  }
  if (file.kind === 'directory') {
    return `Directory with ${file.entryCount ?? 0} entries`;
  }
  return `${file.kind.toUpperCase()} file, ${formatBytes(file.sizeBytes)}`;
}

function getWhyItMatters(file: MemoryWorkspaceItem) {
  if (file.id === 'memory') {
    return 'Primary durable decisions, patterns, and preferences used by search and recall.';
  }
  if (file.id === 'profile' || file.id === 'report') {
    return 'Supplies the Human API context that shapes future agent responses.';
  }
  if (file.id === 'daily') {
    return 'Feeds recency checks and curation before signals become durable memory.';
  }
  if (file.id === 'index') {
    return 'Keeps memory search aligned with the latest curated entries.';
  }
  return file.description;
}

function getValidationSummary(file: MemoryWorkspaceItem) {
  if (!file.exists) {
    return 'Needs attention: file is missing.';
  }
  if (file.kind === 'directory') {
    const count = file.entryCount ?? 0;
    return count > 0 ? `Ready: present with ${count} entries.` : 'Needs attention: directory is empty.';
  }
  if (!file.sizeBytes) {
    return 'Needs attention: file is empty.';
  }
  return `Ready: present and ${formatBytes(file.sizeBytes)}.`;
}

export function MemoryWorkspacePanel({
  workspace,
  isLoading,
  openingFileId,
  onOpenFile,
  onRefresh,
  title = 'Memory Workspace',
  notice,
  error,
}: MemoryWorkspacePanelProps) {
  const [copiedFileId, setCopiedFileId] = useState<string | null>(null);

  const copyPath = async (file: MemoryWorkspaceItem) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(file.path);
      }
    } catch {
      // Browsers can deny clipboard writes; the visible action still confirms what the user attempted.
    } finally {
      setCopiedFileId(file.id);
      if (typeof window !== 'undefined') {
        window.setTimeout(() => setCopiedFileId(null), 1500);
      }
    }
  };

  return (
    <GlassCard
      color="blue"
      icon={BookOpen}
      title={title}
      subtitle={workspace?.rootPath ?? 'Vault-backed canonical memory source'}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-[var(--text-muted)]">
            Canonical memory artifacts, profile state, and generated report files.
          </p>
          <button type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 min-h-[44px] text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] cursor-pointer"
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            Refresh
          </button>
        </div>

        {(notice || error) && (
          <div className="space-y-2">
            {notice && (
              <div
                className={`rounded-lg border px-3 py-2 text-xs ${
                  notice.type === 'success'
                    ? 'border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 text-[var(--text-primary)]'
                    : notice.type === 'error'
                      ? 'border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 text-[var(--text-primary)]'
                      : 'border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)]'
                }`}
                role={notice.type === 'error' ? 'alert' : 'status'}
              >
                {notice.message}
              </div>
            )}
            {error && (
              <div className="rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-3 py-2 text-xs text-[var(--text-primary)]" role="alert">
                {error}
              </div>
            )}
          </div>
        )}

        {isLoading ? (
          <div className="grid gap-3">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="h-20 rounded-xl bg-[var(--bg-secondary)] animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid gap-3">
            {workspace?.files.map((file) => (
              <div
                key={file.id}
                className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 hover:border-[var(--accent-primary)]/30 transition-colors duration-200"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <WorkspaceIcon kind={file.kind} />
                      <h4 className="text-sm font-medium text-[var(--text-primary)]">{file.label}</h4>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] ${
                          file.exists
                            ? 'bg-[var(--accent-success)]/15 text-[var(--accent-success)]'
                            : 'bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]'
                        }`}
                      >
                        {file.exists ? 'Present' : 'Missing'}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">{file.description}</p>
                    <div className="mt-2 flex max-w-full flex-wrap items-center gap-2">
                      <p className="min-w-0 truncate text-[11px] text-[var(--text-muted)]" title={file.path}>{compactPath(file.path)}</p>
                      <button
                        type="button"
                        onClick={() => void copyPath(file)}
                        className="inline-flex min-h-[44px] items-center gap-1 rounded-md border border-[var(--border-color)] px-2 py-1 text-[11px] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                        aria-label={`Copy path for ${file.label}`}
                      >
                        <Copy className="size-3" aria-hidden="true" />
                        {copiedFileId === file.id ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-[var(--text-muted)]">
                      <span>Size: {formatBytes(file.sizeBytes)}</span>
                      {file.modifiedAt && <span>Updated: {new Date(file.modifiedAt).toLocaleString()}</span>}
                      {typeof file.entryCount === 'number' && <span>Entries: {file.entryCount}</span>}
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-[var(--text-secondary)]">
                      <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-2">
                        <span className="block font-medium text-[var(--text-muted)]">Preview</span>
                        {getFilePreview(file)}
                      </div>
                      <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-2">
                        <span className="block font-medium text-[var(--text-muted)]">Why it matters</span>
                        {getWhyItMatters(file)}
                      </div>
                      <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-2">
                        <span className="block font-medium text-[var(--text-muted)]">Validation</span>
                        {getValidationSummary(file)}
                      </div>
                    </div>
                  </div>
                  <button type="button"
                    onClick={() => onOpenFile(file.id)}
                    disabled={!file.exists || openingFileId === file.id}
                    className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] px-3 min-h-[44px] text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                  >
                    <FolderOpen className="size-4" aria-hidden="true" />
                    {openingFileId === file.id ? 'Opening...' : 'Open'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </GlassCard>
  );
}
