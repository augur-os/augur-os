"use client";
// Entry/barrel for the Browse file-card surface. The four public components
// (BrowseCard, BrowseCardSkeleton, BrowseEmptyState, BrowseErrorState) live or
// re-export from here. Pure helpers and badge rendering are extracted into the
// leaf modules ./BrowseCard.helpers and ./BrowseCard.badges (no cycle: those
// never import this file).

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { mcpCall } from "@/lib/mcp/client";
import type { BrowseItem, BrowseCardAction, BrowseCategory } from "@/lib/browse/types";
import { executeBrowseAction } from "@/lib/browse/executeAction";
import { BrowseOverflowMenu } from "./BrowseOverflowMenu";
import { BrowsePinButton } from "./BrowsePinButton";
import { BrowsePromptTrigger } from "./BrowsePromptTrigger";
import { ResolvedIcon, BrowseBadges } from "./BrowseCard.badges";
import {
  NOTE_TYPE_LABELS,
  NOTE_TYPE_ICONS,
  NOTE_TYPE_CLASSES,
  noteTypeForCard,
  noteMetadataSegments,
  enrichmentBadgeForCard,
  itemPageTags,
  isWikiPageItem,
  kindChipClass,
} from "./BrowseCard.helpers";

/* ------------------------------------------------------------------ */
/*  BrowseCard                                                         */
/* ------------------------------------------------------------------ */

interface BrowseCardProps {
  item: BrowseItem;
  onRunMcp?: (target: string) => void;
  onSelect?: () => void;
  isPinned?: boolean;
  onTogglePin?: () => void;
  /** ADR-748: dispatches a resolved prompt body to the CLI chat window. */
  onTriggerPrompt?: (resolvedPrompt: string) => void;
}

export function BrowseCard({
  item,
  onRunMcp,
  onSelect,
  isPinned = false,
  onTogglePin,
  onTriggerPrompt,
}: BrowseCardProps) {
  const router = useRouter();
  const [cliHelp, setCliHelp] = useState<string | null>(null);
  const [cliLoading, setCliLoading] = useState(false);

  const handleAction = async (action: BrowseCardAction | BrowseItem["primaryAction"]) => {
    await executeBrowseAction(action, {
      router,
      onRunMcp,
      onCliHelp: async (target) => {
        if (cliHelp !== null) {
          setCliHelp(null);
          return;
        }
        if (!target) return;
        setCliLoading(true);
        try {
          const data = await mcpCall<{ markdown?: string }>("cli-help", { tools: target });
          setCliHelp(data.markdown || "No output.");
        } catch {
          toast.error("Failed to fetch CLI help");
        } finally {
          setCliLoading(false);
        }
      },
    });
  };

  const handleReveal = async () => {
    if (!item.path) return;
    try {
      const info = await mcpCall<{ exists: boolean }>("file-info", { path: item.path }, { fallback: { exists: false } });
      if (!info.exists) {
        toast.error(`File not found: ${item.path.split("/").pop()}`);
        return;
      }
      const data = await mcpCall<{ success: boolean; error?: string }>("reveal-in-finder", { path: item.path });
      if (!data.success) toast.error(data.error || "Failed to reveal file");
    } catch {
      toast.error("Failed to reveal in Finder");
    }
  };

  const handleCardClick = () => {
    if (onSelect) {
      onSelect();
    }
  };

  const revealActionId = `reveal-${item.id}`;
  const hasExplicitRevealAction = item.actions?.some((action) => (
    action.target === item.path &&
    (
      action.type === "reveal-file" ||
      action.id === revealActionId ||
      action.label.toLowerCase().startsWith("reveal")
    )
  ));
  const pageTags = itemPageTags(item);
  const isWikiItem = isWikiPageItem(item);
  const noteType = noteTypeForCard(item);
  const NoteTypeIcon = noteType ? NOTE_TYPE_ICONS[noteType] : null;
  const noteMetadata = noteMetadataSegments(item);
  const enrichmentBadge = enrichmentBadgeForCard(item, noteType);

  const overflowActions = [
    ...(onTogglePin ? [{
      id: `pin-${item.id}`,
      label: isPinned ? "Unpin" : "Pin",
      icon: "Pin",
      onSelect: () => onTogglePin(),
    }] : []),
    ...(item.path && !hasExplicitRevealAction ? [{
      id: `reveal-${item.id}`,
      label: "Reveal in Finder",
      icon: "FolderOpen",
      onSelect: () => handleReveal(),
    }] : []),
    ...((item.actions ?? []).map((action) => ({
      id: action.id,
      label: action.label,
      icon: action.icon,
      variant: action.variant,
      onSelect: () => handleAction(action),
    }))),
  ];

  return (
    <div
      className="rounded-2xl border border-[var(--border-color)] border-l-[3px] border-l-[var(--border-color)] bg-[var(--bg-secondary)]/95 p-4 shadow-sm transition-[box-shadow,border-color,transform] duration-200 hover:border-[var(--accent-primary)]/35 hover:shadow-md min-h-[168px]"
      data-testid="browse-card"
    >
      <div className="mb-3 flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)]/70">
          <ResolvedIcon name={item.icon} className="size-[18px] text-[var(--accent-primary)]" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
            {noteType && NoteTypeIcon ? (
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] ${NOTE_TYPE_CLASSES[noteType]}`}
                data-testid="browse-note-type-badge"
              >
                <NoteTypeIcon className="size-3" />
                {NOTE_TYPE_LABELS[noteType]}
              </span>
            ) : item.typeBadge && (
              <span className="rounded-full border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">
                {item.typeBadge}
              </span>
            )}
            {item.metadata?.kind && (
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] ${kindChipClass(item.metadata.kind)}`}>
                {item.metadata.kind}
              </span>
            )}
            {item.metadata?.archived === "true" && (
              <span
                className="rounded-full border border-[var(--border-color)] bg-[var(--bg-primary)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]"
                data-testid="browse-archived-chip"
              >
                archived
              </span>
            )}
            {isWikiItem && pageTags.slice(0, 2).map((tag) => (
              <span key={tag} className="rounded-full bg-[var(--accent-info)]/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--accent-info)]">
                {tag}
              </span>
            ))}
          </div>
          <div className="flex items-start justify-between gap-2">
            {onSelect ? (
              <button
                type="button"
                onClick={handleCardClick}
                className="line-clamp-2 cursor-pointer border-0 bg-transparent p-0 text-left text-[15px] font-semibold leading-5 text-[var(--text-primary)] transition-colors hover:text-[var(--accent-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
              >
                {item.title}
              </button>
            ) : (
              <h3 className="line-clamp-2 text-[15px] font-semibold leading-5 text-[var(--text-primary)]">
                {item.title}
              </h3>
            )}
            {onTogglePin && (
              <BrowsePinButton
                title={item.title}
                pinned={isPinned}
                onToggle={onTogglePin}
              />
            )}
          </div>
          {(noteMetadata.length > 0 || enrichmentBadge) && (
            <div
              className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] leading-4 text-[var(--text-muted)]"
              data-testid="browse-note-metadata"
            >
              {noteMetadata.map((segment, index) => (
                <React.Fragment key={segment}>
                  {index > 0 && <span aria-hidden="true">|</span>}
                  <span>{segment}</span>
                </React.Fragment>
              ))}
              {noteMetadata.length > 0 && enrichmentBadge && <span aria-hidden="true">|</span>}
              {enrichmentBadge && (
                <span
                  className={`inline-flex items-center rounded-full border px-1.5 py-0 text-[10px] font-semibold leading-4 ${enrichmentBadge.className}`}
                  data-testid="browse-enrichment-status-badge"
                  title={enrichmentBadge.title}
                >
                  {enrichmentBadge.label}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <p className="mb-3 min-h-[2.25rem] line-clamp-2 text-[13px] leading-5 text-[var(--text-secondary)]">
        {item.description || (
          <span className="text-[var(--text-muted)] italic">
            {item.path || "No description"}
          </span>
        )}
      </p>

      {/* Badges */}
      <BrowseBadges item={item} />

      {/* CLI tool status rows (integrations only) */}
      {item.cliTools && item.cliTools.length > 0 && (
        <div className="mb-3 space-y-1">
          {item.cliTools.map((cli) => (
            <div key={cli.name} className="flex items-center gap-2 text-[11px]">
              <span className="font-mono font-medium text-[var(--text-primary)] min-w-[4rem]">{cli.name}</span>
              {cli.installed ? (
                <>
                  <span className={`px-1.5 py-0.5 rounded text-[11px] font-medium ${
                    cli.configured === false
                      ? "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]"
                      : cli.configured === null && cli.install_hint?.startsWith("Built-in")
                        ? "bg-[var(--accent-success)]/15 text-[var(--accent-success)]"
                        : cli.configured === null
                          ? "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]"
                          : "bg-[var(--accent-success)]/15 text-[var(--accent-success)]"
                  }`}>
                    {cli.configured === true ? "Configured" :
                     cli.configured === false ? "Not Configured" :
                     cli.install_hint?.startsWith("Built-in") ? "Installed" :
                     "Config Unknown"}
                  </span>
                  {cli.version && (
                    <span className="text-[var(--text-muted)]">v{cli.version}</span>
                  )}
                </>
              ) : (
                <span className="px-1.5 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-danger)]/15 text-[var(--accent-danger)]">
                  Not Installed
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button type="button"
          onClick={(e) => {
            e.stopPropagation();
            void handleAction(item.primaryAction);
          }}
          disabled={cliLoading}
          className="min-h-[36px] cursor-pointer rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 py-2 text-xs font-semibold text-[var(--accent-primary)] transition-colors duration-200 hover:bg-[var(--accent-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="browse-card-action"
        >
          {cliLoading ? "Loading..." : cliHelp !== null ? "Hide" : item.primaryAction.label}
        </button>
        {/* ADR-748: Trigger button on prompt cards — dispatches the resolved
            prompt body to the CLI chat window. Gated on metadata.prompt, which
            the Browse transform sets only for prompt items (ADR-748 Task 6). */}
        {onTriggerPrompt && item.metadata?.prompt ? (
          <BrowsePromptTrigger
            promptBody={item.metadata.prompt}
            placeholders={(item.metadata.placeholders ?? "")
              .split(",")
              .flatMap((slot) => {
                const trimmed = slot.trim();
                return trimmed ? [trimmed] : [];
              })}
            onTrigger={onTriggerPrompt}
          />
        ) : null}
        <BrowseOverflowMenu
          items={overflowActions}
          buttonLabel="More actions"
          menuLabel={`${item.title} actions`}
          stopPropagation
          className="ml-auto"
          buttonTestId="browse-card-overflow"
        />
      </div>

      {/* CLI help output */}
      {cliHelp !== null && (
        <div className="mt-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-color)] p-3 max-h-[400px] overflow-y-auto custom-scrollbar">
          <pre className="text-[11px] text-[var(--text-secondary)] whitespace-pre-wrap font-mono leading-relaxed">
            {cliHelp}
          </pre>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  BrowseCardSkeleton                                                 */
/* ------------------------------------------------------------------ */

export function BrowseCardSkeleton() {
  return (
    <div
      className="p-5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)] border-l-[3px] border-l-[var(--border-color)] animate-pulse min-h-[180px]"
      data-testid="browse-card-skeleton"
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="size-4 rounded bg-[var(--bg-primary)]" />
        <div className="h-4 w-32 rounded bg-[var(--bg-primary)]" />
      </div>
      <div className="h-3 w-full rounded bg-[var(--bg-primary)] mb-1" />
      <div className="h-3 w-2/3 rounded bg-[var(--bg-primary)] mb-3" />
      <div className="flex items-center gap-2 mb-3">
        <div className="h-4 w-16 rounded bg-[var(--bg-primary)]" />
        <div className="h-4 w-12 rounded bg-[var(--bg-primary)]" />
      </div>
      <div className="h-6 w-20 rounded bg-[var(--bg-primary)]" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  BrowseEmptyState                                                   */
/* ------------------------------------------------------------------ */

interface BrowseEmptyStateProps {
  category: BrowseCategory;
  search?: string;
  hint?: string;
  action?: {
    label: string;
    onSelect: () => void;
  };
}

export function BrowseEmptyState({
  category,
  search,
  hint,
  action,
}: BrowseEmptyStateProps) {
  return (
    <div
      className="text-center py-12"
      data-testid="browse-empty-state"
    >
      <ResolvedIcon name={category.icon} className="size-8 text-[var(--text-secondary)] mx-auto mb-3" />
      <p className="text-sm text-[var(--text-secondary)]">
        No {category.label.toLowerCase()} found
      </p>
      {search && (
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          Try a different search term
        </p>
      )}
      {!search && hint && (
        <p className="text-xs text-[var(--text-muted)] mt-2">
          {hint}
        </p>
      )}
      {!search && !hint && (
        <p className="text-xs text-[var(--text-muted)] mt-2">
          Try switching categories or adjusting filters above
        </p>
      )}
      {!search && action && (
        <button
          type="button"
          onClick={action.onSelect}
          className="mt-4 inline-flex h-9 items-center justify-center rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)] px-3 text-xs font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  BrowseErrorState                                                   */
/* ------------------------------------------------------------------ */

interface BrowseErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function BrowseErrorState({ message, onRetry }: BrowseErrorStateProps) {
  return (
    <div
      className="text-center py-12"
      data-testid="browse-error-state"
    >
      <AlertCircle className="size-8 text-[var(--accent-danger)] mx-auto mb-3" />
      <p className="text-sm text-[var(--text-primary)] mb-3">{message}</p>
      {onRetry && (
        <button type="button"
          onClick={onRetry}
          className="px-4 py-1.5 rounded-lg text-sm font-medium bg-[var(--accent-primary)] text-white hover:opacity-90 transition-opacity cursor-pointer"
          data-testid="browse-error-retry"
        >
          Retry
        </button>
      )}
    </div>
  );
}
