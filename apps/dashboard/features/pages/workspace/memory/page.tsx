'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AlertCircle, ArrowRight, FolderOpen, RefreshCw } from 'lucide-react';
import { mcpCall } from '@/lib/mcp/client';
import { assertMcpSuccess, getPrimarySourceFreshnessLabel, getPrimarySourceLabel } from './contracts';
import {
  useMemoryDashboardData,
  useMemorySearch,
} from './hooks';
import { MemoryStatsGrid } from './components/MemoryStatsGrid';
import { MemorySearchWidget } from './components/MemorySearchWidget';
import { RecentDecisions } from './components/RecentDecisions';
import { DecisionCategories } from './components/DecisionCategories';
import { MemoryInsights } from './components/MemoryInsights';
import { WikiMaintenancePanel } from './components/WikiMaintenancePanel';
import { MemoryCommandCenter } from './components/MemoryCommandCenter';
import { useWikiMaintenanceData } from './hooks';
import { buildSuggestedQueries } from './search-suggestions';

export default function MemoryPage() {
  const {
    stats,
    categories,
    workspace,
    sources,
    error,
    isStatsLoading,
    refreshAll,
  } = useMemoryDashboardData();
  const searchHook = useMemorySearch();
  const wikiMaintenance = useWikiMaintenanceData();
  const [isCurating, setIsCurating] = useState(false);
  const [curateError, setCurateError] = useState<string | null>(null);
  const [curateNotice, setCurateNotice] = useState<string | null>(null);
  const sourceLabel = getPrimarySourceLabel(sources);
  const freshnessLabel = getPrimarySourceFreshnessLabel(sources);

  const handleCurate = async () => {
    setIsCurating(true);
    setCurateError(null);
    setCurateNotice(null);
    try {
      const response = await mcpCall('memory-curate', { days_back: 7, archive_processed: false });
      assertMcpSuccess(response, 'Curate memory');
      await refreshAll();
      setCurateNotice('Memory curated. Stats and workspace data refreshed.');
    } catch (error) {
      console.error('Curation failed:', error);
      setCurateError('Curate Memory failed. Check the generated report or retry.');
    } finally {
      setIsCurating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header — compact with curate action */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Session Memory</h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Decisions, patterns, and preferences from your sessions
          </p>
          <Link
            href="/browse?view=profile"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--accent-primary)] hover:underline mt-1"
          >
            Browse all memory entries
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
        <button type="button"
          onClick={handleCurate}
          disabled={isCurating}
          className="flex items-center gap-2 px-4 min-h-[44px] bg-gradient-to-r from-purple-500/15 to-pink-500/15 hover:from-purple-500/25 hover:to-pink-500/25 border border-purple-500/30 rounded-lg text-purple-500 font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shrink-0 cursor-pointer"
        >
          <RefreshCw className={`size-4 ${isCurating ? 'animate-spin' : ''}`} aria-hidden="true" />
          {isCurating ? 'Curating...' : 'Curate Memory'}
        </button>
      </header>

      {(error || curateError) && (
        <div role="alert" className="glass-panel rounded-xl border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 size-4 text-[var(--accent-danger)] shrink-0" aria-hidden="true" />
              <div>
                <p className="text-sm text-[var(--text-primary)]">{curateError || error}</p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  The page stays usable, but some live memory data may be stale until the next refresh.
                </p>
              </div>
            </div>
            <button type="button" onClick={refreshAll} className="text-xs text-[var(--accent-danger)] underline hover:opacity-70 cursor-pointer min-h-[44px] min-w-[44px] flex items-center justify-center transition-opacity duration-200 shrink-0">Retry</button>
          </div>
        </div>
      )}

      {curateNotice && (
        <div role="status" aria-live="polite" className="rounded-xl border border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 px-4 py-3 text-sm text-[var(--text-primary)]">
          {curateNotice}
        </div>
      )}

      <MemoryCommandCenter
        stats={stats}
        sources={sources}
        workspace={workspace}
        wikiSummary={wikiMaintenance.summary}
        sourceLabel={sourceLabel}
        freshnessLabel={freshnessLabel}
        isCurating={isCurating}
        onCurate={handleCurate}
      />

      {/* Search — promoted to top as primary action */}
      <MemorySearchWidget
        searchQuery={searchHook.searchQuery}
        setSearchQuery={searchHook.setSearchQuery}
        isSearching={searchHook.isSearching}
        searchResults={searchHook.searchResults}
        hasSearched={searchHook.hasSearched}
        searchError={searchHook.searchError}
        onSearch={searchHook.handleSearch}
        onOpenResult={searchHook.openSearchResult}
        openingResultPath={searchHook.openingResultPath}
        openResultError={searchHook.openResultError}
        suggestedQueries={buildSuggestedQueries(stats)}
        categories={categories}
        sourceLabel={sourceLabel}
        freshnessLabel={freshnessLabel}
      />

      {/* Stats */}
      <MemoryStatsGrid stats={stats} isLoading={isStatsLoading} />

      {/* Recent + Categories — primary content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RecentDecisions stats={stats} categories={categories} />
        </div>
        <DecisionCategories stats={stats} />
      </div>

      {/* Insights */}
      <MemoryInsights stats={stats} categories={categories} />

      <WikiMaintenancePanel
        summary={wikiMaintenance.summary}
        candidates={wikiMaintenance.candidates}
        totalCandidates={wikiMaintenance.totalCandidates}
        isLoading={wikiMaintenance.isLoading}
        error={wikiMaintenance.error}
        onRefresh={wikiMaintenance.refetch}
      />

      <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="rounded-lg border border-blue-500/25 bg-blue-500/10 p-2 text-blue-400">
              <FolderOpen className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Workspace files</h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Canonical memory files and generated reports are browsable in Documents.
              </p>
            </div>
          </div>
          <Link
            href="/browse?view=documents"
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            Browse memory files
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </div>
  );
}
