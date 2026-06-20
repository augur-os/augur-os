'use client';

import Link from 'next/link';
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Calendar,
  ClipboardCheck,
  Inbox,
  ShieldAlert,
  Sparkles,
  User,
} from 'lucide-react';
import { useBrainInbox } from '@/features/pages/workspace/inbox/hooks';
import { useBrainInsights } from '@/features/pages/workspace/insights/hooks';
import { useMemoryDashboardData, useWikiMaintenanceData } from '@/features/pages/workspace/memory/hooks';
import {
  formatFreshness,
} from '@/features/pages/workspace/memory/contracts';
import type { LucideIcon } from 'lucide-react';

interface ActionCardProps {
  href: string;
  title: string;
  summary: string;
  detail: string;
  icon: LucideIcon;
  accentClass: string;
  loading?: boolean;
}

function ActionCard({
  href,
  title,
  summary,
  detail,
  icon: Icon,
  accentClass,
  loading = false,
}: ActionCardProps) {
  return (
    <Link
      href={href}
      aria-busy={loading || undefined}
      className="group flex h-full min-h-[168px] cursor-pointer flex-col rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5 shadow-sm transition-colors duration-200 hover:border-[var(--accent-primary)]/40 hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
    >
      <div className="flex items-start gap-3">
        <div className={`rounded-lg border p-2 ${accentClass}`}>
          <Icon className="size-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold leading-5 text-[var(--text-primary)]">{title}</h2>
          <p className="mt-3 text-base font-semibold leading-6 text-[var(--text-primary)]">{summary}</p>
          <p className="mt-1 line-clamp-3 text-sm leading-5 text-[var(--text-secondary)] [overflow-wrap:anywhere]">
            {detail}
          </p>
        </div>
      </div>
      <div className="mt-auto inline-flex items-center gap-2 pt-4 text-sm font-medium text-[var(--accent-primary)]">
        Open
        <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden="true" />
      </div>
    </Link>
  );
}

function isOlderThan(value: string | null | undefined, hours: number): boolean {
  if (!value) {
    return true;
  }
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) {
    return true;
  }
  return Date.now() - timestamp > hours * 60 * 60 * 1000;
}

function countLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function useBrainOverviewModel() {
  const {
    stats,
    sources,
    error,
    isStatsLoading,
    isWorkspaceLoading,
    refreshStats,
  } = useMemoryDashboardData();
  const wikiMaintenance = useWikiMaintenanceData();
  const brainInbox = useBrainInbox();
  const brainInsights = useBrainInsights();

  const inboxTotals = brainInbox.totals ?? { newFiles: 0, documents: 0, trash: 0, failed: 0 };
  const latestInsightsCount = brainInsights.latestRuns
    ?.reduce((total, run) => total + (run.insights?.length ?? 0), 0) ?? 0;
  const pendingWikiSources = brainInsights.wikiStatus?.compiler?.sources_pending_or_changed ?? 0;
  const inboxLoading = Boolean(brainInbox.loading);
  const insightsLoading = Boolean(brainInsights.loading);
  const brainSignalsLoading = isStatsLoading || isWorkspaceLoading || inboxLoading || insightsLoading;
  const watchedFolderCount = brainInbox.folders?.length ?? 0;

  const needsAttention = [
    {
      key: 'memory-curation',
      visible: isOlderThan(stats?.lastCurated, 48),
      title: 'Memory curation',
      summary: stats?.lastCurated
        ? `Last curated ${formatFreshness(stats.lastCurated).replace(/^Updated /, '').toLowerCase()}`
        : 'Memory has not been curated recently',
      detail: 'Review sessions, refresh the memory report, and capture new decisions.',
      href: '/workspace/memory',
      icon: Sparkles,
      accentClass: 'border-purple-500/25 bg-purple-500/10 text-purple-400',
    },
    {
      key: 'wiki-quality',
      visible: (wikiMaintenance.summary?.rewriteCandidates ?? 0) > 0,
      title: 'Wiki quality',
      summary: `${wikiMaintenance.summary?.rewriteCandidates ?? 0} rewrite candidates pending`,
      detail: 'Memory maintenance found wiki pages that still need editorial cleanup.',
      href: '/workspace/insights',
      icon: ShieldAlert,
      accentClass: 'border-amber-500/25 bg-amber-500/10 text-amber-400',
    },
    {
      key: 'profile-freshness',
      visible: !sources?.profile?.exists || isOlderThan(sources.profile.modifiedAt, 120),
      title: 'Profile freshness',
      summary: sources?.profile?.exists
        ? formatFreshness(sources.profile.modifiedAt)
        : 'Profile source needs attention',
      detail: 'Refresh the human API profile before relying on stale assumptions.',
      href: '/workspace/profile',
      icon: User,
      accentClass: 'border-cyan-500/25 bg-cyan-500/10 text-cyan-400',
    },
  ].filter((item) => item.visible);

  const brainActions = [
    {
      href: '/workspace/memory',
      title: 'Memory',
      summary: isStatsLoading && !stats ? 'Loading memory' : countLabel(stats?.totalDecisions ?? 0, 'decision'),
      detail: stats?.lastCurated
        ? `Curated ${formatFreshness(stats.lastCurated).replace(/^Updated /, '').toLowerCase()}`
        : 'Curate sessions into durable memory',
      icon: BookOpen,
      accentClass: 'border-purple-500/25 bg-purple-500/10 text-purple-400',
      loading: isStatsLoading && !stats,
    },
    {
      href: '/workspace/memory-review',
      title: 'Review',
      summary: 'Memory review queue',
      detail: 'Approve or reject queued memory candidates.',
      icon: ClipboardCheck,
      accentClass: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-400',
    },
    {
      href: '/workspace/inbox',
      title: 'Inbox',
      summary: inboxLoading && !brainInbox.totals ? 'Loading inbox' : countLabel(inboxTotals.newFiles, 'new file'),
      detail: `${inboxTotals.documents} docs across ${countLabel(watchedFolderCount, 'folder')}`,
      icon: Inbox,
      accentClass: 'border-rose-500/25 bg-rose-500/10 text-rose-400',
      loading: inboxLoading && !brainInbox.totals,
    },
    {
      href: '/workspace/insights',
      title: 'Insights',
      summary: insightsLoading && !brainInsights.wikiStatus
        ? 'Loading insights'
        : pendingWikiSources > 0
          ? countLabel(pendingWikiSources, 'wiki candidate')
          : `${latestInsightsCount} latest insights`,
      detail: 'Inspect impact-ranked insights and next actions.',
      icon: ShieldAlert,
      accentClass: 'border-amber-500/25 bg-amber-500/10 text-amber-400',
      loading: insightsLoading && !brainInsights.wikiStatus,
    },
    {
      href: '/workspace/daily-logs',
      title: 'Daily Logs',
      summary: `${stats?.dailyLogs ?? 0} captured`,
      detail: 'Review the calendar and recent entries shaping memory.',
      icon: Calendar,
      accentClass: 'border-blue-500/25 bg-blue-500/10 text-blue-400',
    },
  ];

  return {
    brainSignalsLoading,
    brainActions,
    error,
    needsAttention,
    refreshStats,
  };
}

type BrainOverviewModel = ReturnType<typeof useBrainOverviewModel>;

export function BrainOverviewHome() {
  const model = useBrainOverviewModel();

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <LiveSignalsRegion loading={model.brainSignalsLoading} />
      <BrainOverviewError model={model} />
      <NeedsAttentionSection model={model} />
      <CardGridSection
        eyebrow="Workspace Actions"
        title="Open the next workflow."
        cards={model.brainActions}
        columnsClass="sm:grid-cols-2 xl:grid-cols-5"
      />
    </div>
  );
}

function LiveSignalsRegion({ loading }: { loading: boolean }) {
  if (!loading) {
    return null;
  }
  return (
    <div aria-live="polite" className="sr-only">
      Loading live workspace signals
    </div>
  );
}

function BrainOverviewError({ model }: { model: BrainOverviewModel }) {
  if (!model.error) {
    return null;
  }
  return (
    <div role="alert" className="glass-panel rounded-xl border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-[var(--accent-danger)]" aria-hidden="true" />
          <div>
            <p className="text-sm text-[var(--text-primary)]">{model.error}</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Workspace stays usable, but some signals may be stale until refresh succeeds.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => model.refreshStats()}
          className="min-h-[44px] min-w-[44px] shrink-0 cursor-pointer items-center justify-center text-xs text-[var(--accent-danger)] underline transition-opacity duration-200 hover:opacity-70"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

function CardGridSection({
  eyebrow,
  title,
  cards,
  columnsClass,
}: {
  eyebrow: string;
  title: string;
  cards: ActionCardProps[];
  columnsClass: string;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          {eyebrow}
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">{title}</p>
      </div>
      <div className={`grid grid-cols-1 gap-4 ${columnsClass}`}>
        {cards.map((card) => (
          <ActionCard key={`${card.href}:${card.title}`} {...card} />
        ))}
      </div>
    </section>
  );
}

function NeedsAttentionSection({ model }: { model: BrainOverviewModel }) {
  // Per the lean-overview design, this zone renders only when something is
  // actually wrong — no empty/reassurance card when the Brain is in good shape.
  if (model.needsAttention.length === 0) {
    return null;
  }
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Needs Attention
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          These are the places where stale knowledge or maintenance debt can hurt your workspace.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {model.needsAttention.map((item) => (
          <ActionCard
            key={item.key}
            href={item.href}
            title={item.title}
            summary={item.summary}
            detail={item.detail}
            icon={item.icon}
            accentClass={item.accentClass}
          />
        ))}
      </div>
    </section>
  );
}
