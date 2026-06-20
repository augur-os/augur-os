'use client';

import { useCallback, useEffect, useState } from 'react';
import { FileCode2, ExternalLink, RefreshCw, Sparkles } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { useActionRunner, type ActionDef } from '@/hooks/useActionRunner';
import { mcpCall } from '@/lib/mcp/client';
import type { MemoryReport } from '../types';

interface HumanReportPreviewProps {
  report: MemoryReport | null;
  isLoading: boolean;
  onOpenReport: () => void;
  onRefresh: () => void;
  regenerateAction: ActionDef | null;
}

function formatBytes(sizeBytes: number | null) {
  if (!sizeBytes) return 'n/a';
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function HumanReportPreview({
  report,
  isLoading,
  onOpenReport,
  onRefresh,
  regenerateAction,
}: HumanReportPreviewProps) {
  const { runAction, isExecuting, result, lastActionId } = useActionRunner();
  const [previewHtml, setPreviewHtml] = useState<string | null>(report?.html ?? null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const actionResult = lastActionId === regenerateAction?.id ? result : null;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPreviewHtml(report?.html ?? null);
      setPreviewError(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [report?.html, report?.modifiedAt]);

  const loadPreview = useCallback(async () => {
    if (!report?.exists || isPreviewLoading) {
      return;
    }

    setIsPreviewLoading(true);
    setPreviewError(null);
    try {
      const data = await mcpCall<{ report?: { html?: string }; error?: string }>('knowledge-memory-read', { includeHtml: 1 });

      const rawHtml = data.report?.html;
      if (!rawHtml) {
        throw new Error('Report preview is empty');
      }

      const { default: DOMPurify } = await import('dompurify');
      const sanitized = DOMPurify.sanitize(rawHtml, {
        USE_PROFILES: { html: true },
        FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'link'],
      });
      setPreviewHtml(sanitized);
    } catch (error) {
      console.error('Failed to load report preview:', error);
      setPreviewError('Preview failed to load. Open the file directly or refresh metadata.');
    } finally {
      setIsPreviewLoading(false);
    }
  }, [isPreviewLoading, report?.exists]);

  const regenerateReport = useCallback(async () => {
    if (!regenerateAction) return;
    const ok = await runAction(regenerateAction);
    if (ok) {
      onRefresh();
    }
  }, [onRefresh, regenerateAction, runAction]);

  return (
    <GlassCard
      color="cyan"
      icon={FileCode2}
      title="Human Report"
      subtitle="Preview and regenerate the vault-backed memory report"
    >
      <div className="space-y-4">
        {actionResult && (
          <div className="space-y-2">
            <div
              className={`rounded-lg border px-3 py-2 text-xs ${
                actionResult.type === 'success'
                  ? 'border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 text-[var(--text-primary)]'
                  : 'border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 text-[var(--text-primary)]'
              }`}
              role={actionResult.type === 'error' ? 'alert' : 'status'}
            >
              {regenerateAction?.label || 'Action'}: {actionResult.message}
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-[var(--text-muted)]">
            {report?.exists ? (
              <>
                <div>{report.title || 'Claude Code Insights'}</div>
                <div className="mt-1 text-xs">
                  {report.modifiedAt ? `Updated ${new Date(report.modifiedAt).toLocaleString()}` : 'No timestamp'} · {formatBytes(report.sizeBytes)}
                </div>
              </>
            ) : (
              <div>No report has been generated yet.</div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button"
              onClick={onRefresh}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] px-3 min-h-[44px] text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] cursor-pointer"
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              Refresh
            </button>
            <button type="button"
              onClick={onOpenReport}
              disabled={!report?.exists}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] px-3 min-h-[44px] text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              <ExternalLink className="size-4" aria-hidden="true" />
              Open File
            </button>
            {regenerateAction && (
              <button type="button"
                onClick={regenerateReport}
                disabled={isExecuting}
                className="inline-flex items-center gap-2 rounded-lg border border-[var(--accent-info)]/30 bg-[var(--accent-info)]/15 px-3 min-h-[44px] text-sm text-[var(--accent-info)] transition-colors hover:bg-[var(--accent-info)]/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
              >
                {isExecuting && lastActionId === regenerateAction.id ? (
                  <RefreshCw className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Sparkles className="size-4" aria-hidden="true" />
                )}
                {isExecuting && lastActionId === regenerateAction.id ? 'Launching...' : regenerateAction.label}
              </button>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="h-[520px] rounded-xl bg-[var(--bg-secondary)] animate-pulse" />
        ) : report?.exists && previewHtml ? (
          <iframe
            title="Human memory report preview"
            sandbox=""
            srcDoc={previewHtml}
            className="h-[520px] w-full rounded-xl border border-[var(--border-color)] bg-white"
          />
        ) : report?.exists ? (
          <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] px-6 py-10 text-center">
            <FileCode2 className="mx-auto mb-3 size-10 text-[var(--accent-info)] opacity-70" aria-hidden="true" />
            <p className="text-sm text-[var(--text-primary)]">Preview stays deferred until you ask for it.</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              This keeps the initial page load light even when `report.html` is large.
            </p>
            {previewError && (
              <p className="mt-3 text-xs text-[var(--accent-danger)]">{previewError}</p>
            )}
            <button type="button"
              onClick={loadPreview}
              disabled={isPreviewLoading}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-[var(--accent-info)]/30 bg-[var(--accent-info)]/15 px-4 min-h-[44px] text-sm text-[var(--accent-info)] transition-colors hover:bg-[var(--accent-info)]/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`h-4 w-4 ${isPreviewLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
              {isPreviewLoading ? 'Loading Preview...' : 'Load Preview'}
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] px-6 py-10 text-center">
            <FileCode2 className="mx-auto mb-3 size-10 text-[var(--text-muted)] opacity-50" aria-hidden="true" />
            <p className="text-sm text-[var(--text-secondary)]">Generate a fresh HTML report to preview it here.</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">The report stays in the memory vault and is rendered in-place via a sandboxed preview.</p>
          </div>
        )}
      </div>
    </GlassCard>
  );
}
