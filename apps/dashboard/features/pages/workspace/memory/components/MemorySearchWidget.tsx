'use client';

import DashboardWidget from '@/features/components/DashboardWidget';
import { Search, Target, Sparkles, CalendarDays, FileText, ExternalLink } from 'lucide-react';
import { resolveIcon } from '@/lib/icon-map';
import type { LucideIcon } from 'lucide-react';
import type { MemorySearchFilters, MemorySearchResult, PluginCategory } from '../types';

export interface MemorySearchSuggestion {
  label: string;
  query: string;
  category?: string;
  source?: string;
  dateFrom?: string;
  dateTo?: string;
}

const SUGGESTED_QUERIES: MemorySearchSuggestion[] = [
  { label: 'recent decisions', query: 'recent decisions', category: 'decision', source: 'curated' },
  { label: 'workflow', query: 'workflow' },
  { label: 'communication preferences', query: 'communication preferences', category: 'preference', source: 'curated' },
];

const getConfidenceColor = (relevance: number) => {
  if (relevance >= 0.8) return 'text-[var(--accent-success)]';
  if (relevance >= 0.5) return 'text-[var(--accent-warning)]';
  return 'text-[var(--accent-danger)]';
};

interface MemorySearchWidgetProps {
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  isSearching: boolean;
  searchResults: MemorySearchResult[];
  hasSearched: boolean;
  searchError: string | null;
  onSearch: (queryOverride?: string, filters?: MemorySearchFilters) => void;
  onOpenResult?: (result: MemorySearchResult) => void;
  openingResultPath?: string | null;
  openResultError?: string | null;
  suggestedQueries?: Array<string | MemorySearchSuggestion>;
  categories: PluginCategory[];
  sourceLabel?: string;
  freshnessLabel?: string;
  title?: string;
  description?: string;
}

function getCategoryIcon(category: string | null | undefined, categories: PluginCategory[]): LucideIcon {
  const normalizedCategory = typeof category === 'string' && category.trim() ? category.trim().toLowerCase() : 'memory';
  const cat = categories.find(c => c.id.toLowerCase() === normalizedCategory || c.name.toLowerCase() === normalizedCategory);
  if (cat) return resolveIcon(cat.icon, Target);
  const iconMap: Record<string, string> = {
    decision: 'CheckCircle',
    pattern: 'Lightbulb',
    preference: 'Heart',
    event: 'CalendarDays',
    health: 'Heart', career: 'Briefcase', workflow: 'Settings',
    finance: 'DollarSign', home: 'Home', memory: 'Target',
  };
  return resolveIcon(iconMap[normalizedCategory] || 'Target', Target);
}

export function MemorySearchWidget({
  searchQuery,
  setSearchQuery,
  isSearching,
  searchResults,
  hasSearched,
  searchError,
  onSearch,
  onOpenResult,
  openingResultPath,
  openResultError,
  suggestedQueries,
  categories,
  sourceLabel,
  freshnessLabel,
  title = 'Memory Search',
  description = 'Search for past decisions, patterns, and preferences. Example: "What did we decide about vitamin D?"',
}: MemorySearchWidgetProps) {
  const activeSuggestedQueries = (suggestedQueries?.length ? suggestedQueries : SUGGESTED_QUERIES).map((suggestion) =>
    typeof suggestion === 'string'
      ? { label: suggestion, query: suggestion }
      : suggestion,
  );
  return (
    <DashboardWidget title={title} icon={Search} fillHeight={false}>
      <div className="p-4">
        <p className="text-sm text-[var(--text-muted)] mb-4">
          {description}
        </p>
        {(sourceLabel || freshnessLabel) && (
          <div className="mb-4 flex flex-wrap gap-2 text-xs">
            {sourceLabel && (
              <span className="inline-flex items-center rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2.5 py-1 text-[var(--text-secondary)]">
                {sourceLabel}
              </span>
            )}
            {freshnessLabel && (
              <span className="inline-flex items-center rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2.5 py-1 text-[var(--text-muted)]">
                {freshnessLabel}
              </span>
            )}
          </div>
        )}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-5 text-[var(--text-muted)]" aria-hidden="true" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onSearch()}
              placeholder="Search memory..."
              aria-label="Search memory"
              className="w-full pl-12 pr-4 py-3 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-purple-500/40 focus:border-purple-500/50"
            />
          </div>
          <button type="button"
            onClick={() => onSearch()}
            disabled={isSearching || !searchQuery.trim()}
            className="px-6 py-3 min-h-[44px] bg-[var(--accent-primary)] hover:opacity-90 border border-[var(--accent-primary)] rounded-lg text-[var(--accent-foreground)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </div>
        {!searchQuery.trim() && !isSearching && (
          <p className="mt-2 text-xs text-[var(--text-muted)]">Enter a topic or choose a suggestion to enable search.</p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {activeSuggestedQueries.map((suggestion) => (
            <button type="button"
              key={`${suggestion.label}:${suggestion.query}`}
              onClick={() =>
                onSearch(suggestion.query, {
                  category: suggestion.category,
                  source: suggestion.source,
                  dateFrom: suggestion.dateFrom,
                  dateTo: suggestion.dateTo,
                })
              }
              className="inline-flex min-h-[44px] items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1.5 text-xs text-purple-500 transition-colors hover:bg-purple-500/20"
            >
              <Sparkles className="size-3" aria-hidden="true" />
              {suggestion.label}
            </button>
          ))}
        </div>

        {searchError && (
          <p className="mt-3 text-sm text-[var(--accent-danger)]">{searchError}</p>
        )}
        {openResultError && (
          <p className="mt-3 text-sm text-[var(--accent-danger)]">{openResultError}</p>
        )}

        {searchResults.length > 0 && (
          <div className="mt-4 space-y-2">
            <h4 className="text-sm font-medium text-[var(--text-secondary)]">Results:</h4>
            {searchResults.map((result) => {
              const CategoryIcon = getCategoryIcon(result.category, categories);
              const confidenceLabel = result.relevance >= 0.8 ? 'High' : result.relevance >= 0.5 ? 'Medium' : 'Low';
              return (
                <div key={`${result.source}:${result.file_path ?? result.date}:${result.content}`} className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] hover:border-[var(--accent-primary)]/30 transition-colors duration-200">
                  <div className="flex items-start gap-3">
                    <CategoryIcon className="size-5 text-purple-400 mt-0.5" aria-hidden="true" />
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="rounded-full bg-purple-500/10 px-2 py-0.5 text-purple-500">
                          {result.source === 'daily' ? 'Daily Log' : 'Curated Memory'}
                        </span>
                        {result.date && (
                          <span className="inline-flex items-center gap-1 text-[var(--text-muted)]">
                            <CalendarDays className="size-3" aria-hidden="true" />
                            {result.date}
                          </span>
                        )}
                        <span className={getConfidenceColor(result.relevance)}>
                          {confidenceLabel} confidence
                        </span>
                      </div>
                      <div className="mt-2 text-sm text-[var(--text-primary)]">{result.content}</div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {result.file_path && (
                          <div className="inline-flex items-center gap-1 text-xs text-[var(--text-muted)] max-w-full">
                            <FileText className="size-3 shrink-0" aria-hidden="true" />
                            <span className="truncate" title={`${result.file_path}${result.line_number ? `:${result.line_number}` : ''}`}>
                              {result.file_path}
                              {result.line_number ? `:${result.line_number}` : ''}
                            </span>
                          </div>
                        )}
                        {result.file_path && onOpenResult && (
                          <button type="button"
                            onClick={() => onOpenResult(result)}
                            disabled={openingResultPath === result.file_path}
                            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-2.5 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <ExternalLink className="size-3" aria-hidden="true" />
                            {openingResultPath === result.file_path ? 'Opening...' : 'Open source'}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {hasSearched && !isSearching && !searchError && searchResults.length === 0 && (
          <div className="mt-4 rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-6 text-center">
            <p className="text-sm text-[var(--text-primary)]">No matching memory entries yet.</p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Try a narrower date range, a concrete topic, or a phrase from the original decision. Curate memory if the source looks stale.
            </p>
          </div>
        )}
      </div>
    </DashboardWidget>
  );
}
