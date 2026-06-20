'use client';

import { useState } from 'react';
import { AlertCircle, BookOpenText, Link2, RefreshCw, Sparkles, TriangleAlert } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { mcpCall } from '@/lib/mcp/client';
import type { WikiMaintenanceSummary, WikiRewriteCandidate } from '../types';

interface WikiMaintenancePanelProps {
  summary: WikiMaintenanceSummary | null;
  candidates: WikiRewriteCandidate[];
  totalCandidates: number;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
}

function formatReason(reason: string): string {
  return reason.replace(/_/g, ' ');
}

export function WikiMaintenancePanel({
  summary,
  candidates,
  totalCandidates,
  isLoading,
  error,
  onRefresh,
}: WikiMaintenancePanelProps) {
  const [isWikiUpdating, setIsWikiUpdating] = useState(false);
  const [wikiUpdateResult, setWikiUpdateResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const statItems = [
    {
      label: 'Avg Quality',
      value: `${Math.round(summary?.avgQualityScore ?? 0)}`,
      suffix: '/100',
      icon: Sparkles,
      iconColor: 'text-emerald-300',
      gradient: 'from-emerald-500/10 to-teal-500/10',
      border: 'border-emerald-500/20',
      helper: 'Current synthesized page quality across the wiki',
    },
    {
      label: 'Rewrite Queue',
      value: totalCandidates.toLocaleString(),
      suffix: '',
      icon: TriangleAlert,
      iconColor: totalCandidates > 0 ? 'text-amber-300' : 'text-emerald-300',
      gradient: totalCandidates > 0 ? 'from-amber-500/10 to-orange-500/10' : 'from-emerald-500/10 to-cyan-500/10',
      border: totalCandidates > 0 ? 'border-amber-500/20' : 'border-emerald-500/20',
      helper: 'Pages currently flagged for editorial rewrite',
    },
    {
      label: 'Avg Links/Page',
      value: (summary?.avgOutgoingLinksPerPage ?? 0).toFixed(1),
      suffix: '',
      icon: Link2,
      iconColor: 'text-cyan-300',
      gradient: 'from-cyan-500/10 to-blue-500/10',
      border: 'border-cyan-500/20',
      helper: 'Outgoing wiki cross-links per page',
    },
    {
      label: 'Isolated Pages',
      value: (summary?.isolatedPages ?? 0).toLocaleString(),
      suffix: '',
      icon: BookOpenText,
      iconColor: (summary?.isolatedPages ?? 0) > 0 ? 'text-rose-300' : 'text-emerald-300',
      gradient: (summary?.isolatedPages ?? 0) > 0 ? 'from-rose-500/10 to-red-500/10' : 'from-emerald-500/10 to-lime-500/10',
      border: (summary?.isolatedPages ?? 0) > 0 ? 'border-rose-500/20' : 'border-emerald-500/20',
      helper: 'Pages without inbound graph connections',
    },
  ];

  const handleUpdateWiki = async () => {
    setIsWikiUpdating(true);
    setWikiUpdateResult(null);
    try {
      const result = await mcpCall<{ success?: boolean; message?: string; error?: string }>('wiki-update', { limit: 20 });
      if (result?.success === false) {
        throw new Error(result.error || result.message || 'wiki-update failed');
      }
      setWikiUpdateResult({
        type: 'success',
        message: result.message || 'Wiki update batch prepared. Agent synthesis and apply still need to run.',
      });
      onRefresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setWikiUpdateResult({ type: 'error', message });
    } finally {
      setIsWikiUpdating(false);
    }
  };

  return (
    <GlassCard color="cyan" icon={BookOpenText} title="Wiki Maintenance">
      <div className="space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-[var(--text-secondary)]">
              Live wiki quality and editorial debt from the maintenance loop.
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              This uses the same rewrite-candidate queue the nightly autoloop sees.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button type="button"
              onClick={onRefresh}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] px-3 min-h-[44px] text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer shrink-0"
              disabled={isLoading}
            >
              <RefreshCw className={`size-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
              Refresh
            </button>
            <button type="button"
              onClick={handleUpdateWiki}
              disabled={isLoading || isWikiUpdating}
              className="inline-flex items-center gap-2 rounded-lg border border-cyan-500/25 bg-cyan-500/10 px-3 min-h-[44px] text-sm text-cyan-300 transition-colors hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer shrink-0"
            >
              {isWikiUpdating ? (
                <RefreshCw className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Sparkles className="size-4" aria-hidden="true" />
              )}
              {isWikiUpdating ? 'Preparing...' : 'Update Wiki'}
            </button>
          </div>
        </div>

        {wikiUpdateResult && (
          <div
            className={`rounded-xl border px-4 py-3 text-sm ${
              wikiUpdateResult.type === 'success'
                ? 'border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 text-[var(--text-primary)]'
                : 'border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 text-[var(--text-primary)]'
            }`}
            role={wikiUpdateResult.type === 'error' ? 'alert' : 'status'}
          >
            {wikiUpdateResult.type === 'success' ? 'Wiki update status: ' : 'Wiki update failed: '}
            {wikiUpdateResult.message}
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 size-4 text-[var(--accent-danger)] shrink-0" aria-hidden="true" />
              <div>
                <p className="text-sm text-[var(--text-primary)]">{error}</p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  Wiki health data could not be loaded from MCP.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {statItems.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.label} className={`rounded-xl border ${item.border} bg-gradient-to-br ${item.gradient} p-4`}>
                <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                  <Icon className={`size-4 ${item.iconColor}`} aria-hidden="true" />
                  <span>{item.label}</span>
                </div>
                {isLoading ? (
                  <div className="mt-2 h-8 w-20 rounded bg-[var(--bg-secondary)] animate-pulse" />
                ) : (
                  <div className="mt-2 text-2xl font-bold text-[var(--text-primary)]">
                    {item.value}
                    {item.suffix && <span className="ml-1 text-base text-[var(--text-muted)]">{item.suffix}</span>}
                  </div>
                )}
                <p className="mt-2 text-xs text-[var(--text-muted)]">{item.helper}</p>
              </div>
            );
          })}
        </div>

        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-medium text-[var(--text-primary)]">Top Rewrite Candidates</h3>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                Highest-priority pages currently flagged by wiki-quality heuristics.
              </p>
            </div>
            {!isLoading && totalCandidates > candidates.length && (
              <span className="text-xs text-[var(--text-muted)]">Showing {candidates.length} of {totalCandidates}</span>
            )}
          </div>

          <div className="mt-4 space-y-3">
            {isLoading ? (
              Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4 animate-pulse">
                  <div className="h-4 w-48 rounded bg-[var(--bg-hover)]" />
                  <div className="mt-3 h-3 w-full rounded bg-[var(--bg-hover)]" />
                </div>
              ))
            ) : candidates.length === 0 ? (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-5 text-sm text-[var(--text-secondary)]">
                No rewrite candidates are currently flagged. The wiki is clean under the current quality thresholds.
              </div>
            ) : (
              candidates.map((candidate) => (
                <div key={candidate.page} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-sm font-medium text-[var(--text-primary)]">{candidate.title}</h4>
                        <span className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-[11px] text-[var(--text-muted)]">
                          {candidate.page}
                        </span>
                        {candidate.hub && (
                          <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[11px] text-cyan-300">
                            {candidate.hub}
                          </span>
                        )}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {candidate.reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-300"
                          >
                            {formatReason(reason)}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="shrink-0 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-right">
                      <div className="text-[11px] uppercase tracking-wide text-[var(--text-muted)]">Quality</div>
                      <div className="text-lg font-bold text-[var(--text-primary)]">{candidate.quality_score}/100</div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
