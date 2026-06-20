'use client';

import { GlassCard } from '@/components/ui/GlassCard';
import { CheckCircle, Target } from 'lucide-react';
import { resolveIcon } from '@/lib/icon-map';
import type { LucideIcon } from 'lucide-react';
import type { MemoryStats, PluginCategory } from '../types';

function getCategoryIcon(category: string, categories: PluginCategory[]): LucideIcon {
  const cat = categories.find(c => c.id.toLowerCase() === category.toLowerCase() || c.name.toLowerCase() === category.toLowerCase());
  if (cat) return resolveIcon(cat.icon, Target);
  const iconMap: Record<string, string> = {
    health: 'Heart', career: 'Briefcase', workflow: 'Settings',
    finance: 'DollarSign', home: 'Home',
  };
  return resolveIcon(iconMap[category.toLowerCase()] || 'Target', Target);
}

interface RecentDecisionsProps {
  stats: MemoryStats | null;
  categories: PluginCategory[];
}

export function RecentDecisions({ stats, categories }: RecentDecisionsProps) {
  const lastCurated = stats?.lastCurated;

  return (
    <GlassCard color="emerald" icon={CheckCircle} title="Recent Decisions">
      <div className="space-y-2">
        {stats?.recentDecisions && stats.recentDecisions.length > 0 ? (
          stats.recentDecisions.map((decision) => {
            const CategoryIcon = getCategoryIcon(decision.category, categories);
            return (
              <div key={`${decision.category}:${decision.topic}`} className="flex items-start gap-3 p-3 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] transition-colors duration-200">
                <CategoryIcon className="size-4 text-emerald-400 mt-0.5" aria-hidden="true" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[var(--text-primary)] truncate">
                    {decision.topic}
                  </div>
                  <div className="text-xs text-[var(--text-muted)] truncate">
                    {decision.decision}
                  </div>
                </div>
                <span className="text-xs text-[var(--text-muted)]">{decision.date}</span>
              </div>
            );
          })
        ) : (
          <div className="rounded-xl border border-dashed border-emerald-500/20 bg-emerald-500/5 px-6 py-8 text-center">
            <CheckCircle className="mx-auto mb-3 size-8 text-emerald-400/40" aria-hidden="true" />
            <p className="text-sm font-medium text-[var(--text-primary)]">
              {lastCurated ? 'No decisions extracted in the latest curation' : 'No decisions recorded yet'}
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              {lastCurated
                ? `Last curation ran on ${lastCurated}. Open the memory sources below or widen the curation window to capture explicit decisions.`
                : 'Decisions are captured automatically during curation. Click "Curate Memory" to extract insights from recent sessions.'}
            </p>
          </div>
        )}
      </div>
    </GlassCard>
  );
}
