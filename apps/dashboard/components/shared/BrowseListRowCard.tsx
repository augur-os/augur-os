"use client";

import React from "react";
import { resolveIcon as resolveIconFromMap } from "@/lib/icon-map";
import type { BrowseCardBadge, BrowseCardModel } from "@/lib/browse/cardModel";
import { visibleCardMetadataRows } from "@/lib/browse/cardModel";
import {
  aiItemActionsFor,
  directItemActionsFor,
  type AiItemActionItem,
  type DirectItemAction,
} from "@/lib/browse/itemActions";
import { BrowseOverflowMenu, type BrowseOverflowMenuItem } from "./BrowseOverflowMenu";
import { BrowsePinButton } from "./BrowsePinButton";

interface BrowseListRowCardProps {
  model: BrowseCardModel;
  selected?: boolean;
  pinned?: boolean;
  onPin?: () => void;
  onSelect?: () => void;
  onPrimaryAction?: () => void | Promise<void>;
  onAction?: (actionId: string) => void | Promise<void>;
  onPolicy?: () => void;
  selectionMode?: boolean;
  isMultiSelected?: boolean;
  onToggleMultiSelect?: () => void;
  /** Active BrowseCategory id — selects this card's per-category AI actions. */
  category?: string;
  /** Hands a resolved, item-aware prompt to the chat as an editable draft. */
  onItemPrompt?: (prompt: string) => void;
  /** Runs a generated direct MCP action against this item. */
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
}

const BADGE_TONE_CLASSES: Record<NonNullable<BrowseCardBadge["tone"]>, string> = {
  neutral: "border-[var(--border-color)] bg-[var(--bg-primary)] text-[var(--text-secondary)]",
  success: "border-[var(--accent-success)]/25 bg-[var(--accent-success)]/10 text-[var(--accent-success)]",
  warning: "border-[var(--accent-warning)]/25 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)]",
  danger: "border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 text-[var(--accent-danger)]",
  info: "border-[var(--accent-info)]/25 bg-[var(--accent-info)]/10 text-[var(--accent-info)]",
  "note-url": "border-cyan-500/25 bg-cyan-500/10 text-cyan-500",
  "note-file": "border-slate-500/25 bg-slate-500/10 text-slate-400",
  "note-thought": "border-amber-500/25 bg-amber-500/10 text-amber-500",
  "note-voice-memo": "border-violet-500/25 bg-violet-500/10 text-violet-500",
  "note-meeting": "border-sky-500/25 bg-sky-500/10 text-sky-500",
  "note-image": "border-emerald-500/25 bg-emerald-500/10 text-emerald-500",
  "note-prompt": "border-rose-500/25 bg-rose-500/10 text-rose-500",
};

function ResolvedIcon({ name, className }: { name: string; className?: string }) {
  return React.createElement(resolveIconFromMap(name), { className });
}

function badgeClass(tone: BrowseCardBadge["tone"]): string {
  return BADGE_TONE_CLASSES[tone ?? "neutral"];
}

function stopKeyPropagation(event: React.KeyboardEvent<HTMLElement>) {
  event.stopPropagation();
}

function selectFromContainerKey(
  event: React.KeyboardEvent<HTMLElement>,
  onSelect: (() => void) | undefined,
) {
  if (!onSelect || (event.key !== "Enter" && event.key !== " " && event.key !== "Spacebar")) return;
  event.preventDefault();
  onSelect();
}

export function BrowseListRowCard({
  model,
  selected = false,
  pinned = false,
  onPin,
  onSelect,
  onPrimaryAction,
  onAction,
  onPolicy,
  selectionMode = false,
  isMultiSelected = false,
  onToggleMultiSelect,
  category,
  onItemPrompt,
  onItemDirect,
}: BrowseListRowCardProps) {
  const hasPolicy = Boolean(model.rawItem.metadata?.capabilityId && onPolicy);
  // Per-category AI actions ride the same overflow menu as the panel's buttons;
  // each hands a resolved, item-aware prompt to the chat as an editable draft.
  const aiActions = onItemPrompt ? aiItemActionsFor(category, model.rawItem) : [];
  const directActions = onItemDirect ? directItemActionsFor(category, model.rawItem) : [];
  const overflowItems: BrowseOverflowMenuItem[] = [
    ...model.overflowActions.map((action) => ({
      id: action.id,
      label: action.label,
      icon: action.icon,
      variant: action.variant,
      onSelect: () => onAction?.(action.id),
    })),
    ...aiActions.map((action) => ({
      id: `ai:${action.id}`,
      label: action.label,
      icon: action.icon,
      onSelect: () => onItemPrompt?.(action.template(model.rawItem)),
    })),
    ...directActions.map((action) => ({
      id: `direct:${action.id}`,
      label: action.label,
      icon: action.icon,
      onSelect: () => onItemDirect?.(action, model.rawItem),
    })),
  ];
  const visibleBadges = model.badges.slice(0, 4);
  const hiddenBadges = model.badges.slice(4);
  const metadataRows = visibleCardMetadataRows(model);

  const effectivelySelected = selectionMode ? isMultiSelected : selected;
  const interactive = selectionMode || Boolean(onSelect);

  return (
    <div
      data-testid="browse-list-row-card"
      tabIndex={selectionMode || !onSelect ? undefined : 0}
      aria-label={model.title}
      onClick={selectionMode ? undefined : onSelect}
      onKeyDown={(event) => selectFromContainerKey(event, onSelect)}
      className={`relative z-0 grid min-h-[76px] grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-xl border bg-[var(--bg-secondary)]/95 p-3 shadow-sm transition-[border-color,box-shadow,transform] duration-200 hover:z-10 focus-within:z-40 hover:border-[var(--accent-primary)]/35 hover:shadow-md md:grid-cols-[auto_minmax(0,1.2fr)_minmax(160px,0.8fr)_auto] md:items-center ${
        effectivelySelected
          ? "border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]/25"
          : "border-[var(--border-color)]"
      } ${interactive ? "cursor-pointer active:scale-[0.995]" : ""}`}
    >
      {selectionMode ? (
        <>
          <button
            type="button"
            data-testid="browse-list-row-select-overlay"
            aria-label={`${isMultiSelected ? "Deselect" : "Select"} ${model.title}`}
            aria-pressed={isMultiSelected}
            onClick={onToggleMultiSelect}
            className="absolute inset-0 z-10 cursor-pointer rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          />
          <input
            type="checkbox"
            data-testid="browse-list-row-checkbox"
            checked={isMultiSelected}
            readOnly
            tabIndex={-1}
            aria-hidden="true"
            className="pointer-events-none absolute right-3 top-3 z-20 size-4 accent-[var(--accent-primary)]"
          />
        </>
      ) : null}
      <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)]/70 text-[var(--accent-primary)]">
        <ResolvedIcon name={model.icon} className="size-5" />
      </div>

      <div className="min-w-0">
        <button
          type="button"
          aria-label={model.title}
          onClick={(event) => {
            event.stopPropagation();
            onSelect?.();
          }}
          onKeyDown={stopKeyPropagation}
          className="block w-full cursor-pointer truncate text-left text-sm font-semibold text-[var(--text-primary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          dir="auto"
        >
          {model.title}
        </button>
        <p className="mt-0.5 line-clamp-1 text-xs leading-5 text-[var(--text-secondary)]" dir="auto">
          {model.description || model.path || "No description"}
        </p>
      </div>

      <div className="col-span-2 flex min-w-0 flex-wrap items-center gap-1.5 md:col-span-1">
        {visibleBadges.map((badge) => (
          <span
            key={badge.id}
            className={`inline-flex max-w-[12rem] items-center gap-1 truncate rounded-full border px-2 py-0.5 text-[11px] font-medium ${badgeClass(badge.tone)}`}
            title={badge.label}
          >
            {badge.icon ? <ResolvedIcon name={badge.icon} className="size-3 shrink-0" /> : null}
            <span className="truncate">{badge.label}</span>
          </span>
        ))}
        {hiddenBadges.length > 0 ? (
          <span
            className="inline-flex rounded-full border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-muted)]"
            title={hiddenBadges.map((badge) => badge.label).join(", ")}
          >
            +{hiddenBadges.length} more
          </span>
        ) : null}
        {metadataRows.slice(0, 2).map((row) => (
          <span
            key={`${row.label}-${row.value}`}
            className="max-w-[14rem] truncate text-[11px] text-[var(--text-muted)]"
            title={`${row.label}: ${row.value}`}
            dir="auto"
          >
            <span className="font-medium text-[var(--text-secondary)]">{row.label}:</span> {row.value}
          </span>
        ))}
      </div>

      <div className={`col-span-2 flex flex-wrap items-center gap-2 md:col-span-1 md:justify-end ${selectionMode ? "md:pr-8" : ""}`}>
        {onPin ? <BrowsePinButton title={model.title} pinned={pinned} onToggle={onPin} /> : null}
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            void onPrimaryAction?.();
          }}
          onKeyDown={stopKeyPropagation}
          className="inline-flex min-h-[34px] cursor-pointer items-center rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 py-1.5 text-xs font-semibold text-[var(--accent-primary)] transition-colors hover:bg-[var(--accent-primary)]/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          {model.primaryAction.label}
        </button>
        {hasPolicy ? (
          <button
            type="button"
            aria-label={`Review policy for ${model.title}`}
            onClick={(event) => {
              event.stopPropagation();
              onPolicy?.();
            }}
            onKeyDown={stopKeyPropagation}
            className="inline-flex min-h-[34px] cursor-pointer items-center rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          >
            Policy
          </button>
        ) : null}
        <BrowseOverflowMenu
          items={overflowItems}
          buttonLabel="More actions"
          menuLabel={`${model.title} actions`}
          stopPropagation
          buttonTestId="browse-list-row-overflow"
        />
      </div>
    </div>
  );
}
