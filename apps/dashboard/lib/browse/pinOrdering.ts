import type { OverlayScopeFilter } from "@/lib/browse/overlay";
import type { BrowseItem, BrowsePageKindFilter, ViewMode } from "@/lib/browse/types";

export type BrowseSortBy =
  | "default"
  | "name-asc"
  | "name-desc"
  | "rank-desc"
  | "modified-desc"
  | "modified-asc";

export interface BrowsePinEntry {
  url?: string;
  title?: string;
  kind?: string;
  category?: string;
  itemKey?: string;
  pinnedAt?: string;
}

export interface BrowsePinTarget {
  category: ViewMode;
  itemKey: string;
  url: string;
  title: string;
  kind: string;
}

export interface BrowseNarrowingState {
  search: string;
  tagFilter: string | null;
  typeFilter: string | null;
  skillTagFilter: string | null;
  masterFilter: string | null;
  pluginFilter: string | null;
  sourceFilter: string | null;
  kindFilter: BrowsePageKindFilter;
  archivedFilter: string | null;
  scopeFilter: OverlayScopeFilter | null;
  exposureFilter: string | null;
  surfaceFilter: string | null;
  ownerFilter: string | null;
  managementFilter: string | null;
  policyScopeFilter: string | null;
  driftFilter: string | null;
  capabilityClientFilter: string | null;
}

const TIMESTAMP_FIELDS = [
  "created_at",
  "createdAt",
  "created",
  "promoted_at",
  "promotedAt",
  "modified",
  "modified_at",
  "modifiedAt",
  "updated_at",
  "updatedAt",
  "timestamp",
  "date",
] as const;

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value !== "string") continue;
    const trimmed = value.trim();
    if (trimmed) return trimmed;
  }
  return null;
}

function itemRecord(item: BrowseItem): Record<string, unknown> {
  return item as unknown as Record<string, unknown>;
}

function canonicalBrowseUrl(item: BrowseItem): string {
  return firstString(
    item.metadata?.url,
    item.primaryAction.type === "navigate" ? item.primaryAction.target : undefined,
    item.path,
    item.primaryAction.target,
    item.id,
  ) ?? item.id;
}

export function browseItemPinTarget(category: ViewMode, item: BrowseItem): BrowsePinTarget {
  return {
    category,
    itemKey: `${category}::${item.id || canonicalBrowseUrl(item)}`,
    url: canonicalBrowseUrl(item),
    title: item.title,
    kind: "browse-card",
  };
}

export function browseItemPinKeys(category: ViewMode, item: BrowseItem): string[] {
  const target = browseItemPinTarget(category, item);
  const keys = new Set<string>([target.itemKey]);
  if (target.url) keys.add(`${category}::${target.url}`);
  if (category === "pages" && target.url) keys.add(`pages::${target.url}`);
  return [...keys];
}

export function normalizePinEntries(
  entries: BrowsePinEntry[] | undefined,
  category: ViewMode,
): Map<string, BrowsePinEntry> {
  const lookup = new Map<string, BrowsePinEntry>();
  for (const entry of entries ?? []) {
    if (entry.category && entry.category !== category) continue;
    if (entry.itemKey) {
      lookup.set(entry.itemKey, entry);
      continue;
    }
    if (entry.category && entry.url) {
      lookup.set(`${category}::${entry.url}`, entry);
      continue;
    }
    if (category === "pages" && entry.url) {
      lookup.set(`pages::${entry.url}`, entry);
    }
  }
  return lookup;
}

export function getBrowseItemTimestampMs(item: BrowseItem): number | null {
  const metadata = item.metadata ?? {};
  const topLevel = itemRecord(item);
  for (const field of TIMESTAMP_FIELDS) {
    const raw = firstString(metadata[field], topLevel[field]);
    if (!raw) continue;
    const parsed = Date.parse(raw);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return null;
}

export function isBrowseItemPinned(
  category: ViewMode,
  item: BrowseItem,
  pins: Map<string, BrowsePinEntry>,
): boolean {
  return browseItemPinKeys(category, item).some((key) => pins.has(key));
}

export function isBrowseNarrowed(filters: BrowseNarrowingState): boolean {
  return Boolean(
    filters.search.trim() ||
      filters.tagFilter ||
      filters.typeFilter ||
      filters.skillTagFilter ||
      filters.masterFilter ||
      filters.pluginFilter ||
      filters.sourceFilter ||
      filters.kindFilter !== "all" ||
      filters.archivedFilter ||
      filters.scopeFilter ||
      filters.exposureFilter ||
      filters.surfaceFilter ||
      filters.ownerFilter ||
      filters.managementFilter ||
      filters.policyScopeFilter ||
      filters.driftFilter ||
      filters.capabilityClientFilter,
  );
}

function titleAsc(left: BrowseItem, right: BrowseItem): number {
  return left.title.localeCompare(right.title);
}

function baseSort(left: BrowseItem, right: BrowseItem, sortBy: BrowseSortBy): number {
  switch (sortBy) {
    case "name-desc":
      return right.title.localeCompare(left.title);
    case "rank-desc": {
      const scoreA = parseFloat(left.metadata?.qualityScore || "0");
      const scoreB = parseFloat(right.metadata?.qualityScore || "0");
      if (scoreA !== scoreB) return scoreB - scoreA;
      const tierOrder: Record<string, number> = { A: 1, B: 2, C: 3, D: 4, F: 5 };
      const tierA = tierOrder[left.metadata?.qualityTier || ""] ?? 6;
      const tierB = tierOrder[right.metadata?.qualityTier || ""] ?? 6;
      if (tierA !== tierB) return tierA - tierB;
      return titleAsc(left, right);
    }
    case "modified-desc":
      return (right.metadata?.modified || "").localeCompare(left.metadata?.modified || "") || titleAsc(left, right);
    case "modified-asc":
      return (left.metadata?.modified || "").localeCompare(right.metadata?.modified || "") || titleAsc(left, right);
    case "name-asc":
    case "default":
    default:
      return titleAsc(left, right);
  }
}

export function sortBrowseItems(
  items: BrowseItem[],
  options: {
    category: ViewMode;
    pins: Map<string, BrowsePinEntry>;
    sortBy: BrowseSortBy;
    narrowed: boolean;
  },
): BrowseItem[] {
  return items.toSorted((left, right) => {
    const leftPinned = isBrowseItemPinned(options.category, left, options.pins);
    const rightPinned = isBrowseItemPinned(options.category, right, options.pins);
    if (leftPinned !== rightPinned) return leftPinned ? -1 : 1;

    if (options.sortBy === "default" && !options.narrowed) {
      const leftTimestamp = getBrowseItemTimestampMs(left);
      const rightTimestamp = getBrowseItemTimestampMs(right);
      if (leftTimestamp !== null && rightTimestamp !== null && leftTimestamp !== rightTimestamp) {
        return rightTimestamp - leftTimestamp;
      }
      if (leftTimestamp !== null && rightTimestamp === null) return -1;
      if (leftTimestamp === null && rightTimestamp !== null) return 1;
      return titleAsc(left, right);
    }

    const resolvedSort = options.sortBy === "default" ? "name-asc" : options.sortBy;
    return baseSort(left, right, resolvedSort);
  });
}
