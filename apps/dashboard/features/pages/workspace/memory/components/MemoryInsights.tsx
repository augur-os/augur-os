'use client';

import { GlassCard } from '@/components/ui/GlassCard';
import { Brain, Lightbulb, CheckCircle, Heart, GitBranch, Clock3 } from 'lucide-react';
import type { MemoryStats, PluginCategory } from '../types';

interface MemoryInsightsProps {
  stats: MemoryStats | null;
  categories: PluginCategory[];
}

export function MemoryInsights({ stats, categories }: MemoryInsightsProps) {
  const topCategoryEntry = Object.entries(stats?.categoryCounts ?? {}).reduce<
    [string, number] | null
  >((top, entry) => (top === null || entry[1] > top[1] ? entry : top), null);
  const topCategoryLabel = topCategoryEntry
    ? categories.find((category) => category.id === topCategoryEntry[0])?.name || topCategoryEntry[0]
    : 'General';
  const totalSignals = (stats?.totalDecisions || 0) + (stats?.totalPatterns || 0) + (stats?.totalPreferences || 0);
  const hasData = totalSignals > 0;
  const lastCurated = stats?.lastCurated;

  if (!hasData) {
    return (
      <GlassCard color="violet" icon={Brain} title="Memory Insights">
        <div className="rounded-xl border border-dashed border-violet-500/20 bg-violet-500/5 px-6 py-8 text-center">
          <Brain className="mx-auto mb-3 size-8 text-violet-400/40" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {lastCurated ? 'Last curation did not extract durable memory signals' : 'Insights will appear after your first curation'}
          </p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {lastCurated
              ? `Last curation ran on ${lastCurated}. Capture explicit decisions or preferences in daily logs, then curate again.`
              : 'Patterns, decision history, preferences, and signal volume are analyzed from curated memory data.'}
          </p>
        </div>
      </GlassCard>
    );
  }

  const insights = [
    {
      icon: Lightbulb,
      iconColor: 'text-purple-400',
      title: 'Patterns Detected',
      value: stats?.totalPatterns ?? 0,
      gradient: 'from-purple-500/10 to-pink-500/10',
      border: 'border-purple-500/20',
      description: `${stats?.totalPatterns} recurring patterns extracted from recent sessions`,
    },
    {
      icon: CheckCircle,
      iconColor: 'text-emerald-400',
      title: 'Decision History',
      value: stats?.recentDecisions?.length ?? 0,
      gradient: 'from-emerald-500/10 to-blue-500/10',
      border: 'border-emerald-500/20',
      description: `${stats?.recentDecisions?.length ?? 0} recent decisions ready for quick recall`,
    },
    {
      icon: Heart,
      iconColor: 'text-pink-400',
      title: 'Preferences',
      value: stats?.totalPreferences ?? 0,
      gradient: 'from-pink-500/10 to-amber-500/10',
      border: 'border-pink-500/20',
      description: `${stats?.totalPreferences} preferences codified for future sessions`,
    },
    {
      icon: GitBranch,
      iconColor: 'text-cyan-300',
      title: 'Top Theme',
      value: topCategoryEntry ? topCategoryEntry[1] : 0,
      gradient: 'from-cyan-500/10 to-blue-500/10',
      border: 'border-cyan-500/20',
      description: topCategoryEntry
        ? `${topCategoryLabel} leads with ${topCategoryEntry[1]} tracked decisions`
        : 'No dominant category yet',
    },
    {
      icon: Clock3,
      iconColor: 'text-amber-300',
      title: 'Last Curated',
      value: null,
      gradient: 'from-amber-500/10 to-orange-500/10',
      border: 'border-amber-500/20',
      description: stats?.lastCurated
        ? `Memory was last distilled on ${stats.lastCurated}`
        : 'Run Curate Memory to generate the next snapshot',
    },
    {
      icon: Brain,
      iconColor: 'text-emerald-300',
      title: 'Signal Volume',
      value: totalSignals,
      gradient: 'from-emerald-500/10 to-teal-500/10',
      border: 'border-emerald-500/20',
      description: `${totalSignals} curated memory signals are searchable right now`,
    },
  ];

  return (
    <GlassCard color="violet" icon={Brain} title="Memory Insights">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {insights.map((insight) => {
          const Icon = insight.icon;
          return (
            <div
              key={insight.title}
              className={`p-4 rounded-lg bg-gradient-to-br ${insight.gradient} border ${insight.border} transition-colors duration-200`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon className={`w-5 h-5 ${insight.iconColor}`} aria-hidden="true" />
                <h4 className="text-sm font-medium text-[var(--text-primary)]">{insight.title}</h4>
                {insight.value !== null && (
                  <span className="ml-auto text-lg font-bold text-[var(--text-primary)]">{insight.value.toLocaleString()}</span>
                )}
              </div>
              <p className="text-xs text-[var(--text-muted)]">{insight.description}</p>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
