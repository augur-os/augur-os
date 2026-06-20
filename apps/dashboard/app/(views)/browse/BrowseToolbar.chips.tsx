"use client";

import { X } from "lucide-react";
import type { FilterChip, FilterOption } from "./BrowseToolbar.types";

export function ActiveFilterChips({
  chips,
  onClearAll,
}: {
  chips: FilterChip[];
  onClearAll: () => void;
}) {
  if (chips.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <button
          key={chip.id}
          type="button"
          onClick={chip.onClear}
          className="inline-flex min-h-[32px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--accent-primary)]/20 bg-[var(--accent-primary)]/10 px-2.5 py-1 text-xs font-medium text-[var(--accent-primary)] transition-colors duration-200 hover:bg-[var(--accent-primary)]/15"
        >
          <span>{chip.label}</span>
          <X className="size-3" />
        </button>
      ))}
      <button
        type="button"
        onClick={onClearAll}
        className="cursor-pointer text-xs font-medium text-[var(--text-secondary)] underline-offset-2 transition-colors duration-200 hover:text-[var(--text-primary)] hover:underline"
      >
        Clear all
      </button>
    </div>
  );
}

export function NotesTypeFilterControl({
  onChange,
  options,
  value,
}: {
  onChange: (type: string | null) => void;
  options: FilterOption[];
  value: string | null;
}) {
  const typeOptions = options.filter((option) => option.id !== "all");
  if (typeOptions.length === 0) return null;

  const selectedTypes = new Set(
    (value ?? "")
      .split(",")
      .flatMap((type) => {
        const trimmed = type.trim();
        return trimmed ? [trimmed] : [];
      }),
  );
  const updateType = (type: string) => {
    const nextTypes = new Set(selectedTypes);
    if (nextTypes.has(type)) {
      nextTypes.delete(type);
    } else {
      nextTypes.add(type);
    }
    const next = typeOptions
      .map((option) => option.id)
      .filter((candidate) => nextTypes.has(candidate));
    onChange(next.length > 0 ? next.join(",") : null);
  };

  return (
    <fieldset className="m-0 flex min-h-[44px] w-full min-w-0 flex-wrap items-center gap-1 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-1">
      <legend className="sr-only">Filter by Type</legend>
      <span className="w-full px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
        Type
      </span>
      <button
        type="button"
        aria-pressed={selectedTypes.size === 0}
        onClick={() => onChange(null)}
        className={`min-h-[32px] rounded-md px-2 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
          selectedTypes.size === 0
            ? "bg-[var(--accent-primary)] text-white"
            : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
        }`}
      >
        All
      </button>
      {typeOptions.map((option) => {
        const active = selectedTypes.has(option.id);
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            onClick={() => updateType(option.id)}
            className={`min-h-[32px] rounded-md px-2 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
              active
                ? "bg-[var(--accent-primary)] text-white"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </fieldset>
  );
}

export function NotesCategoryFilterChips({
  activeCategory,
  onChange,
  options,
  show,
}: {
  activeCategory: string | null;
  onChange: (category: string | null) => void;
  options: FilterOption[];
  show: boolean;
}) {
  if (!show) return null;
  const categoryOptions = options.filter((option) => option.id !== "all");
  if (categoryOptions.length === 0) return null;

  return (
    <fieldset className="mt-3 flex flex-wrap items-center gap-2">
      <legend className="sr-only">Filter notes by category</legend>
      <span className="mr-1 px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
        Category
      </span>
      <button
        type="button"
        aria-pressed={activeCategory === null}
        onClick={() => onChange(null)}
        className={`inline-flex min-h-[32px] items-center rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
          activeCategory === null
            ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
            : "border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
        }`}
      >
        All
      </button>
      {categoryOptions.map((option) => {
        const active = activeCategory === option.id;
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.id)}
            className={`inline-flex min-h-[32px] items-center rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
              active
                ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
                : "border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
              }`}
          >
            {option.label}
          </button>
        );
      })}
    </fieldset>
  );
}

export function NotesStateFilterChips({
  activeState,
  onChange,
  options,
  show,
}: {
  activeState: string | null;
  onChange: (state: string | null) => void;
  options: FilterOption[];
  show: boolean;
}) {
  if (!show) return null;
  const stateOptions = options.filter((option) => option.id !== "all");
  if (stateOptions.length === 0) return null;

  return (
    <fieldset className="mt-3 flex flex-wrap items-center gap-2">
      <legend className="sr-only">Filter notes by state</legend>
      <span className="mr-1 px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
        State
      </span>
      <button
        type="button"
        aria-pressed={activeState === null}
        onClick={() => onChange(null)}
        className={`inline-flex min-h-[32px] items-center rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
          activeState === null
            ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
            : "border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
        }`}
      >
        All
      </button>
      {stateOptions.map((option) => {
        const active = activeState === option.id;
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(active ? null : option.id)}
            className={`inline-flex min-h-[32px] items-center rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
              active
                ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
                : "border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </fieldset>
  );
}
