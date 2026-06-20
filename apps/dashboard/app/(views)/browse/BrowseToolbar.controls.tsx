"use client";

import { BrainCircuit, Grid2x2Plus, List, Loader2, Search, SlidersHorizontal } from "lucide-react";
import { type BrowseCategory, type BrowsePageKindFilter } from "@/lib/browse/types";
import type { BrowseSortBy } from "@/lib/browse/pinOrdering";
import type { BrowseDisplayMode } from "@/lib/browse/displayMode";
import { selectClass, selectActiveClass, PAGE_KIND_OPTIONS } from "./BrowseToolbar.helpers";

export function FilterSelect({
  label,
  value,
  onChange,
  options,
  ariaLabel,
  showWhenSingle = false,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  options: { id: string; label: string }[];
  ariaLabel?: string;
  showWhenSingle?: boolean;
}) {
  if (options.length === 0 || (!showWhenSingle && options.length <= 1)) return null;
  const selectOptions = options.some((option) => option.id === "all")
    ? options
    : [{ id: "all", label: `${label}: All` }, ...options];
  const hasFilter = value !== null;
  return (
    <select
      value={value ?? "all"}
      onChange={(event) => onChange(event.target.value === "all" ? null : event.target.value)}
      aria-label={ariaLabel ?? `Filter by ${label}`}
      className={`${hasFilter ? selectActiveClass : selectClass} w-full`}
    >
      {selectOptions.map((option) => (
        <option key={option.id} value={option.id}>
          {option.id === "all" ? `${label}: All` : option.label}
        </option>
      ))}
    </select>
  );
}

export function KindSegmentedControl({
  value,
  onChange,
}: {
  value: BrowsePageKindFilter;
  onChange: (value: BrowsePageKindFilter) => void;
}) {
  return (
    <fieldset className="m-0 inline-flex min-h-[44px] w-full min-w-0 overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-1">
      <legend className="sr-only">Filter pages by kind</legend>
      {PAGE_KIND_OPTIONS.map((option) => {
        const active = value === option.id;
        return (
          <button
            key={option.id}
            type="button"
            onClick={() => onChange(option.id)}
            className={`min-w-0 flex-1 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
              active
                ? "bg-[var(--accent-primary)] text-white"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            }`}
            aria-pressed={active}
          >
            {option.label}
          </button>
        );
      })}
    </fieldset>
  );
}

export function ToolbarSearchControl({
  activeCategory,
  deepSearchBusy,
  disabled,
  onDeepSearch,
  onSearchChange,
  onSemanticSearch,
  search,
}: {
  activeCategory: BrowseCategory;
  deepSearchBusy: boolean;
  disabled: boolean;
  onDeepSearch?: () => void;
  onSearchChange: (value: string) => void;
  onSemanticSearch: (query: string) => void;
  search: string;
}) {
  return (
    <div className="flex min-w-[14rem] flex-1 items-center gap-2">
      <div className="relative min-w-0 flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-[var(--text-secondary)]" />
        <input
          id="browse-search"
          type="text"
          placeholder={`Search ${activeCategory.label.toLowerCase()}... (/)`}
          aria-label={`Search ${activeCategory.label.toLowerCase()}`}
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onSemanticSearch(search);
            }
          }}
          className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] py-2.5 pl-10 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        />
      </div>
      <button
        type="button"
        onClick={onDeepSearch}
        disabled={disabled}
        aria-label="Ask AI"
        title={disabled ? "Type a query first, then Ask AI" : "Ask AI about these results (opens chat)"}
        className="inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] transition-colors duration-200 hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {deepSearchBusy ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <BrainCircuit className="size-4" aria-hidden="true" />
        )}
      </button>
    </div>
  );
}

export function DisplayModeControl({
  displayMode,
  onChange,
}: {
  displayMode: BrowseDisplayMode;
  onChange: (mode: BrowseDisplayMode) => void;
}) {
  return (
    <fieldset className="m-0 inline-flex min-h-[44px] min-w-0 overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-1">
      <legend className="sr-only">Display mode</legend>
      <button
        type="button"
        aria-label="Card mode"
        aria-pressed={displayMode === "card"}
        onClick={() => onChange("card")}
        className={`inline-flex items-center rounded-md px-2 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
          displayMode === "card"
            ? "bg-[var(--accent-primary)] text-white"
            : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
        }`}
      >
        <Grid2x2Plus className="size-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        aria-label="List mode"
        aria-pressed={displayMode === "list"}
        onClick={() => onChange("list")}
        className={`inline-flex items-center rounded-md px-2 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
          displayMode === "list"
            ? "bg-[var(--accent-primary)] text-white"
            : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
        }`}
      >
        <List className="size-4" aria-hidden="true" />
      </button>
    </fieldset>
  );
}

export function FiltersToggleButton({
  activeFilterCount,
  filtersOpen,
  onToggle,
}: {
  activeFilterCount: number;
  filtersOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={filtersOpen}
      aria-label={`${filtersOpen ? "Hide" : "Show"} filters`}
      className={`inline-flex min-h-[44px] cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-2.5 text-xs font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
        activeFilterCount > 0
          ? "border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
          : "border-[var(--border-primary)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
      }`}
    >
      <SlidersHorizontal className="size-4" />
      <span>Filters</span>
      <span className="tabular-nums">{activeFilterCount}</span>
    </button>
  );
}

export function SortSelect({
  className = "",
  onSortChange,
  sortBy,
}: {
  className?: string;
  onSortChange: (value: BrowseSortBy) => void;
  sortBy: BrowseSortBy;
}) {
  return (
    <select
      value={sortBy}
      onChange={(event) => onSortChange(event.target.value as BrowseSortBy)}
      aria-label="Sort order"
      className={`${className} ${selectClass}`}
    >
      <option value="default">Default</option>
      <option value="name-asc">Name (A-Z)</option>
      <option value="name-desc">Name (Z-A)</option>
      <option value="rank-desc">By Rank</option>
      <option value="modified-desc">Newest First</option>
      <option value="modified-asc">Oldest First</option>
    </select>
  );
}
