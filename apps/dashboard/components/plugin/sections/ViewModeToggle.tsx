'use client';

/**
 * ADR-274 D5: View mode toggle for switching between list/grid/card views.
 *
 * Persists selection in localStorage per section ID.
 */

import { useState } from 'react';
import { List, LayoutGrid, CreditCard } from 'lucide-react';
import type { ViewMode } from './types';

const VIEW_ICONS: Record<ViewMode, typeof List> = {
  list: List,
  grid: LayoutGrid,
  card: CreditCard,
};

interface ViewModeToggleProps {
  sectionId: string;
  modes: ViewMode[];
  defaultMode: ViewMode;
  activeMode: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export function ViewModeToggle({ sectionId, modes, defaultMode, activeMode, onChange }: ViewModeToggleProps) {
  return (
    <div className="inline-flex items-center rounded-lg border border-gray-200 bg-white p-0.5">
      {modes.map((mode) => {
        const Icon = VIEW_ICONS[mode];
        const isActive = mode === activeMode;
        return (
          <button type="button"
            key={mode}
            onClick={() => onChange(mode)}
            className={`rounded-md p-1.5 transition-colors ${
              isActive
                ? 'bg-gray-900 text-white'
                : 'text-gray-400 hover:text-gray-600'
            }`}
            title={`${mode} view`}
            aria-label={`Switch to ${mode} view`}
            aria-pressed={isActive}
          >
            <Icon className="size-4" />
          </button>
        );
      })}
    </div>
  );
}

/**
 * Hook for managing view mode state with localStorage persistence.
 */
export function useViewMode(sectionId: string, modes: ViewMode[], defaultMode: ViewMode): [ViewMode, (m: ViewMode) => void] {
  const storageKey = `augur-view-mode-${sectionId}`;
  const [mode, setMode] = useState<ViewMode>(() => {
    if (typeof window === 'undefined') return defaultMode;
    const stored = localStorage.getItem(storageKey);
    if (stored && modes.includes(stored as ViewMode)) return stored as ViewMode;
    return defaultMode;
  });

  const setAndPersist = (m: ViewMode) => {
    setMode(m);
    localStorage.setItem(storageKey, m);
  };

  return [mode, setAndPersist];
}
