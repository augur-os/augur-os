"use client";

import { createElement, useEffect, useRef, useState } from "react";
import { Brain, ChevronDown, Plus } from "lucide-react";
import { resolveIcon } from "@/lib/icon-map";
import { formatTimeAgo, formatDateFull } from "@/lib/timestamps";
import type { BrowseOverflowMenuItem } from "@/components/shared/BrowseOverflowMenu";
import {
  selectedFolderLabel,
  type ActiveFolderContext,
  type FolderContextOption,
} from "@/lib/browse/folderContext";

export type ContextFreshness = {
  timestamp: string | null;
  level: "fresh" | "aging" | "stale" | null;
};

type BrowseFolderContextMenuProps = {
  context: ActiveFolderContext;
  options: FolderContextOption[];
  loading: boolean;
  onSelect: (context: ActiveFolderContext) => void | Promise<void>;
  onAddFolder: () => void;
  /** Index freshness for the trigger dot + the popover status line. */
  freshness?: ContextFreshness | null;
  /** Category-specific actions folded into the ACTIONS section of the popover. */
  actionItems?: BrowseOverflowMenuItem[];
  /** Accessible label for the ACTIONS section (e.g. "Notes actions"). */
  actionsLabel?: string;
};

function freshnessDotClass(level: ContextFreshness["level"]): string {
  if (level === "aging") return "bg-[var(--accent-warning)]";
  if (level === "stale") return "bg-[var(--accent-danger)]";
  return "bg-[var(--accent-success)]";
}

export function BrowseFolderContextMenu({
  context,
  options,
  loading,
  onSelect,
  onAddFolder,
  freshness,
  actionItems = [],
  actionsLabel = "Actions",
}: BrowseFolderContextMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const label = selectedFolderLabel(context);
  const hasFreshness = Boolean(freshness?.timestamp);
  const scopeOptions = options.filter((option) => option.scope !== "action");
  const addFolderOption = options.find((option) => option.scope === "action");

  useEffect(() => {
    if (!open) return;

    const handleMouseDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const handleSelect = (option: FolderContextOption) => {
    if (!isSelectableOption(option)) return;
    setOpen(false);
    if (option.scope === "all") {
      onSelect({ scope: "all", label: option.label });
      return;
    }
    if (option.scope === "unassigned") {
      onSelect({ scope: "unassigned", label: option.label });
      return;
    }
    onSelect({ scope: "brain", brain_id: option.brain_id, label: option.label });
  };

  const handleAddFolder = () => {
    setOpen(false);
    onAddFolder();
  };

  const ariaLabel = hasFreshness
    ? `Browse context: ${label}, indexed ${formatTimeAgo(freshness!.timestamp!)}`
    : `Browse context: ${label}`;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        disabled={loading}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-8 max-w-[15rem] items-center gap-1.5 rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 disabled:cursor-not-allowed disabled:opacity-50"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={ariaLabel}
        data-testid="browse-context-menu-trigger"
      >
        <Brain className="size-3.5 shrink-0 text-[var(--text-muted)]" aria-hidden="true" />
        <span className="min-w-0 truncate">{label}</span>
        {hasFreshness && (
          <span
            className={`ml-0.5 inline-block size-2 shrink-0 rounded-full ${freshnessDotClass(freshness!.level)}`}
            title={`Indexed ${formatTimeAgo(freshness!.timestamp!)}`}
            aria-hidden="true"
          />
        )}
        <ChevronDown
          className={`size-3.5 shrink-0 text-[var(--text-muted)] transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Browse context"
          className="absolute right-0 z-40 mt-2 w-72 overflow-hidden rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] shadow-xl shadow-black/20"
        >
          <div className="max-h-[28rem] overflow-y-auto py-1">
            <SectionLabel>Scope</SectionLabel>
            {scopeOptions.map((option) => (
              <FolderContextOptionButton
                key={option.id}
                option={option}
                active={isActiveOption(option, context)}
                disabled={!isSelectableOption(option)}
                onSelect={handleSelect}
              />
            ))}
            {addFolderOption && (
              <button
                type="button"
                role="menuitem"
                onClick={handleAddFolder}
                className="flex min-h-9 w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:bg-[var(--bg-hover)] focus-visible:outline-none"
              >
                <Plus className="size-3.5 shrink-0 text-[var(--text-muted)]" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate">{addFolderOption.label}</span>
              </button>
            )}

            {(hasFreshness || actionItems.length > 0) && (
              <div className="my-1 border-t border-[var(--border-color)]" role="separator" />
            )}

            {(hasFreshness || actionItems.length > 0) && <SectionLabel>{actionsLabel}</SectionLabel>}

            {hasFreshness && (
              <div
                className="flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--text-tertiary)]"
                title={formatDateFull(freshness!.timestamp!)}
              >
                <span
                  className={`inline-block size-2 shrink-0 rounded-full ${freshnessDotClass(freshness!.level)}`}
                  aria-hidden="true"
                />
                <span className="min-w-0 truncate">Indexed {formatTimeAgo(freshness!.timestamp!)}</span>
              </div>
            )}

            {actionItems.map((item) => (
              <button
                key={item.id}
                type="button"
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  setOpen(false);
                  void item.onSelect();
                }}
                className={`flex min-h-9 w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium transition-colors focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
                  item.variant === "danger"
                    ? "text-[var(--accent-danger)] hover:bg-[var(--accent-danger)]/10 focus-visible:bg-[var(--accent-danger)]/10"
                    : "text-[var(--text-primary)] hover:bg-[var(--bg-hover)] focus-visible:bg-[var(--bg-hover)]"
                }`}
              >
                {createElement(resolveIcon(item.icon), {
                  className: "size-3.5 shrink-0 text-[var(--text-muted)]",
                  "aria-hidden": "true",
                })}
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
      {children}
    </div>
  );
}

// Folder health states need to read as actionable problems, not passive grey
// chips. Each carries a semantic colour + an explanation of what selecting the
// folder will do (the select handler repairs/initializes server-side).
const FOLDER_STATE_META: Record<string, { badgeClass: string; title: string }> = {
  repairable: {
    badgeClass: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
    title: "This folder's index needs repair — select it to fix and switch to it.",
  },
  unregistered: {
    badgeClass: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
    title: "This folder isn't set up yet — select it to initialize it.",
  },
  missing: {
    badgeClass: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
    title: "This folder's data can't be found, so it can't be opened.",
  },
};

function FolderContextOptionButton({
  option,
  active,
  disabled,
  onSelect,
}: {
  option: FolderContextOption;
  active: boolean;
  disabled: boolean;
  onSelect: (option: FolderContextOption) => void;
}) {
  const stateMeta = option.state ? FOLDER_STATE_META[option.state] : undefined;
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={active}
      disabled={disabled}
      onClick={() => onSelect(option)}
      title={stateMeta?.title}
      className="flex min-h-9 w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:bg-[var(--bg-hover)] focus-visible:bg-[var(--bg-hover)] focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span
        className={`size-2 shrink-0 rounded-full border ${
          active
            ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]"
            : "border-[var(--border-color)]"
        }`}
        aria-hidden="true"
      />
      <span className="min-w-0 flex-1 truncate font-medium text-[var(--text-primary)]">{option.label}</span>
      <span className="flex min-w-[3.5rem] shrink-0 items-center justify-end gap-1.5">
        {typeof option.count === "number" && (
          <span className="tabular-nums text-[var(--text-muted)]">{option.count}</span>
        )}
        {option.badge && (
          <span
            className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
              stateMeta?.badgeClass ??
              "border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-muted)]"
            }`}
          >
            {option.badge}
          </span>
        )}
      </span>
    </button>
  );
}

function isActiveOption(option: FolderContextOption, context: ActiveFolderContext): boolean {
  if (option.scope === "all") return context.scope === "all";
  if (option.scope === "unassigned") return context.scope === "unassigned";
  if (option.scope === "brain") return context.scope === "brain" && option.brain_id === context.brain_id;
  return false;
}

function isSelectableOption(option: FolderContextOption): option is FolderContextOption & { scope: "all" | "brain" | "unassigned" } {
  if (option.disabled) return false;
  if (option.scope !== "all" && option.scope !== "brain" && option.scope !== "unassigned") return false;
  if (option.state === "missing" || option.state === "unregistered") return false;
  if (option.scope === "brain" && !option.brain_id) return false;
  return true;
}
