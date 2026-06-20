'use client';

/**
 * ADR-274 D13: Tabbed section renderer for auto-page data sections.
 *
 * Groups multiple data sources into tabs. Active tab persisted in URL
 * search params namespaced by section ID to avoid collisions with
 * DetailModal (D8) and other tabbed sections on the same page.
 */

import { useState, useEffect, useCallback, useRef, useReducer } from 'react';
import { Loader2 } from 'lucide-react';

import type { TabbedSectionTab } from './types';
import { fetchFromSource } from '@/lib/plugin-schema/data-fetcher';

interface TabbedSectionRendererProps {
  sectionId: string;
  tabs: TabbedSectionTab[];
  renderContent: (data: unknown[], tabId: string) => React.ReactNode;
}

function normalizeTabResult(result: unknown): unknown[] {
  if (Array.isArray(result)) return result;
  if (!result || typeof result !== 'object') return [];

  const obj = result as Record<string, unknown>;

  if ('success' in obj && obj.success === true && 'data' in obj) {
    return normalizeTabResult(obj.data);
  }

  const scalarKeys = Object.keys(obj).filter((key) => {
    const value = obj[key];
    return (
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean'
    );
  });

  if (scalarKeys.length >= 3) {
    return [obj];
  }

  const collectionKeys = [
    'items',
    'results',
    'entries',
    'rows',
    'records',
    'list',
    'accounts',
    'transactions',
    'categories',
    'goals',
    'holdings',
  ];

  for (const key of collectionKeys) {
    if (Array.isArray(obj[key])) {
      return obj[key] as unknown[];
    }
  }

  const arrayEntries = Object.entries(obj).filter(([, value]) => Array.isArray(value));
  if (arrayEntries.length === 1) {
    return arrayEntries[0][1] as unknown[];
  }

  return [obj];
}

function getTabParamKey(sectionId: string): string {
  return `${sectionId}_tab`;
}

function getActiveTabFromUrl(sectionId: string, tabs: TabbedSectionTab[]): string {
  if (typeof window === 'undefined') return tabs[0]?.id ?? '';
  const params = new URLSearchParams(window.location.search);
  const stored = params.get(getTabParamKey(sectionId));
  if (stored && tabs.some((t) => t.id === stored)) return stored;
  return tabs[0]?.id ?? '';
}

function setActiveTabInUrl(sectionId: string, tabId: string): void {
  if (typeof window === 'undefined') return;
  const params = new URLSearchParams(window.location.search);
  params.set(getTabParamKey(sectionId), tabId);
  const url = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState(null, '', url);
}

interface TabbedSectionState {
  loadedData: Record<string, unknown[]>;
  loading: Record<string, boolean>;
}

type TabbedSectionAction =
  | { type: 'start'; tabId: string }
  | { type: 'complete'; tabId: string; data: unknown[] };

function tabbedSectionReducer(
  state: TabbedSectionState,
  action: TabbedSectionAction,
): TabbedSectionState {
  switch (action.type) {
    case 'start':
      return {
        ...state,
        loading: { ...state.loading, [action.tabId]: true },
      };
    case 'complete':
      return {
        loadedData: { ...state.loadedData, [action.tabId]: action.data },
        loading: { ...state.loading, [action.tabId]: false },
      };
    default:
      return state;
  }
}

export function TabbedSectionRenderer({ sectionId, tabs, renderContent }: TabbedSectionRendererProps) {
  const [activeTab, setActiveTab] = useState(() => getActiveTabFromUrl(sectionId, tabs));
  const [{ loadedData, loading }, dispatchTabState] = useReducer(
    tabbedSectionReducer,
    { loadedData: {}, loading: {} },
  );
  const fetchedTabsRef = useRef<Set<string> | null>(null);
  if (fetchedTabsRef.current === null) {
    fetchedTabsRef.current = new Set<string>();
  }

  const switchTab = useCallback(
    (tabId: string) => {
      setActiveTab(tabId);
      setActiveTabInUrl(sectionId, tabId);
    },
    [sectionId],
  );

  useEffect(() => {
    const fetchedTabs = fetchedTabsRef.current;
    if (!fetchedTabs || fetchedTabs.has(activeTab)) return;
    if (loadedData[activeTab] !== undefined) return;
    const tab = tabs.find((t) => t.id === activeTab);
    if (!tab) return;

    let cancelled = false;
    fetchedTabs.add(activeTab);
    dispatchTabState({ type: 'start', tabId: activeTab });
    fetchFromSource(tab.source)
      .then((result) => {
        if (cancelled) return;
        dispatchTabState({
          type: 'complete',
          tabId: activeTab,
          data: normalizeTabResult(result),
        });
      })
      .catch((err) => {
        if (cancelled) return;
        console.error(`Failed to load tab "${activeTab}":`, err);
        dispatchTabState({ type: 'complete', tabId: activeTab, data: [] });
      });
    return () => { cancelled = true; };
  }, [activeTab, tabs, loadedData]);

  if (tabs.length === 0) return null;

  return (
    <div>
      {/* Tab bar */}
      <div className="flex border-b border-gray-200 mb-4">
        {tabs.map((tab) => (
          <button type="button"
            key={tab.id}
            onClick={() => switchTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab.id === activeTab
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {loading[activeTab] ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-[var(--text-muted)]" />
        </div>
      ) : loadedData[activeTab] ? (
        renderContent(loadedData[activeTab], activeTab)
      ) : null}
    </div>
  );
}
