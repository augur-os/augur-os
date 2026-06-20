"use client";

import { useRef, useEffect, useState, useMemo, useSyncExternalStore } from "react";
import type { ReactNode, SyntheticEvent } from "react";
import type { ViewMode, BrowseItem, BrowseCategory } from "@/lib/browse/types";
import type { BrowseDisplayMode } from "@/lib/browse/displayMode";
import type { BrowseChatResult } from "@/lib/browse/executeAction";
import type { AiItemActionItem, DirectItemAction } from "@/lib/browse/itemActions";
import { AlertCircle, ChevronDown, Pin, RefreshCw } from "lucide-react";
import {
  BrowseCardSkeleton,
  BrowseEmptyState,
  BrowseErrorState,
} from "@/components/shared/BrowseCard";
import { summarizeSkillInventory } from "@/lib/browse/skill-card-ux";
import { indexCategoryForViewMode } from "@/lib/browse/viewModeMapping";
import {
  capabilityMetadataList,
  capabilityMetadataValue,
  formatCapabilityLabel,
  hasCapabilityMetadata,
} from "@/lib/browse/capabilityMetadata";
import {
  enrichItemsWithCoverage,
  EMPTY_COVERAGE_INDEX,
  type CoverageIndex,
} from "@/lib/browse/skillCoverage";
import type { ActiveFolderContext } from "@/lib/browse/folderContext";
import { BrowseDisplayRenderer } from "./BrowseDisplayRenderer";

/* ------------------------------------------------------------------ */
/*  Not-indexed state with reindex button                              */
/* ------------------------------------------------------------------ */

function NotIndexedState({
  effectiveViewMode,
  onIndexed,
  stale = false,
}: {
  effectiveViewMode: ViewMode;
  onIndexed: () => void;
  stale?: boolean;
}) {
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleIndex = () => {
    setIndexing(true);
    setError(null);
    const indexCategory = indexCategoryForViewMode(effectiveViewMode);
    import("@/lib/mcp/client").then(({ mcpCall }) =>
      mcpCall("reindex-browse-category", { category: indexCategory })
        .then(() => onIndexed())
        .catch((e) => setError(e instanceof Error ? e.message : "Indexing failed"))
        .finally(() => setIndexing(false)),
    );
  };

  return (
    <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] p-8 text-center">
      <AlertCircle className="size-8 text-[var(--text-muted)] mx-auto mb-3" />
      <p className="text-sm text-[var(--text-secondary)] mb-4">
        {stale
          ? "This category's index is stale — its source files moved or were removed. Reindex to refresh it."
          : "This category has not been indexed yet. Index it to browse its contents."}
      </p>
      <button type="button"
        onClick={handleIndex}
        disabled={indexing}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[var(--accent-primary)] text-white hover:opacity-90 cursor-pointer transition-opacity disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
      >
        <RefreshCw className={`h-4 w-4${indexing ? " animate-spin" : ""}`} />
        {indexing ? "Indexing..." : stale ? "Reindex this category" : "Index this category"}
      </button>
      {error && (
        <p className="mt-3 text-xs text-[var(--accent-danger)]">{error}</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface BrowseContentGridProps {
  effectiveViewMode: ViewMode;
  activeCategory: BrowseCategory;
  displayMode: BrowseDisplayMode;
  sorted: BrowseItem[];
  pinnedItems: BrowseItem[];
  semanticResultsActive: boolean;
  semanticResults: BrowseItem[];
  semanticLoading: boolean;
  loading: boolean;
  error: string | null;
  refetch: () => void;
  notIndexed: boolean;
  stale?: boolean;
  visibleCount: number;
  onLoadMore: () => void;
  pageSize: number;
  selectedSkill: string | null;
  selectedSchedule: string | null;
  search: string;
  onRunMcp: (target: string) => void;
  onChatResult: (result: BrowseChatResult) => void;
  onSelectSkill: (skillId: string) => void;
  onSelectItem: (item: BrowseItem) => void;
  onSelectCapability: (item: BrowseItem) => void;
  onSelectScheduledExecution: (executionId: string) => void;
  isPinned: (item: BrowseItem) => boolean;
  onTogglePin: (item: BrowseItem) => void;
  /** ADR-748: dispatches a resolved prompt body to the CLI chat window. */
  onTriggerPrompt: (resolvedPrompt: string) => void;
  /** Hands a per-category AI-action prompt to the chat as an editable draft. */
  onItemPrompt?: (prompt: string) => void;
  /** Runs a generated direct MCP action against an item. */
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
  /** ADR-741 check-resolvable findings, joined onto skill + mcp-tool cards. */
  coverageIndex?: CoverageIndex;
  activeFolderContext?: ActiveFolderContext | null;
  onAttachDocumentSource?: () => void;
}

function emptyHintForFolderContext(
  activeCategory: BrowseCategory,
  activeFolderContext: ActiveFolderContext | null | undefined,
): string | undefined {
  if (
    activeCategory.id !== "documents" ||
    activeFolderContext?.scope !== "brain" ||
    !activeFolderContext.brain_id ||
    activeFolderContext.brain_id === "personal"
  ) {
    return undefined;
  }
  const label = activeFolderContext.label || "this project";
  return `No shared document source is attached to ${label} yet. Attach a shared folder such as Google Drive or SharePoint for this project.`;
}

function emptyActionForFolderContext(
  activeCategory: BrowseCategory,
  activeFolderContext: ActiveFolderContext | null | undefined,
  onAttachDocumentSource?: () => void,
) {
  if (
    activeCategory.id === "documents" &&
    activeFolderContext?.scope === "brain" &&
    activeFolderContext.brain_id &&
    activeFolderContext.brain_id !== "personal" &&
    onAttachDocumentSource
  ) {
    return { label: "Attach shared source", onSelect: onAttachDocumentSource };
  }
  return undefined;
}

function increment(map: Record<string, number>, key: string | undefined) {
  if (!key) return;
  map[key] = (map[key] ?? 0) + 1;
}

function summarizeCapabilityInventory(items: BrowseItem[]) {
  const summary = {
    total: 0,
    byOwner: {} as Record<string, number>,
    byManagement: {} as Record<string, number>,
    byScope: {} as Record<string, number>,
    byCurrentExposure: {} as Record<string, number>,
    withDrift: 0,
  };

  for (const item of items) {
    if (!hasCapabilityMetadata(item)) continue;
    summary.total += 1;
    increment(summary.byOwner, item.metadata?.ownerKind);
    increment(summary.byManagement, capabilityMetadataValue(item.metadata, "management"));
    increment(summary.byScope, capabilityMetadataValue(item.metadata, "scope"));
    for (const exposure of capabilityMetadataList(item.metadata, "currentExposure")) {
      increment(summary.byCurrentExposure, exposure);
    }
    if (capabilityMetadataList(item.metadata, "drift").length > 0) {
      summary.withDrift += 1;
    }
  }

  return summary.total > 0 ? summary : null;
}

function summaryEntries(map: Record<string, number>): Array<[string, number]> {
  return Object.entries(map).sort(([left], [right]) => left.localeCompare(right));
}

const STATS_DISCLOSURE_STORAGE_KEY = "augur-browse-stats-open";
const statsDisclosureListeners = new Set<() => void>();
let statsDisclosureFallbackOpen = false;

function subscribeStatsDisclosure(listener: () => void) {
  statsDisclosureListeners.add(listener);
  return () => statsDisclosureListeners.delete(listener);
}

function readStatsDisclosureOpen() {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STATS_DISCLOSURE_STORAGE_KEY) === "true";
  } catch {
    return statsDisclosureFallbackOpen;
  }
}

function writeStatsDisclosureOpen(open: boolean) {
  statsDisclosureFallbackOpen = open;
  try {
    window.localStorage.setItem(STATS_DISCLOSURE_STORAGE_KEY, open ? "true" : "false");
  } catch {
    // ignore persistence failures
  }
  statsDisclosureListeners.forEach((listener) => listener());
}

function handleBrowseStatsDisclosureToggle(event: SyntheticEvent<HTMLDetailsElement>) {
  writeStatsDisclosureOpen(event.currentTarget.open);
}

function BrowseStatsDisclosure({ children }: { children: ReactNode }) {
  const open = useSyncExternalStore(
    subscribeStatsDisclosure,
    readStatsDisclosureOpen,
    () => false,
  );

  return (
    <details
      open={open}
      onToggle={handleBrowseStatsDisclosureToggle}
      className="mb-2 group"
      data-testid="browse-stats-disclosure"
    >
      <summary className="inline-flex cursor-pointer items-center gap-1.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50">
        <ChevronDown
          className="size-3.5 transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
        Show stats
      </summary>
      <div className="mt-2 space-y-2">{children}</div>
    </details>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function BrowseContentGrid({
  effectiveViewMode,
  activeCategory,
  displayMode,
  sorted,
  pinnedItems,
  semanticResultsActive,
  semanticResults,
  semanticLoading,
  loading,
  error,
  refetch,
  notIndexed,
  stale,
  visibleCount,
  onLoadMore,
  pageSize,
  selectedSkill,
  selectedSchedule,
  search,
  onRunMcp,
  onChatResult,
  onSelectSkill,
  onSelectItem,
  onSelectCapability,
  onSelectScheduledExecution,
  isPinned,
  onTogglePin,
  onTriggerPrompt,
  onItemPrompt,
  onItemDirect,
  coverageIndex = EMPTY_COVERAGE_INDEX,
  activeFolderContext,
  onAttachDocumentSource,
}: BrowseContentGridProps) {
  const allDisplayItems = semanticResultsActive
    ? semanticResults
    : sorted;
  const isLoading = loading || semanticLoading;
  // Pinned items get their own "Pinned" section on every tab (not just pages),
  // so they are pulled out of the main grid to avoid rendering twice. The strip
  // is suppressed during semantic search, where results carry their own ranking.
  const showPinnedStrip = !semanticResultsActive && pinnedItems.length > 0;
  const mainItems = useMemo(
    () =>
      showPinnedStrip
        ? allDisplayItems.filter((item) => !isPinned(item))
        : allDisplayItems,
    [showPinnedStrip, allDisplayItems, isPinned],
  );
  const displayItems = useMemo(
    () =>
      enrichItemsWithCoverage(
        mainItems.slice(0, visibleCount),
        coverageIndex,
        effectiveViewMode,
      ),
    [mainItems, visibleCount, coverageIndex, effectiveViewMode],
  );
  const pinnedDisplayItems = useMemo(
    () =>
      showPinnedStrip
        ? enrichItemsWithCoverage(pinnedItems, coverageIndex, effectiveViewMode)
        : [],
    [showPinnedStrip, pinnedItems, coverageIndex, effectiveViewMode],
  );
  const hasMore = mainItems.length > visibleCount;

  // Infinite scroll: auto-load more when sentinel enters viewport
  const sentinelRef = useRef<HTMLDivElement>(null);
  const onLoadMoreRef = useRef(onLoadMore);

  useEffect(() => {
    onLoadMoreRef.current = onLoadMore;
  }, [onLoadMore]);

  useEffect(() => {
    if (!hasMore) return;
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) onLoadMoreRef.current();
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, visibleCount]);

  const hasAnyItems = allDisplayItems.length > 0 || pinnedDisplayItems.length > 0;

  if (isLoading && !hasAnyItems) {
    return (
      <div className="grid grid-cols-1 @2xl:grid-cols-2 @5xl:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <BrowseCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (error && !hasAnyItems) {
    return <BrowseErrorState message={error} onRetry={refetch} />;
  }

  if (notIndexed) {
    return (
      <NotIndexedState
        effectiveViewMode={effectiveViewMode}
        onIndexed={refetch}
        stale={stale}
      />
    );
  }

  if (allDisplayItems.length === 0) {
    return (
      <BrowseEmptyState
        category={activeCategory}
        search={search}
        hint={emptyHintForFolderContext(activeCategory, activeFolderContext)}
        action={emptyActionForFolderContext(activeCategory, activeFolderContext, onAttachDocumentSource)}
      />
    );
  }

  const loadMoreSentinel = hasMore ? (
    <div className="flex flex-col items-center gap-2 pt-4">
      {/* Intersection observer sentinel — triggers auto-load */}
      <div ref={sentinelRef} className="h-px w-full" aria-hidden="true" />
      {/* Fallback button for manual trigger */}
      <button type="button"
        onClick={onLoadMore}
        className="px-5 py-2.5 text-sm font-medium rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:border-[var(--accent-primary)]/30 hover:text-[var(--text-primary)] cursor-pointer transition-colors duration-200"
      >
        Show more ({visibleCount} of {mainItems.length})
      </button>
    </div>
  ) : null;

  const isSkillsMode = effectiveViewMode === "skills";
  const skillSummary = isSkillsMode
    ? summarizeSkillInventory(allDisplayItems)
    : null;
  const capabilitySummary = summarizeCapabilityInventory(allDisplayItems);

  return (
    <>
      {error ? (
        <div role="alert" className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-[var(--accent-danger)]/40 bg-[var(--accent-danger)]/5 px-4 py-2 text-sm text-[var(--text-secondary)]">
          <span>Some items may be missing: {error}</span>
          <button type="button" onClick={refetch} className="shrink-0 font-medium underline">
            Retry
          </button>
        </div>
      ) : null}
      {showPinnedStrip ? (
        <section className="mb-5" data-testid="browse-pinned-strip">
          <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-secondary)]">
            <Pin className="size-3" aria-hidden="true" />
            Pinned
          </h3>
          <BrowseDisplayRenderer
            activeCategory={activeCategory}
            viewMode={effectiveViewMode}
            displayMode={displayMode}
            items={pinnedDisplayItems}
            selectedSkill={selectedSkill}
            selectedSchedule={selectedSchedule}
            onRunMcp={onRunMcp}
            onChatResult={onChatResult}
            onSelectSkill={onSelectSkill}
            onSelectItem={onSelectItem}
            onSelectCapability={onSelectCapability}
            onSelectScheduledExecution={onSelectScheduledExecution}
            isPinned={isPinned}
            onTogglePin={onTogglePin}
            onTriggerPrompt={onTriggerPrompt}
            onItemPrompt={onItemPrompt}
            onItemDirect={onItemDirect}
          />
        </section>
      ) : null}
      {(skillSummary || capabilitySummary) ? (
        <BrowseStatsDisclosure>
          {skillSummary ? (
            <div
              className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/90 p-3 text-xs text-[var(--text-secondary)]"
              data-testid="skills-insight-strip"
            >
              <span className="font-semibold text-[var(--text-primary)]">Skills inventory</span>
              <span className="tabular-nums">Total: {skillSummary.total}</span>
              <span className="tabular-nums">Augur: {skillSummary.augur}</span>
              <span className="tabular-nums">User: {skillSummary.user}</span>
              <span className="tabular-nums">External: {skillSummary.external}</span>
              <span className="tabular-nums">Adopted: {skillSummary.adopted}</span>
              <span className="tabular-nums">Needs setup: {skillSummary.needsSetup}</span>
            </div>
          ) : null}
          {capabilitySummary ? (
            <div
              className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/90 p-3 text-xs text-[var(--text-secondary)]"
              data-testid="capability-insight-strip"
            >
              <span className="font-semibold text-[var(--text-primary)]">Capability inventory</span>
              <span className="tabular-nums">Total: {capabilitySummary.total}</span>
              {summaryEntries(capabilitySummary.byOwner).map(([owner, count]) => (
                <span key={`owner-${owner}`} className="tabular-nums">{formatCapabilityLabel(owner)}: {count}</span>
              ))}
              {summaryEntries(capabilitySummary.byManagement).map(([management, count]) => (
                <span key={`management-${management}`} className="tabular-nums">{formatCapabilityLabel(management)}: {count}</span>
              ))}
              {summaryEntries(capabilitySummary.byScope).map(([scope, count]) => (
                <span key={`scope-${scope}`} className="tabular-nums">{formatCapabilityLabel(scope)}: {count}</span>
              ))}
              <span className="tabular-nums">Drift: {capabilitySummary.withDrift}</span>
              {summaryEntries(capabilitySummary.byCurrentExposure).map(([exposure, count]) => (
                <span key={`exposure-${exposure}`} className="tabular-nums">Exposure {formatCapabilityLabel(exposure)}: {count}</span>
              ))}
            </div>
          ) : null}
        </BrowseStatsDisclosure>
      ) : null}
      {displayItems.length > 0 ? (
        <BrowseDisplayRenderer
          activeCategory={activeCategory}
          viewMode={effectiveViewMode}
          displayMode={displayMode}
          items={displayItems}
          selectedSkill={selectedSkill}
          selectedSchedule={selectedSchedule}
          onRunMcp={onRunMcp}
          onChatResult={onChatResult}
          onSelectSkill={onSelectSkill}
          onSelectItem={onSelectItem}
          onSelectCapability={onSelectCapability}
          onSelectScheduledExecution={onSelectScheduledExecution}
          isPinned={isPinned}
          onTogglePin={onTogglePin}
          onTriggerPrompt={onTriggerPrompt}
          onItemPrompt={onItemPrompt}
          onItemDirect={onItemDirect}
        />
      ) : null}
      {loadMoreSentinel}
    </>
  );
}
