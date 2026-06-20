'use client';

import { CheckCircle, Lightbulb, Heart, Calendar } from 'lucide-react';
import { GlassCard, type GlassCardColor } from '@/components/ui/GlassCard';
import type { MemoryStats, MemoryStatItem } from '../types';

const MEMORY_STATS: (MemoryStatItem & { cardColor: GlassCardColor })[] = [
  { label: 'Decisions', valueKey: 'totalDecisions', icon: CheckCircle, color: 'text-emerald-400', cardColor: 'emerald' },
  { label: 'Patterns', valueKey: 'totalPatterns', icon: Lightbulb, color: 'text-purple-400', cardColor: 'purple' },
  { label: 'Preferences', valueKey: 'totalPreferences', icon: Heart, color: 'text-pink-400', cardColor: 'pink' },
  { label: 'Daily Logs', valueKey: 'dailyLogs', icon: Calendar, color: 'text-blue-400', cardColor: 'blue' },
];

interface MemoryStatsGridProps {
  stats: MemoryStats | null;
  isLoading: boolean;
}

export function MemoryStatsGrid({ stats, isLoading }: MemoryStatsGridProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 min-h-[120px]">
      {MEMORY_STATS.map((stat) => {
        const value = stats?.[stat.valueKey] ?? 0;
        return (
          <GlassCard key={stat.label} color={stat.cardColor}>
            <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <stat.icon className={`w-4 h-4 ${stat.color}`} aria-hidden="true" />
              {stat.label}
            </div>
            <div className="text-2xl font-bold text-[var(--text-primary)] mt-1">
              {isLoading ? (
                <div className="h-8 w-12 bg-[var(--bg-secondary)] rounded animate-pulse" />
              ) : (
                value.toLocaleString()
              )}
            </div>
            {!isLoading && value === 0 && (
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {stats?.lastCurated ? 'No signals in the latest snapshot' : 'Run Curate to populate'}
              </p>
            )}
          </GlassCard>
        );
      })}
    </div>
  );
}
