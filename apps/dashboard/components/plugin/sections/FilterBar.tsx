'use client';

/**
 * ADR-274 D1: Pill-style filter bar for auto-page data sections.
 *
 * Renders toggleable filter pills for discrete field values.
 * Supports multi-select — clicking a pill toggles it on/off.
 */

import type { FilterDefinition } from './types';

const DEFAULT_COLORS: Record<string, string> = {
  blue: 'bg-blue-500/15 text-blue-500 border-blue-500/25',
  amber: 'bg-amber-500/15 text-amber-500 border-amber-500/25',
  emerald: 'bg-emerald-500/15 text-emerald-500 border-emerald-500/25',
  rose: 'bg-rose-500/15 text-rose-500 border-rose-500/25',
  purple: 'bg-purple-500/15 text-purple-500 border-purple-500/25',
  gray: 'bg-[var(--bg-hover)] text-[var(--text-secondary)] border-[var(--border-color)]',
  orange: 'bg-orange-500/15 text-orange-500 border-orange-500/25',
  cyan: 'bg-cyan-500/15 text-cyan-500 border-cyan-500/25',
  indigo: 'bg-indigo-500/15 text-indigo-500 border-indigo-500/25',
  teal: 'bg-teal-500/15 text-teal-500 border-teal-500/25',
  pink: 'bg-pink-500/15 text-pink-500 border-pink-500/25',
};

const INACTIVE_STYLE = 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border-color)] hover:bg-[var(--bg-hover)]';

interface FilterBarProps {
  filter: FilterDefinition;
  activeValues: Set<string>;
  onToggle: (value: string) => void;
}

export function FilterBar({ filter, activeValues, onToggle }: FilterBarProps) {
  const values = filter.values ?? [];

  return (
    <fieldset className="m-0 flex min-w-0 flex-wrap gap-1.5 border-0 p-0">
      <legend className="sr-only">{`Filter by ${filter.field}`}</legend>
      {values.map((val) => {
        const isActive = activeValues.has(val);
        const colorKey = filter.colors?.[val];
        const activeStyle = colorKey && DEFAULT_COLORS[colorKey]
          ? DEFAULT_COLORS[colorKey]
          : 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)] border-[var(--accent-primary)]/30';

        return (
          <button type="button"
            key={val}
            onClick={() => onToggle(val)}
            aria-pressed={isActive}
            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
              isActive ? activeStyle : INACTIVE_STYLE
            }`}
          >
            {val}
          </button>
        );
      })}
    </fieldset>
  );
}
