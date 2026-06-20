'use client';

/**
 * ADR-274 D6: Progress list renderer for auto-page data sections.
 *
 * Renders rows with label, progress bar, and value/max text.
 * Color rules evaluated per row using the safe expression evaluator from D4.
 */

import type { ProgressDefinition } from './types';
import { keyedRenderItems } from '@/lib/stable-render-key';
import { evaluateColorRule, formatStatValue } from './computeStatValue';

const COLOR_MAP: Record<string, string> = {
  emerald: 'bg-emerald-500',
  green: 'bg-green-500',
  amber: 'bg-amber-500',
  yellow: 'bg-yellow-500',
  rose: 'bg-rose-500',
  red: 'bg-red-500',
  blue: 'bg-blue-500',
  purple: 'bg-purple-500',
  indigo: 'bg-indigo-500',
  cyan: 'bg-cyan-500',
  orange: 'bg-orange-500',
  pink: 'bg-pink-500',
};

interface ProgressListRendererProps {
  data: Record<string, unknown>[];
  progress: ProgressDefinition;
}

export function ProgressListRenderer({ data, progress }: ProgressListRendererProps) {
  return (
    <div className="space-y-3">
      {keyedRenderItems(data).map(({ item, key }) => {
        const value = Number(item[progress.value_field]) || 0;
        const max = Number(item[progress.max_field]) || 1;
        const label = String(item[progress.label_field] ?? '');
        const percent = max > 0 ? (value / max) * 100 : 0;
        const clampedPercent = Math.min(Math.max(percent, 0), 100);

        // Evaluate color rule
        let barColor = 'bg-blue-500';
        if (progress.color_rule) {
          const colorName = evaluateColorRule(progress.color_rule, value, percent);
          if (colorName && COLOR_MAP[colorName]) {
            barColor = COLOR_MAP[colorName];
          }
        }

        const formattedValue = formatStatValue(value, progress.format);
        const formattedMax = formatStatValue(max, progress.format);

        return (
          <div key={key} className="rounded-xl bg-[var(--bg-hover)]/30 border border-[var(--border-color)]/20 p-4 transition-colors hover:bg-[var(--bg-hover)]/50">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-[var(--text-primary)]">{label}</span>
              <span className="text-xs text-[var(--text-muted)]">
                {formattedValue} / {formattedMax}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
              <div
                className={`h-full rounded-full transition-all ${barColor}`}
                style={{ width: `${clampedPercent}%` }}
              />
            </div>
            <div className="mt-1 text-right text-xs text-[var(--text-muted)]">
              {percent.toFixed(0)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}
