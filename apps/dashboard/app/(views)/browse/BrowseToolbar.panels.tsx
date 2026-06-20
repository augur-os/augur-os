"use client";

import { Loader2 } from "lucide-react";
import { type BrowseCategory } from "@/lib/browse/types";
import type { BrowseSortBy } from "@/lib/browse/pinOrdering";
import type { BrowseDisplayMode } from "@/lib/browse/displayMode";
import { VaultSyncStatus } from "@/features/browse/VaultSyncStatus";
import type { FilterControl } from "./BrowseToolbar.types";
import {
  ToolbarSearchControl,
  DisplayModeControl,
  FiltersToggleButton,
  SortSelect,
} from "./BrowseToolbar.controls";

export function BrowseToolbarMainRow({
  activeCategory,
  activeFilterCount,
  deepSearchBusy,
  displayMode,
  filtersOpen,
  isDeepSearchDisabled,
  onDeepSearch,
  onDisplayModeChange,
  onFiltersOpenToggle,
  onSearchChange,
  onSemanticSearch,
  onSortChange,
  search,
  sortBy,
}: {
  activeCategory: BrowseCategory;
  activeFilterCount: number;
  deepSearchBusy: boolean;
  displayMode: BrowseDisplayMode;
  filtersOpen: boolean;
  isDeepSearchDisabled: boolean;
  onDeepSearch?: () => void;
  onDisplayModeChange: (mode: BrowseDisplayMode) => void;
  onFiltersOpenToggle: () => void;
  onSearchChange: (value: string) => void;
  onSemanticSearch: (query: string) => void;
  onSortChange: (value: BrowseSortBy) => void;
  search: string;
  sortBy: BrowseSortBy;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <ToolbarSearchControl
        activeCategory={activeCategory}
        deepSearchBusy={deepSearchBusy}
        disabled={isDeepSearchDisabled}
        onDeepSearch={onDeepSearch}
        onSearchChange={onSearchChange}
        onSemanticSearch={onSemanticSearch}
        search={search}
      />
      <div className="flex flex-wrap items-center gap-2">
        <VaultSyncStatus />
        <DisplayModeControl displayMode={displayMode} onChange={onDisplayModeChange} />
        <FiltersToggleButton
          activeFilterCount={activeFilterCount}
          filtersOpen={filtersOpen}
          onToggle={onFiltersOpenToggle}
        />
        <SortSelect sortBy={sortBy} onSortChange={onSortChange} className="hidden sm:block" />
      </div>
    </div>
  );
}

export function FilterControlsPanel({
  activeFilterCount,
  controls,
  open,
  onClearAll,
  onSortChange,
  sortBy,
}: {
  activeFilterCount: number;
  controls: FilterControl[];
  open: boolean;
  onClearAll: () => void;
  onSortChange: (value: BrowseSortBy) => void;
  sortBy: BrowseSortBy;
}) {
  if (!open) return null;

  return (
    <div className="mt-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[var(--text-primary)]">Filters</div>
          <div className="text-xs text-[var(--text-secondary)]">Refine the browse surface without crowding the toolbar.</div>
        </div>
        {activeFilterCount > 0 ? (
          <button
            type="button"
            onClick={onClearAll}
            className="cursor-pointer text-xs font-medium text-[var(--text-secondary)] underline-offset-2 transition-colors duration-200 hover:text-[var(--text-primary)] hover:underline"
          >
            Reset filters
          </button>
        ) : null}
      </div>
      <div className="mb-3 grid grid-cols-1 gap-2 sm:hidden">
        <SortSelect sortBy={sortBy} onSortChange={onSortChange} className="w-full" />
      </div>
      <div
        data-testid="browse-filter-controls"
        className="flex flex-wrap items-start gap-2"
      >
        {controls.map((control) => (
          <div key={control.id} className="w-full min-w-0 sm:w-[180px]">
            {control.node}
          </div>
        ))}
      </div>
    </div>
  );
}

export function SemanticSearchStatus({
  error,
  loading,
  onRetry,
  resultCount,
  search,
  searched,
}: {
  error: string | null;
  loading: boolean;
  onRetry: () => void;
  resultCount: number;
  search: string;
  searched: boolean;
}) {
  const hasSearch = search.trim().length > 0;

  return (
    <div className="mt-2 text-sm text-[var(--text-secondary)]">
      {loading ? (
        <span className="inline-flex items-center gap-1.5">
          <Loader2 className="size-3.5 animate-spin" />
          Searching…
        </span>
      ) : resultCount > 0 ? (
        <span>Found {resultCount} results in this tab</span>
      ) : error ? (
        <span className="text-[var(--accent-warning)]">
          {error}
          {hasSearch ? (
            <button
              type="button"
              onClick={onRetry}
              className="ml-2 cursor-pointer underline hover:no-underline"
            >
              Retry
            </button>
          ) : null}
        </span>
      ) : searched && hasSearch ? (
        <span>No results found for &apos;{search}&apos;</span>
      ) : !searched && hasSearch ? (
        <span className="text-[var(--text-muted)]">Press Enter to search</span>
      ) : null}
    </div>
  );
}
