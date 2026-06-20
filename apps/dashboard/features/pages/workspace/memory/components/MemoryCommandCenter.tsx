'use client';

import Link from 'next/link';
import { AlertTriangle, CheckCircle2, ClipboardList, Gauge, RefreshCw } from 'lucide-react';
import type { BrainDataSources, MemoryStats, MemoryWorkspace, WikiMaintenanceSummary } from '../types';

interface MemoryCommandCenterProps {
  stats: MemoryStats | null;
  sources: BrainDataSources | undefined;
  workspace: MemoryWorkspace | null;
  wikiSummary: WikiMaintenanceSummary | null | undefined;
  sourceLabel: string;
  freshnessLabel: string;
  isCurating: boolean;
  onCurate: () => void;
}

function totalSignals(stats: MemoryStats | null) {
  return (stats?.totalDecisions ?? 0) + (stats?.totalPatterns ?? 0) + (stats?.totalPreferences ?? 0);
}

function buildAttentionItems({
  stats,
  sources,
  workspace,
  wikiSummary,
}: Pick<MemoryCommandCenterProps, 'stats' | 'sources' | 'workspace' | 'wikiSummary'>) {
  const items: string[] = [];
  const memoryFreshness = sources?.memory?.freshness?.trim().toLowerCase();
  const missingFiles = workspace?.files.filter((file) => !file.exists) ?? [];

  if (memoryFreshness && memoryFreshness !== 'fresh') {
    items.push(`Memory source is marked ${memoryFreshness}; curate after checking recent daily logs.`);
  }
  if (!stats?.lastCurated) {
    items.push('No curation timestamp is available, so freshness cannot be trusted.');
  }
  if (missingFiles.length > 0) {
    items.push(`${missingFiles.length} canonical workspace file${missingFiles.length === 1 ? '' : 's'} need attention.`);
  }
  if ((wikiSummary?.rewriteCandidates ?? 0) > 0) {
    items.push(`${wikiSummary?.rewriteCandidates} wiki rewrite candidate${wikiSummary?.rewriteCandidates === 1 ? '' : 's'} may need compounding.`);
  }

  return items.length ? items : ['No blocking memory issues from the loaded dashboard data.'];
}

function buildHealthLabel(stats: MemoryStats | null, workspace: MemoryWorkspace | null) {
  const signalCount = totalSignals(stats);
  const presentFiles = workspace?.files.filter((file) => file.exists).length ?? 0;
  const totalFiles = workspace?.files.length ?? 0;
  const fileLabel = totalFiles > 0 ? `${presentFiles}/${totalFiles} canonical files present` : 'Workspace file inventory unavailable';

  return `${signalCount} curated signals; ${fileLabel}.`;
}

export function MemoryCommandCenter({
  stats,
  sources,
  workspace,
  wikiSummary,
  sourceLabel,
  freshnessLabel,
  isCurating,
  onCurate,
}: MemoryCommandCenterProps) {
  const attentionItems = buildAttentionItems({ stats, sources, workspace, wikiSummary });
  const signalCount = totalSignals(stats);
  const topCategory = Object.entries(stats?.categoryCounts ?? {}).reduce<
    [string, number] | null
  >((top, entry) => (top === null || entry[1] > top[1] ? entry : top), null);

  return (
    <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Gauge className="size-4 text-emerald-400" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Command center</h3>
          </div>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {sourceLabel} · {freshnessLabel}
          </p>
        </div>
        <button
          type="button"
          onClick={onCurate}
          disabled={isCurating}
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`size-4 ${isCurating ? 'animate-spin' : ''}`} aria-hidden="true" />
          Curate latest seven days
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
          <div className="mb-2 flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-400" aria-hidden="true" />
            <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)]">Needs attention</h4>
          </div>
          <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
            {attentionItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
          <div className="mb-2 flex items-center gap-2">
            <ClipboardList className="size-4 text-cyan-400" aria-hidden="true" />
            <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)]">Next best actions</h4>
          </div>
          <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
            <li>Curate the latest seven days to fold fresh session signals into durable memory.</li>
            <li>{topCategory ? `Review the ${topCategory[0]} theme with ${topCategory[1]} tracked signals.` : 'Search for a current project and save durable decisions.'}</li>
            <li>
              <Link href="/browse?view=documents" className="text-[var(--accent-primary)] underline-offset-2 hover:underline">
                Browse Documents
              </Link>
            </li>
          </ul>
        </div>

        <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
          <div className="mb-2 flex items-center gap-2">
            <CheckCircle2 className="size-4 text-emerald-400" aria-hidden="true" />
            <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)]">Memory health</h4>
          </div>
          <p className="text-sm text-[var(--text-secondary)]">{buildHealthLabel(stats, workspace)}</p>
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            {signalCount > 0 ? 'Search/profile/workspace stay separate; this page now prioritizes memory operations.' : 'Run curation after recording explicit decisions or preferences.'}
          </p>
        </div>
      </div>
    </section>
  );
}
