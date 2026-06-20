'use client';

import { GlassCard } from '@/components/ui/GlassCard';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { keyedRenderItems } from '@/lib/stable-render-key';

interface Stat {
  label: string;
  value: string | number;
  icon?: string;
  color?: string;
}

interface StatCardsProps {
  stats?: Stat[];
  /** @deprecated Use `tool` instead */
  apiUrl?: string;
  tool?: string;
  toolArgs?: Record<string, unknown>;
}

const DEFAULT_STATS: Stat[] = [
  { label: 'Total', value: '—' },
  { label: 'Active', value: '—' },
  { label: 'Completed', value: '—' },
  { label: 'Pending', value: '—' },
];

export default function StatCards({ stats, tool, toolArgs }: StatCardsProps) {
  const { data: fetched, loading } = useMcpQuery<Stat[]>(
    ['stat-cards', tool ?? ''],
    tool ?? '',
    'live',
    {
      enabled: !!tool,
      args: toolArgs,
      select: (raw: unknown) => {
        const data = raw as Record<string, unknown>;
        return Array.isArray(data) ? data : (data.stats ?? data.items ?? []) as Stat[];
      },
    },
  );

  const displayStats = tool ? (fetched ?? []) : stats ?? DEFAULT_STATS;

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-4">
        {['stat-card-skeleton-a', 'stat-card-skeleton-b', 'stat-card-skeleton-c', 'stat-card-skeleton-d'].map((key) => (
          <GlassCard key={key} className="p-4 animate-pulse">
            <div className="h-8 bg-[var(--bg-secondary)] rounded mb-1" />
            <div className="h-3 w-16 bg-[var(--bg-secondary)] rounded" />
          </GlassCard>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-4">
      {keyedRenderItems(displayStats, (stat) => stat.label).map(({ item: stat, key }) => (
        <GlassCard key={key} className="p-4 flex flex-col gap-1">
          {stat.icon && (
            <span
              className="text-2xl mb-1 leading-none"
              aria-hidden="true"
            >
              {stat.icon}
            </span>
          )}
          <span
            className="text-2xl font-bold tracking-tight tabular-nums"
            style={{ color: stat.color ?? 'var(--text-primary)' }}
          >
            {stat.value}
          </span>
          <span className="text-xs font-medium truncate" style={{ color: 'var(--text-muted)' }}>
            {stat.label}
          </span>
        </GlassCard>
      ))}
    </div>
  );
}
