'use client';

import { GlassCard } from '@/components/ui/GlassCard';
import { Target } from 'lucide-react';
import { resolveIcon } from '@/lib/icon-map';
import type { MemoryStats } from '../types';

const CATEGORY_META: Record<string, { icon: string; color: string }> = {
  general: { icon: 'Target', color: 'text-[var(--text-secondary)]' },
  architecture: { icon: 'Layers', color: 'text-blue-400' },
  workflow: { icon: 'Settings', color: 'text-amber-400' },
  communication: { icon: 'MessageSquare', color: 'text-emerald-400' },
};

interface DecisionCategoriesProps {
  stats: MemoryStats | null;
}

export function DecisionCategories({ stats }: DecisionCategoriesProps) {
  const categoryCounts = stats?.categoryCounts ?? {};
  const sorted = Object.entries(categoryCounts).sort((a, b) => b[1] - a[1]);

  return (
    <GlassCard color="amber" icon={Target} title="Decision Categories">
      <div className="space-y-2">
        {sorted.length > 0 ? (
          sorted.slice(0, 8).map(([key, count]) => {
            const meta = CATEGORY_META[key] ?? { icon: 'Target', color: 'text-[var(--text-muted)]' };
            const CategoryIcon = resolveIcon(meta.icon, Target);
            const label = key.charAt(0).toUpperCase() + key.slice(1);
            return (
              <div key={key} className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] transition-colors duration-200">
                <div className="flex items-center gap-3">
                  <CategoryIcon className={`w-4 h-4 ${meta.color}`} aria-hidden="true" />
                  <span className="text-sm text-[var(--text-primary)]">{label}</span>
                </div>
                <span className="text-sm font-medium text-[var(--text-muted)]">{count.toLocaleString()}</span>
              </div>
            );
          })
        ) : (
          <div className="rounded-xl border border-dashed border-amber-500/20 bg-amber-500/5 px-6 py-8 text-center">
            <Target className="mx-auto mb-3 size-8 text-amber-400/40" aria-hidden="true" />
            <p className="text-sm font-medium text-[var(--text-primary)]">No categories yet</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Categories emerge as decisions are curated across different domains.
            </p>
          </div>
        )}
      </div>
    </GlassCard>
  );
}
