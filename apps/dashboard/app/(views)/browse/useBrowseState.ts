"use client";

import { useState, useMemo, useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { mcpCall } from "@/lib/mcp/client";
import { useModeStore } from "@/lib/stores/modeStore";
import { useChatStore } from "@/lib/stores/chatStore";
import { coreTabRegistry, getCompleteRegistry } from "@/lib/tabs/registry";
import type { ViewMode, BrowseItem, BrowseCategory, BrowsePageKindFilter, NoteTypeFilter } from "@/lib/browse/types";
import type { NoteDomain, NoteSource, NoteStatus } from "@/lib/browse/types";
import {
  BROWSE_CATEGORIES,
  NOTE_TYPE_FILTERS,
  compareBrowseCategoriesByJourney,
} from "@/lib/browse/types";
import { dedupeSkillBrowseItems, transformIndexEntry, transformPages } from "@/lib/browse/transforms";
import type { BrowseChatResult } from "@/lib/browse/executeAction";
import type { IndexedPageEntry } from "@/lib/browse/pages-merge";
import {
  browseItemKey,
  isOverlayViewMode,
  matchesOverlayScope,
  type OverlayScopeFilter,
} from "@/lib/browse/overlay";
import {
  indexCategoryForViewMode,
  itemMatchesViewMode,
  journeyCategoryForViewMode,
  normalizeRequestedViewMode,
} from "@/lib/browse/viewModeMapping";
import {
  browseItemPinTarget,
  isBrowseItemPinned,
  isBrowseNarrowed,
  normalizePinEntries,
  sortBrowseItems,
  type BrowsePinEntry,
  type BrowseSortBy,
} from "@/lib/browse/pinOrdering";
import {
  displayModeForCategory,
  readDisplayModeOverrides,
  writeDisplayModeOverride,
  type BrowseDisplayMode,
  type BrowseDisplayModeOverrides,
} from "@/lib/browse/displayMode";
import { useSkillDetail } from "@/lib/browse/useSkillDetail";
import { useScheduledExecutionDetail } from "@/lib/browse/useScheduledExecutionDetail";
import { runCliExecPrompt } from "@/lib/browse/cliExecClient";
import {
  capabilityMetadataList,
  capabilityMetadataValue,
  formatCapabilityLabel,
} from "@/lib/browse/capabilityMetadata";
import {
  buildBrainFilterOptions,
  itemMatchesBrainFilter,
  type BrainDiscoveryLite,
  type BrainFilter,
} from "@/lib/browse/brainFilters";
import {
  buildFolderContextOptions,
  defaultFolderContext,
  itemMatchesFolderContext,
  type ActiveFolderContext,
  type FolderContextOption,
  type FolderContextResponse,
} from "@/lib/browse/folderContext";
import {
  buildProblemFilterOptions,
  itemMatchesProblemFilter,
} from "@/lib/browse/problems";
import {
  noteClassificationForItem,
  noteDomainLabel,
  noteSourceLabel,
  noteStatusLabel,
  type FilterOption,
} from "@/lib/browse/noteClassification";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const LS_KEY = "augur:browse:view";
const PAGE_SIZE = 30;
const NOTE_TYPE_LABELS: Record<NoteTypeFilter, string> = {
  url: "URL",
  file: "File",
  thought: "Thought",
  "voice-memo": "Voice Memo",
  meeting: "Meeting",
  image: "Image",
  prompt: "Prompt",
};
const NOTE_TYPE_ALIASES: Record<string, NoteTypeFilter> = {
  url: "url",
  article: "url",
  webpage: "url",
  source: "url",
  file: "file",
  document: "file",
  markdown: "file",
  thought: "thought",
  text: "thought",
  note: "thought",
  "voice-memo": "voice-memo",
  voice: "voice-memo",
  audio: "voice-memo",
  meeting: "meeting",
  image: "image",
  prompt: "prompt",
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

type PageEntry = { label: string; href: string; hub: string; icon: string; pageType?: string; skillId?: string };
type PinMutationResponse = {
  success?: boolean;
  added?: boolean;
  removed?: boolean;
  error?: string;
};

function normalizeActiveFolderContext(
  context: unknown,
): ActiveFolderContext {
  if (!context || typeof context !== "object") {
    return defaultFolderContext();
  }
  const candidate = context as Record<string, unknown>;
  const scope = candidate.scope;
  const label = typeof candidate.label === "string" ? candidate.label.trim() : "";
  const brainId = typeof candidate.brain_id === "string" ? candidate.brain_id.trim() : "";
  const state = typeof candidate.state === "string" ? candidate.state : null;
  const projectRoot = typeof candidate.project_root === "string" ? candidate.project_root.trim() : "";
  const root = typeof candidate.root === "string" ? candidate.root.trim() : "";

  if (scope === "all") {
    return label ? { scope: "all", label } : defaultFolderContext();
  }
  if (scope === "unassigned") {
    return { scope: "unassigned", label: label || "Unassigned" };
  }
  if (
    scope === "brain" &&
    brainId &&
    state !== "unregistered" &&
    state !== "missing"
  ) {
    return {
      scope: "brain",
      brain_id: brainId,
      label: label || brainId,
      ...(projectRoot ? { project_root: projectRoot } : {}),
      ...(root ? { root } : {}),
      ...(state ? { state } : {}),
    };
  }
  return defaultFolderContext();
}

function getAllPages(): PageEntry[] {
  const pages: PageEntry[] = [];
  for (const [hub, config] of Object.entries(getCompleteRegistry())) {
    if (hub in coreTabRegistry) continue;
    // Custom TSX pages (tabs + overflow)
    const customTabs = [...(config.tabs || []), ...(config.overflow || [])];
    for (const tab of customTabs) {
      if (!tab.href || tab.href === `/${hub}`) continue;
      pages.push({
        label: tab.label,
        href: tab.href,
        hub,
        icon: typeof tab.icon === "string" ? tab.icon : "FileText",
        pageType: tab.pageSource || "tsx",
        skillId: tab.skillId,
      });
    }
    // YAML config-driven pages
    for (const tab of config.configPages || []) {
      if (!tab.href) continue;
      pages.push({
        label: tab.label,
        href: tab.href,
        hub,
        icon: typeof tab.icon === "string" ? tab.icon : "FileText",
        pageType: "yaml",
        skillId: tab.skillId,
      });
    }
    // Auto-generated pages
    for (const tab of config.autoPages || []) {
      if (!tab.href) continue;
      pages.push({
        label: tab.label,
        href: tab.href,
        hub,
        icon: typeof tab.icon === "string" ? tab.icon : "FileText",
        pageType: "auto",
        skillId: tab.skillId,
      });
    }
  }
  return pages;
}

function readViewMode(isDev: boolean): ViewMode {
  if (typeof window === "undefined") return "skills";
  const stored = localStorage.getItem(LS_KEY);
  const normalized = normalizeRequestedViewMode(stored);
  if (!normalized) return "skills";
  const category = BROWSE_CATEGORIES.find((c) => c.id === normalized);
  if (!category) return "skills";
  if (category.devOnly && !isDev) return "skills";
  return category.id;
}

function readUrlViewMode(value: string | null, isDev: boolean): ViewMode | null {
  const normalized = normalizeRequestedViewMode(value);
  if (!normalized) return null;
  const category = BROWSE_CATEGORIES.find((c) => c.id === normalized);
  if (!category) return null;
  if (category.devOnly && !isDev) return null;
  return category.id;
}

function normalizeSkillOwnership(value: unknown): "augur" | "external" | "adopted" {
  const ownership = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (ownership === "external" || ownership === "adopted") return ownership;
  if (ownership === "local" || ownership === "global" || ownership === "plugin") return "external";
  return "augur";
}

function splitMetadataList(value: string | undefined): string[] {
  return value
    ? value.split(",").flatMap((item) => {
        const trimmed = item.trim();
        return trimmed ? [trimmed] : [];
      })
    : [];
}

type SemanticSearchHit = {
  file?: string;
  path?: string;
  source_path?: string;
  content?: string;
  description?: string;
  scope?: string;
  category?: string;
  browse_category?: string;
  type?: string;
  hub?: string;
  line?: string;
  score?: number;
  budget?: SearchBudget;
  provenance?: string[];
  name?: string;
  label?: string;
  title?: string;
  document_title?: string;
  document_summary?: string;
  format?: string;
  modified?: string;
  indexed_at?: string;
  metadata?: Record<string, unknown>;
};

function firstSemanticString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    if (typeof value === "string") {
      const text = value.trim();
      if (text) return text;
    } else if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
  }
  return undefined;
}

function semanticBasename(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}

function semanticTitleFromPath(path: string): string {
  return semanticBasename(path).replace(/\.\w+$/, "").replace(/[-_]/g, " ");
}

function semanticDisplayTitle(title: string): string {
  return title.replace(/\.\w+$/, "").replace(/[-_]/g, " ");
}

function semanticFileExtension(path: string): string {
  const name = semanticBasename(path);
  const index = name.lastIndexOf(".");
  return index > 0 ? name.slice(index + 1).toLowerCase() : "";
}

function semanticShortPath(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const scopedMatch = normalized.match(/\/(?:Au-docs|Documents\/Augur|Vault\/Augur)\/(.*)$/);
  if (scopedMatch) {
    return scopedMatch[1].split("/").filter(Boolean).join(" / ");
  }
  const ragDocumentsIndex = normalized.indexOf("/rag/documents/");
  if (ragDocumentsIndex >= 0) {
    return normalized.slice(ragDocumentsIndex + "/rag/documents/".length).split("/").filter(Boolean).join(" / ");
  }
  return normalized.split("/").filter(Boolean).slice(-4).join(" / ");
}

function semanticHub(hit: SemanticSearchHit, category: string, sourcePath: string, file: string): string {
  const explicit = firstSemanticString(hit.hub, hit.metadata?.hub);
  if (explicit && explicit !== "rag") return explicit;
  const path = (sourcePath || file).replace(/\\/g, "/");
  const docsIndex = path.indexOf("/Au-docs/");
  if (docsIndex >= 0) {
    const [hub] = path.slice(docsIndex + "/Au-docs/".length).split("/").filter(Boolean);
    if (hub) return hub;
  }
  const ragDocsIndex = path.indexOf("/rag/documents/");
  if (ragDocsIndex >= 0) {
    const [hub] = path.slice(ragDocsIndex + "/rag/documents/".length).split("/").filter(Boolean);
    if (hub) return hub;
  }
  return category === "documents" ? "documents" : hit.scope || "unknown";
}

function dedupeChips(tags: string[], hub: string, typeBadge: string): string[] {
  const seen = new Set([hub.toLowerCase(), typeBadge.toLowerCase()]);
  return tags.filter((t) => t && !seen.has(t.toLowerCase()));
}

export function semanticHitToBrowseItem(hit: SemanticSearchHit, index: number, fallbackBudget: SearchBudget): BrowseItem {
  const file = hit.file || hit.path || "";
  const sourcePath = firstSemanticString(hit.source_path, hit.metadata?.source_path) || "";
  const category = firstSemanticString(hit.browse_category, hit.category, hit.metadata?.category, hit.type) || (sourcePath ? "documents" : hit.scope || "result");
  const format = firstSemanticString(hit.format, hit.metadata?.format) || semanticFileExtension(sourcePath || file);
  const typeBadge = category === "documents"
    ? format || "document"
    : firstSemanticString(hit.metadata?.["x-augur-note-type"], hit.type) || "note";
  const hub = semanticHub(hit, category, sourcePath, file);
  const title = semanticDisplayTitle(
    firstSemanticString(hit.document_title, hit.title, hit.label, hit.name, hit.metadata?.document_title, hit.metadata?.name)
      || semanticTitleFromPath(sourcePath || file || `Result ${index + 1}`),
  );
  const description = category === "documents" && (sourcePath || file)
    ? `${(format || "file").toUpperCase()} · ${semanticShortPath(sourcePath || file)}`
    : firstSemanticString(hit.description, hit.document_summary, hit.content) || "";
  const target = sourcePath || file;
  const metadata: Record<string, string> = {
    scope: hit.scope || "unknown",
    category,
    budget: hit.budget ?? fallbackBudget,
  };
  if (sourcePath) metadata.source_path = sourcePath;
  if (file && sourcePath && file !== sourcePath) metadata.ragPath = file;
  if (format) metadata.fileType = format;
  if (hit.modified) metadata.modified = hit.modified;
  if (hit.indexed_at) metadata.indexedAt = hit.indexed_at;
  if (typeof hit.score === "number") metadata.score = hit.score.toFixed(6);
  if (hit.provenance) metadata.provenance = hit.provenance.join(", ");
  if (hit.line) metadata.line = hit.line;

  return {
    id: `semantic-${index}-${target || title}`,
    title,
    description: description.slice(0, 240),
    icon: category === "documents" ? "FileText" : "Search",
    typeBadge,
    path: target,
    tags: dedupeChips(category === "documents" ? ["documents"] : [hit.scope || category], hub, typeBadge),
    primaryAction: {
      label: "Open",
      type: "open-file" as const,
      target,
    },
    metadata,
  };
}

function browseFilterValues(item: BrowseItem, key: string): string[] {
  const value = item.metadata?.[key];
  if (!value) return [];
  return key === "pageTags" || key === "skillTags" ? splitMetadataList(value) : [value];
}

function normalizeNoteType(value: string | undefined): NoteTypeFilter | null {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return null;
  return NOTE_TYPE_ALIASES[normalized] ?? null;
}

function noteTypeForItem(item: BrowseItem): NoteTypeFilter | null {
  const metadata = item.metadata ?? {};
  const explicit = normalizeNoteType(
    metadata["x-augur-note-type"] ||
    metadata.noteType ||
    metadata.note_type ||
    metadata.note_type_filter ||
    item.typeBadge,
  );
  if (explicit) return explicit;

  const path = item.path || metadata.source_path || "";
  const normalizedPath = path.replace(/\\/g, "/").toLowerCase();
  if (normalizedPath.includes("/sources/urls/")) return "url";
  if (normalizedPath.includes("/sources/files/")) return "file";
  if (normalizedPath.includes("/prompts/")) return "prompt";
  if (metadata.canonical_url || metadata.url || metadata.source_domain) return "url";
  return null;
}

function hasNoteFilterSignal(item: BrowseItem): boolean {
  if (noteTypeForItem(item)) return true;
  const metadata = item.metadata ?? {};
  if (
    metadata["x-augur-domain"] ||
    metadata["x-augur-source"] ||
    metadata["x-augur-status"] ||
    metadata["x-augur-note-domain"] ||
    metadata["x-augur-note-source"] ||
    metadata["x-augur-note-status"] ||
    metadata.noteDomain ||
    metadata.noteSource ||
    metadata.noteStatus ||
    metadata.note_domain ||
    metadata.note_source ||
    metadata.note_status ||
    metadata.canonical_url ||
    metadata.canonicalUrl ||
    metadata.url ||
    metadata.source_url ||
    metadata.sourceUrl ||
    metadata.source_domain
  ) {
    return true;
  }
  const path = (item.path || metadata.source_path || item.primaryAction.target || "").replace(/\\/g, "/").toLowerCase();
  return path.includes("/sources/urls/") || path.includes("/sources/files/") || path.includes("/prompts/");
}

function noteFilterClassificationForItem(item: BrowseItem) {
  return hasNoteFilterSignal(item) ? noteClassificationForItem(item) : null;
}

function formatMetadataFilterLabel(value: string): string {
  return value
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function stripLegacyDispatchHint(target: string): string {
  const sepIdx = target.lastIndexOf(":");
  if (sepIdx <= 0) return target;
  const suffix = target.slice(sepIdx + 1);
  return ["fire", "ide", "oneshot", "chat", "auto", "modal"].includes(suffix)
    ? target.slice(0, sepIdx)
    : target;
}

function countNoteFilterOptions<T extends string>(
  items: BrowseItem[],
  valueForItem: (item: BrowseItem) => T | null,
  labelForValue: (value: T) => string,
): FilterOption<T>[] {
  const counts = new Map<T, number>();
  for (const item of items) {
    const value = valueForItem(item);
    if (value) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([id, count]) => ({
      id,
      label: `${labelForValue(id)} (${count})`,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export type SearchBudget = "conservative" | "balanced" | "tokenmax";

export type { BrainFilter } from "@/lib/browse/brainFilters";

/* ------------------------------------------------------------------ */
/*  Hook return type                                                    */
/* ------------------------------------------------------------------ */

export interface BrowseState {
  /* Mode */
  isDev: boolean;
  effectiveViewMode: ViewMode;
  visibleCategories: BrowseCategory[];
  activeCategory: BrowseCategory;
  changeView: (id: string) => void;

  /* Display mode */
  displayMode: BrowseDisplayMode;
  setDisplayMode: (mode: BrowseDisplayMode) => void;

  /* Search */
  search: string;
  setSearch: (value: string) => void;

  /* Semantic search */
  semanticMode: boolean;
  setSemanticMode: React.Dispatch<React.SetStateAction<boolean>>;
  semanticResults: BrowseItem[];
  semanticDisplayResults: BrowseItem[];
  semanticSearchActive: boolean;
  semanticResultsActive: boolean;
  setSemanticResults: React.Dispatch<React.SetStateAction<BrowseItem[]>>;
  semanticLoading: boolean;
  semanticSearched: boolean;
  setSemanticSearched: React.Dispatch<React.SetStateAction<boolean>>;
  semanticError: string | null;
  semanticBudget: SearchBudget;
  setSemanticBudget: React.Dispatch<React.SetStateAction<SearchBudget>>;
  handleSemanticSearch: (query: string) => Promise<void>;

  /* Filters */
  brainFilter: BrainFilter;
  setBrainFilter: (brain: BrainFilter) => void;
  brainItems: { id: string; label: string }[];
  focusMode: boolean;
  setFocusMode: (value: boolean) => void;
  activeBrainId: string | null;
  activeFolderContext: ActiveFolderContext;
  folderContextOptions: FolderContextOption[];
  folderContextLoading: boolean;
  setActiveFolderContext: (context: ActiveFolderContext) => Promise<boolean>;
  scanFolderForContext: (projectRoot: string) => Promise<unknown>;
  tagFilter: string | null;
  setTagFilter: (tag: string | null) => void;
  problemFilter: string | null;
  setProblemFilter: (problem: string | null) => void;
  problemItems: { id: string; label: string }[];
  typeFilter: string | null;
  setTypeFilter: (type: string | null) => void;
  typeItems: { id: string; label: string }[];
  journeyCategoryFilter: string | null;
  setJourneyCategoryFilter: (category: string | null) => void;
  journeyCategoryItems: { id: string; label: string }[];
  noteStateFilter: string | null;
  setNoteStateFilter: (state: string | null) => void;
  noteStateItems: { id: string; label: string }[];
  noteDomainFilter: NoteDomain | null;
  setNoteDomainFilter: (domain: NoteDomain | null) => void;
  noteDomainItems: FilterOption<NoteDomain>[];
  noteSourceFilter: NoteSource | null;
  setNoteSourceFilter: (source: NoteSource | null) => void;
  noteSourceItems: FilterOption<NoteSource>[];
  noteStatusFilter: NoteStatus | null;
  setNoteStatusFilter: (status: NoteStatus | null) => void;
  noteStatusItems: FilterOption<NoteStatus>[];
  skillTagFilter: string | null;
  setSkillTagFilter: (tag: string | null) => void;
  skillTagItems: { id: string; label: string }[];
  masterFilter: string | null;
  setMasterFilter: (client: string | null) => void;
  masterClients: string[];
  pluginFilter: string | null;
  setPluginFilter: (plugin: string | null) => void;
  pluginNames: string[];
  sourceFilter: string | null;
  setSourceFilter: (source: string | null) => void;
  kindFilter: BrowsePageKindFilter;
  setKindFilter: (kind: BrowsePageKindFilter) => void;
  archivedFilter: string | null;
  setArchivedFilter: (value: string | null) => void;
  archivedItems: { id: string; label: string }[];
  scopeFilter: OverlayScopeFilter | null;
  setScopeFilter: (scope: OverlayScopeFilter | null) => void;
  scopeItems: { id: string; label: string }[];
  exposureFilter: string | null;
  setExposureFilter: (status: string | null) => void;
  exposureItems: { id: string; label: string }[];
  surfaceFilter: string | null;
  setSurfaceFilter: (surface: string | null) => void;
  surfaceItems: { id: string; label: string }[];
  ownerFilter: string | null;
  setOwnerFilter: (owner: string | null) => void;
  ownerItems: { id: string; label: string }[];
  managementFilter: string | null;
  setManagementFilter: (management: string | null) => void;
  managementItems: { id: string; label: string }[];
  policyScopeFilter: string | null;
  setPolicyScopeFilter: (scope: string | null) => void;
  policyScopeItems: { id: string; label: string }[];
  driftFilter: string | null;
  setDriftFilter: (drift: string | null) => void;
  driftItems: { id: string; label: string }[];
  capabilityClientFilter: string | null;
  setCapabilityClientFilter: (client: string | null) => void;
  capabilityClientItems: { id: string; label: string }[];

  /* Sort */
  sortBy: BrowseSortBy;
  setSortBy: (value: BrowseSortBy) => void;

  /* Data */
  sorted: BrowseItem[];
  filtered: BrowseItem[];
  sweepFilteredItems: BrowseItem[];
  sweepFilterSummary: {
    search: string;
    scope: string;
    tag: string;
    kind: BrowsePageKindFilter;
    source: string;
    viewMode: ViewMode;
  };
  pinnedItems: BrowseItem[];
  isPinned: (item: BrowseItem) => boolean;
  togglePin: (item: BrowseItem) => Promise<void>;
  loading: boolean;
  error: string | null;
  refetch: () => void;
  notIndexed: boolean;
  stale: boolean;
  truncated: boolean;
  totalCount: number | null;

  /* Pagination */
  visibleCount: number;
  setVisibleCount: React.Dispatch<React.SetStateAction<number>>;
  pageSize: number;

  /* Tag bar */
  tagItems: { id: string; label: string }[];

  /* Freshness (ADR-478) */
  lastIndexed: string | null;
  categoryFreshness: Record<string, string>;

  /* Actions */
  handleRunMcp: (target: string) => void;
  handleChatResult: (result: BrowseChatResult) => void;
  /** ADR-748: open the CLI chat window pre-loaded with a resolved prompt. */
  handleTriggerPrompt: (resolvedPrompt: string) => void;

  /* Detail panel */
  selectedSkill: string | null;
  selectedSchedule: string | null;
  skillDetail: ReturnType<typeof useSkillDetail>["detail"];
  scheduledExecutionDetail: ReturnType<typeof useScheduledExecutionDetail>["detail"];
  detailLoading: boolean;
  scheduledExecutionDetailLoading: boolean;
  selectSkill: (skillId: string) => void;
  selectScheduledExecution: (executionId: string) => void;
  closeDetail: () => void;

}

interface BrowseStateRouter {
  replace(href: string): void;
}

interface BrowseStateSearchParams {
  get(name: string): string | null;
  toString(): string;
}

interface UseBrowseStateOptions {
  router?: BrowseStateRouter;
  searchParams?: BrowseStateSearchParams;
}

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export function useBrowseState(options: UseBrowseStateOptions = {}): BrowseState {
  const fallbackRouter = useRouter();
  const fallbackSearchParams = useSearchParams();
  const router = options.router ?? fallbackRouter;
  const searchParams = options.searchParams ?? fallbackSearchParams;

  /* ----- Mode store ----- */
  const mode = useModeStore((s) => s.mode);
  const isDev = mode === "development";

  /* ----- URL state for detail panel ----- */
  const selectedSkill = searchParams.get("skill");
  const selectedSchedule = searchParams.get("schedule");
  const rawUrlCategory = searchParams.get("category");
  const rawUrlView = searchParams.get("view");
  const rawUrlMode = rawUrlCategory || rawUrlView;
  const rawTypeFilter = searchParams.get("type");
  const rawUrlSearch = searchParams.get("search")?.trim() ?? "";
  const urlViewMode = readUrlViewMode(rawUrlMode, isDev);

  /* ----- View mode (persisted) ----- */
  const [viewMode, setViewMode] = useState<ViewMode>(() => urlViewMode ?? "skills");

  useLayoutEffect(() => {
    const nextViewMode = urlViewMode ?? readViewMode(isDev);
    if (urlViewMode) {
      localStorage.setItem(LS_KEY, urlViewMode);
    }

    setViewMode((current) => (current === nextViewMode ? current : nextViewMode));
  }, [isDev, urlViewMode]);

  /* ----- Shared search ----- */
  const [search, setSearchState] = useState(rawUrlSearch);

  /* ----- Debounced search for server-side filtering (large categories) ----- */
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  /* ----- Sort ----- */
  const [sortBy, setSortBy] = useState<BrowseSortBy>("default");

  /* ----- Brain filter + focus mode (ADR-772) ----- */
  const [brainFilter, setBrainFilter] = useState<BrainFilter>("all");
  const [focusMode, setFocusMode] = useState(false);

  /* ----- Tag filter (grade/status) ----- */
  const [tagFilter, setTagFilter] = useState<string | null>(null);

  /* ----- Problem filter (inventory metadata) ----- */
  const [problemFilter, setProblemFilter] = useState<string | null>(null);

  /* ----- Type filter (skill taxonomy type / note type) ----- */
  const [typeFilter, setTypeFilterState] = useState<string | null>(null);

  useEffect(() => {
    const next = rawTypeFilter && rawTypeFilter !== "all" ? rawTypeFilter : null;
    const timer = window.setTimeout(() => {
      setTypeFilterState((current) => (current === next ? current : next));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [rawTypeFilter]);

  /* ----- Notes journey/content-category filter (sub-collection under notes/) ----- */
  // The note's journey_category is always "notes"; the content collection that
  // distinguishes Books / Reading list / Jobs / ... is the immediate subfolder,
  // carried as metadata.note_category from the index (ADR-491 vault scanner).
  const [journeyCategoryFilter, setJourneyCategoryFilter] = useState<string | null>(null);

  /* ----- Notes state filter (inbox / normal) ----- */
  const [noteStateFilter, setNoteStateFilter] = useState<string | null>(null);

  /* ----- Notes classification filters ----- */
  const [noteDomainFilter, setNoteDomainFilter] = useState<NoteDomain | null>(null);
  const [noteSourceFilter, setNoteSourceFilter] = useState<NoteSource | null>(null);
  const [noteStatusFilter, setNoteStatusFilter] = useState<NoteStatus | null>(null);

  /* ----- Skill tag filter (x-augur-tags) ----- */
  const [skillTagFilter, setSkillTagFilter] = useState<string | null>(null);

  /* ----- Master client filter ----- */
  const [masterFilter, setMasterFilter] = useState<string | null>(null);

  /* ----- Plugin filter ----- */
  const [pluginFilter, setPluginFilter] = useState<string | null>(null);

  /* ----- Source filter (skill provenance) ----- */
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);

  /* ----- Page/artifact kind filter ----- */
  const [kindFilter, setKindFilter] = useState<BrowsePageKindFilter>("all");

  /* ----- Archived filter (ADRs only) ----- */
  const [archivedFilter, setArchivedFilter] = useState<string | null>(null);

  /* ----- Overlay scope filter ----- */
  const [scopeFilter, setScopeFilter] = useState<OverlayScopeFilter | null>(null);

  /* ----- Capability policy filters ----- */
  const [exposureFilter, setExposureFilter] = useState<string | null>(null);
  const [surfaceFilter, setSurfaceFilter] = useState<string | null>(null);
  const [ownerFilter, setOwnerFilter] = useState<string | null>(null);
  const [managementFilter, setManagementFilter] = useState<string | null>(null);
  const [policyScopeFilter, setPolicyScopeFilter] = useState<string | null>(null);
  const [driftFilter, setDriftFilter] = useState<string | null>(null);
  const [capabilityClientFilter, setCapabilityClientFilter] = useState<string | null>(null);

  /* ----- Browse CLI execution streams ----- */
  const browseExecStreams = useRef<Set<EventSource> | null>(null);
  if (browseExecStreams.current === null) {
    browseExecStreams.current = new Set<EventSource>();
  }
  const browseExecStreamSet = browseExecStreams.current;

  useEffect(
    () => () => {
      for (const source of browseExecStreamSet) {
        source.close();
      }
      browseExecStreamSet.clear();
    },
    [browseExecStreamSet],
  );

  /* ----- Semantic search mode ----- */
  const [semanticMode, setSemanticMode] = useState(true);
  const [semanticResults, setSemanticResults] = useState<BrowseItem[]>([]);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticSearched, setSemanticSearched] = useState(false);
  const [semanticError, setSemanticError] = useState<string | null>(null);
  const [semanticBudget, setSemanticBudget] = useState<SearchBudget>("balanced");
  const [semanticResultScope, setSemanticResultScope] = useState<string | null>(null);
  const currentSemanticScopeRef = useRef<string>("");
  const activeSemanticRequestScopeRef = useRef<string | null>(null);

  const resetSemanticSearch = useCallback(() => {
    setSemanticResults([]);
    setSemanticSearched(false);
    setSemanticError(null);
    setSemanticResultScope(null);
  }, []);

  useEffect(() => {
    if (!rawUrlSearch) return undefined;
    const timer = window.setTimeout(() => {
      setSearchState((current) => {
        if (current === rawUrlSearch) return current;
        resetSemanticSearch();
        return rawUrlSearch;
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [rawUrlSearch, resetSemanticSearch]);

  const buildSemanticResultScope = useCallback(
    (query: string) => JSON.stringify({
      query: query.trim(),
      viewMode,
      tagFilter,
      problemFilter,
      typeFilter,
      journeyCategoryFilter,
      noteDomainFilter: viewMode === "notes" ? noteDomainFilter : null,
      noteSourceFilter: viewMode === "notes" ? noteSourceFilter : null,
      noteStatusFilter: viewMode === "notes" ? noteStatusFilter : null,
      skillTagFilter,
      masterFilter,
      pluginFilter,
      sourceFilter,
      kindFilter,
      archivedFilter,
      scopeFilter,
      exposureFilter,
      surfaceFilter,
      ownerFilter,
      managementFilter,
      policyScopeFilter,
      driftFilter,
      capabilityClientFilter,
    }),
    [
      archivedFilter,
      capabilityClientFilter,
      driftFilter,
      exposureFilter,
      journeyCategoryFilter,
      kindFilter,
      managementFilter,
      masterFilter,
      noteDomainFilter,
      noteSourceFilter,
      noteStatusFilter,
      ownerFilter,
      pluginFilter,
      policyScopeFilter,
      problemFilter,
      scopeFilter,
      skillTagFilter,
      sourceFilter,
      surfaceFilter,
      tagFilter,
      typeFilter,
      viewMode,
    ],
  );

  const setSearch = useCallback((value: string) => {
    if (search !== value) {
      resetSemanticSearch();
    }
    currentSemanticScopeRef.current = buildSemanticResultScope(value);
    setSearchState(value);
  }, [buildSemanticResultScope, resetSemanticSearch, search]);

  if (currentSemanticScopeRef.current !== buildSemanticResultScope(search)) {
    currentSemanticScopeRef.current = buildSemanticResultScope(search);
  }

  const handleSemanticSearch = useCallback(
    async (query: string) => {
      if (!query.trim()) return;
      const resultScope = buildSemanticResultScope(query);
      currentSemanticScopeRef.current = resultScope;
      activeSemanticRequestScopeRef.current = resultScope;
      setSemanticLoading(true);
      setSemanticError(null);
      setSemanticSearched(false);

      try {
        const data = await mcpCall<{
          success?: boolean;
          results?: SemanticSearchHit[];
          error?: string;
        }>("unified-search", {
          query: query.trim(),
          budget: semanticBudget,
          // Scope the per-tab semantic search to the active tab so results stay
          // within the tab (no cross-category mixing) instead of returning the
          // whole knowledge base. See ADR / browse search scoping.
          category: indexCategoryForViewMode(viewMode),
        });

        if (!data.success) {
          throw new Error(data.error || "Search failed");
        }

        const results: BrowseItem[] = (data.results || []).map((hit, i) => semanticHitToBrowseItem(hit, i, semanticBudget));

        if (currentSemanticScopeRef.current !== resultScope) return;
        setSemanticResults(results);
        setSemanticResultScope(resultScope);
        setSemanticSearched(true);
      } catch (err) {
        if (currentSemanticScopeRef.current !== resultScope) return;
        setSemanticError(err instanceof Error ? err.message : "Search failed");
        setSemanticResults([]);
        setSemanticResultScope(resultScope);
        setSemanticSearched(true);
      } finally {
        if (activeSemanticRequestScopeRef.current === resultScope) {
          activeSemanticRequestScopeRef.current = null;
          setSemanticLoading(false);
        }
      }
    },
    [buildSemanticResultScope, semanticBudget, viewMode],
  );

  const semanticSearchActive =
    semanticSearched && semanticResultScope === buildSemanticResultScope(search);
  const semanticResultsActive = semanticSearchActive;

  /* ----- Visible categories ----- */
  const visibleCategories = useMemo(
    () => BROWSE_CATEGORIES
      .filter((c) => !c.devOnly || isDev)
      .slice()
      .sort(compareBrowseCategoriesByJourney),
    [isDev],
  );

  const effectiveViewMode = useMemo(() => {
    const cat = BROWSE_CATEGORIES.find((c) => c.id === viewMode);
    if (cat?.devOnly && !isDev) return "skills";
    return viewMode;
  }, [viewMode, isDev]);
  const activeCategory = useMemo(
    () => BROWSE_CATEGORIES.find((c) => c.id === effectiveViewMode) ?? BROWSE_CATEGORIES[0],
    [effectiveViewMode],
  );
  const [displayModeOverrides, setDisplayModeOverrides] =
    useState<BrowseDisplayModeOverrides>({});

  useLayoutEffect(() => {
    setDisplayModeOverrides(readDisplayModeOverrides());
  }, []);

  const displayMode = useMemo(
    () => displayModeForCategory(activeCategory, displayModeOverrides),
    [activeCategory, displayModeOverrides],
  );
  const setDisplayMode = useCallback(
    (mode: BrowseDisplayMode) => {
      setDisplayModeOverrides(writeDisplayModeOverride(effectiveViewMode, mode));
    },
    [effectiveViewMode],
  );
  const indexCategory = indexCategoryForViewMode(effectiveViewMode);
  const journeyCategory = journeyCategoryForViewMode(effectiveViewMode);
  const journeyCategoryKey = journeyCategory ?? "all";
  const setTypeFilter = useCallback((type: string | null) => {
    const nextType = type && type !== "all" ? type : null;
    setTypeFilterState(nextType);
    const params = new URLSearchParams(searchParams.toString());
    if (nextType) {
      params.set("type", nextType);
    } else {
      params.delete("type");
    }
    if (effectiveViewMode === "notes") {
      params.delete("category");
      params.set("view", "notes");
    }
    params.delete("skill");
    params.delete("schedule");
    const qs = params.toString();
    router.replace(qs ? `/browse?${qs}` : "/browse");
  }, [effectiveViewMode, router, searchParams]);

  const openChat = useChatStore((s) => s.openChat);
  const openChatWithOneshotResult = useChatStore((s) => s.openChatWithOneshotResult);
  const handleRunMcp = useCallback(
    (target: string) => {
      const prompt = stripLegacyDispatchHint(target).trim();
      if (!prompt) return;

      const toastId = toast.loading("Running in CLI...");
      void runCliExecPrompt(prompt, {
        onStream: (source) => browseExecStreamSet.add(source),
        onStreamClose: (source) => browseExecStreamSet.delete(source),
      })
        .then(() => {
          toast.success("CLI run completed", { id: toastId });
        })
        .catch((error) => {
          const message =
            error instanceof Error ? error.message : "CLI run failed";
          toast.error(message, { id: toastId });
        });
    },
    [browseExecStreamSet],
  );

  const handleChatResult = useCallback(
    (result: BrowseChatResult) => {
      openChatWithOneshotResult({
        actionId: result.actionId,
        actionLabel: result.actionLabel,
        resultText: result.resultText,
        prompt: result.prompt,
        timestamp: new Date(),
      });
    },
    [openChatWithOneshotResult],
  );

  /* ----- ADR-748: prompt-card Trigger → CLI chat window ----- */
  const handleTriggerPrompt = useCallback(
    (resolvedPrompt: string) => {
      const prompt = resolvedPrompt.trim();
      if (!prompt) return;
      openChat({ mode: "auto", initialPrompt: prompt });
    },
    [openChat],
  );

  const changeView = useCallback((id: string) => {
    if (!BROWSE_CATEGORIES.some((c) => c.id === id)) return;
    const mode = id as ViewMode;
    setViewMode(mode);
    setSearchState("");
    resetSemanticSearch();
    setBrainFilter("all");
    setFocusMode(false);
    setTagFilter(null);
    setProblemFilter(null);
    setTypeFilterState(null);
    setJourneyCategoryFilter(null);
    setNoteStateFilter(null);
    setNoteDomainFilter(null);
    setNoteSourceFilter(null);
    setNoteStatusFilter(null);
    setSkillTagFilter(null);
    setMasterFilter(null);
    setPluginFilter(null);
    setSourceFilter(null);
    setKindFilter("all");
    setScopeFilter(null);
    setExposureFilter(null);
    setSurfaceFilter(null);
    setOwnerFilter(null);
    setManagementFilter(null);
    setPolicyScopeFilter(null);
    setDriftFilter(null);
    setCapabilityClientFilter(null);
    setSortBy("default");
    localStorage.setItem(LS_KEY, mode);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("category");
    params.set("view", mode);
    params.delete("type");
    params.delete("search");
    params.delete("skill");
    params.delete("schedule");
    const qs = params.toString();
    router.replace(qs ? `/browse?${qs}` : "/browse");
  }, [resetSemanticSearch, router, searchParams]);

  /* ----- Skill detail panel ----- */
  const { detail: skillDetail, loading: detailLoading } = useSkillDetail(selectedSkill);
  const {
    detail: scheduledExecutionDetail,
    loading: scheduledExecutionDetailLoading,
  } = useScheduledExecutionDetail(selectedSchedule);

  const selectSkill = useCallback(
    (skillId: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("skill", skillId);
      params.delete("schedule");
      router.replace(`/browse?${params.toString()}`);
    },
    [searchParams, router],
  );

  const selectScheduledExecution = useCallback(
    (executionId: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("schedule", executionId);
      params.delete("skill");
      router.replace(`/browse?${params.toString()}`);
    },
    [searchParams, router],
  );

  const closeDetail = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("skill");
    params.delete("schedule");
    const qs = params.toString();
    router.replace(qs ? `/browse?${qs}` : "/browse");
  }, [searchParams, router]);

  /* ----- Unified data fetch ----- */
  const allPages = useMemo(() => getAllPages(), []);

  const {
    data: indexData,
    loading: indexLoading,
    error: indexError,
    refetch: indexRefetch,
  } = useMcpQuery<{
    items?: Record<string, unknown>[];
    count?: number;
    status?: string;
    error?: string;
    last_indexed?: string;
    truncated?: boolean;
    total_count?: number;
  }>(
    ["browse-index", indexCategory, journeyCategoryKey, debouncedSearch, scopeFilter ?? "all"],
    "browse-index",
    "config",
    {
      args: {
        category: indexCategory,
        ...(journeyCategory ? { journey_category: journeyCategory } : {}),
        ...(debouncedSearch ? { search: debouncedSearch } : {}),
        ...(scopeFilter ? { scope: scopeFilter } : {}),
      },
    },
  );

  const {
    data: pinsData,
    error: pinsError,
    refetch: pinsRefetch,
  } = useMcpQuery<{ pins: BrowsePinEntry[] }>(
    ["pin-list", effectiveViewMode],
    "pin-list",
    "user-data",
    {
      fallback: { pins: [] },
    },
  );

  /* ----- Brain registry (ADR-772): active/current for filters ----- */
  const { data: brainDiscovery } = useMcpQuery<BrainDiscoveryLite>(
    ["browse-brain-discovery"],
    "brain-discovery",
    "config",
    { args: { include_git_status: false }, fallback: {} },
  );
  const activeBrainId = brainDiscovery?.active?.brain_id ?? null;

  const {
    data: folderContextData,
    loading: folderContextLoading,
    refetch: folderContextRefetch,
  } = useMcpQuery<FolderContextResponse>(
    ["browse-folder-context"],
    "brain-active-context",
    "config",
    { fallback: { success: true, context: defaultFolderContext(), options: [] } },
  );
  const activeFolderContext = useMemo(
    () => normalizeActiveFolderContext(folderContextData?.context),
    [folderContextData?.context],
  );
  const folderContextOptions = useMemo(
    () => buildFolderContextOptions(folderContextData),
    [folderContextData],
  );

  const setActiveFolderContext = useCallback(async (context: ActiveFolderContext): Promise<boolean> => {
    const response = await mcpCall<FolderContextResponse>("brain-set-active-context", {
      scope: context.scope,
      brain_id: context.brain_id || "",
    });
    if (response?.success === false) {
      throw new Error(response.error || "Folder context update failed");
    }
    folderContextRefetch();
    // Selecting a repairable/unregistered folder fixes it server-side; report
    // back so the UI can confirm the repair instead of silently switching.
    return response?.repaired === true;
  }, [folderContextRefetch]);

  const scanFolderForContext = useCallback(async (projectRoot: string) => {
    return mcpCall("brain-folder-scan", { project_root: projectRoot });
  }, []);

  // Folder context has a synchronous default and pins are an enhancement strip:
  // neither may block the card grid (spec 2026-06-10-browse-pages-load-speed).
  const loading = indexLoading;
  const error = indexError || pinsError;
  const refetch = useCallback(() => {
    indexRefetch();
    pinsRefetch();
    folderContextRefetch();
  }, [
    indexRefetch,
    pinsRefetch,
    folderContextRefetch,
  ]);
  const indexNotIndexed = indexData?.status === "not_indexed";
  // A non-empty on-disk index that filtered down to nothing (stale source_paths,
  // e.g. files moved). Reuses the not-indexed empty state so the user gets a
  // reindex affordance instead of a silent empty grid.
  const indexStale = indexData?.status === "stale";
  const lastIndexed = indexData?.last_indexed ?? null;
  const truncated = indexData?.truncated === true;
  const totalCount = (indexData?.total_count as number | undefined) ?? null;
  const isPageFallback = effectiveViewMode === "pages";
  const notIndexed = (indexNotIndexed || indexStale) && !isPageFallback;
  const stale = indexStale && !isPageFallback;

  /* ----- Track lastIndexed per category (ADR-478) ----- */
  const [categoryFreshness, setCategoryFreshness] = useState<Record<string, string>>({});

  useEffect(() => {
    if (lastIndexed && effectiveViewMode) {
      const timer = window.setTimeout(() => {
        setCategoryFreshness((prev) => {
          if (prev[effectiveViewMode] === lastIndexed) return prev;
          return { ...prev, [effectiveViewMode]: lastIndexed };
        });
      }, 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [lastIndexed, effectiveViewMode]);

  /* ----- Normalize to BrowseItem[] ----- */
  const rawItems = useMemo<BrowseItem[]>(() => {
    if (isPageFallback) {
      return transformPages(
        allPages,
        indexData?.items as IndexedPageEntry[] | undefined,
      );
    }
    if (!indexData?.items) return [];
    return indexData.items.flatMap((entry) => {
      const item = transformIndexEntry(entry as Record<string, any>, indexCategory);
      return itemMatchesViewMode(item, effectiveViewMode) ? [item] : [];
    });
  }, [
    effectiveViewMode,
    isPageFallback,
    allPages,
    indexData,
    indexCategory,
  ]);

  const items = useMemo(() => {
    const seen = new Set<string>();
    const dedupeBase = effectiveViewMode === "skills" ? dedupeSkillBrowseItems(rawItems) : rawItems;
    return dedupeBase.filter((item) => {
      const key = browseItemKey(item, effectiveViewMode);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [rawItems, effectiveViewMode]);

  const folderScopedItems = useMemo(() => {
    let result = effectiveViewMode === "pages"
      ? items
      : items.filter((item) => itemMatchesFolderContext(item, activeFolderContext));
    // ADR-772: focus mode pins the view to the active brain (screen-sharing),
    // then any manual brain filter narrows that focused set further.
    if (focusMode && activeBrainId) {
      result = result.filter((item) => item.metadata?.brain_id === activeBrainId);
    }
    if (brainFilter !== "all") {
      result = result.filter((item) => itemMatchesBrainFilter(item, brainFilter, brainDiscovery));
    }
    if (scopeFilter && isOverlayViewMode(effectiveViewMode)) {
      result = result.filter((item) => matchesOverlayScope(item, scopeFilter));
    }
    return result;
  }, [
    items,
    activeFolderContext,
    effectiveViewMode,
    focusMode,
    activeBrainId,
    brainFilter,
    brainDiscovery,
    scopeFilter,
  ]);

  const noteFilterBaseItems = effectiveViewMode === "notes" ? folderScopedItems : items;

  /* ----- Pagination ----- */
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    const timer = window.setTimeout(() => setVisibleCount(PAGE_SIZE), 0);
    return () => window.clearTimeout(timer);
  }, [effectiveViewMode, brainFilter, focusMode, tagFilter, problemFilter, typeFilter, journeyCategoryFilter, noteStateFilter, noteDomainFilter, noteSourceFilter, noteStatusFilter, skillTagFilter, masterFilter, pluginFilter, sourceFilter, kindFilter, scopeFilter, exposureFilter, surfaceFilter, ownerFilter, managementFilter, policyScopeFilter, driftFilter, capabilityClientFilter, search]);

  /* ----- Tag counts ----- */
  const tagKey = useMemo((): string | null => {
    switch (effectiveViewMode) {
      case "skills": return "qualityTier";
      case "commands": return "qualityTier";
      case "notes":
      case "archive":
      case "system-metadata": return "format";
      case "documents": return "fileType";
      case "integrations": return "status";
      case "mcp-servers": return "runtimeStatus";
      case "pages": return "kind";
      case "wiki": return "pageTags";
      default: return "grade";
    }
  }, [effectiveViewMode]);

  const tagCounts = useMemo(() => {
    if (!tagKey) return {};
    const map: Record<string, number> = {};
    for (const item of noteFilterBaseItems) {
      for (const val of browseFilterValues(item, tagKey)) {
        map[val] = (map[val] || 0) + 1;
      }
    }
    return map;
  }, [noteFilterBaseItems, tagKey]);

  const tagItems = useMemo(() => {
    const entries = Object.entries(tagCounts).sort(([, a], [, b]) => b - a);
    if (entries.length === 0) return [];
    const allItem = { id: "all", label: `All` };
    const isFormat = tagKey === "fileType" || tagKey === "format";
    return [allItem, ...entries.map(([tag, count]) => ({ id: tag, label: `${isFormat ? tag.toUpperCase() : tag} (${count})` }))];
  }, [tagCounts, tagKey]);

  const problemItems = useMemo(
    () => buildProblemFilterOptions(items),
    [items],
  );

  /* ----- Available master clients ----- */
  const masterClients = useMemo(() => {
    const clients = new Set<string>();
    for (const item of items) {
      const clientSources = splitMetadataList(item.metadata?.skillClients);
      if (clientSources.length > 0) {
        for (const client of clientSources) clients.add(client);
      } else {
        const c = item.metadata?.masterClient;
        if (c) clients.add(c);
      }
    }
    return Array.from(clients).toSorted();
  }, [items]);

  /* ----- Available plugin names ----- */
  const pluginNames = useMemo(() => {
    const plugins = new Set<string>();
    for (const item of items) {
      const p = item.metadata?.plugin;
      if (p) plugins.add(p);
    }
    return Array.from(plugins).toSorted();
  }, [items]);

  /* ----- Skill/note type counts ----- */
  const typeItems = useMemo(() => {
    if (effectiveViewMode === "notes") {
      const map: Record<string, number> = {};
      for (const type of NOTE_TYPE_FILTERS) {
        map[type] = 0;
      }
      for (const item of noteFilterBaseItems) {
        const type = noteTypeForItem(item);
        if (type) map[type] = (map[type] || 0) + 1;
      }
      return [
        { id: "all", label: "All Types" },
        ...NOTE_TYPE_FILTERS.map((type) => ({
          id: type,
          label: `${NOTE_TYPE_LABELS[type]} (${map[type] || 0})`,
        })),
      ];
    }
    if (effectiveViewMode !== "skills") return [];
    const map: Record<string, number> = {};
    for (const item of items) {
      const t = item.metadata?.skillType;
      if (t) map[t] = (map[t] || 0) + 1;
    }
    const entries = Object.entries(map).sort(([, a], [, b]) => b - a);
    if (entries.length === 0) return [];
    return [{ id: "all", label: "All Types" }, ...entries.map(([t, count]) => ({ id: t, label: `${t} (${count})` }))];
  }, [items, noteFilterBaseItems, effectiveViewMode]);

  /* ----- Notes content-category counts (notes view only) ----- */
  const journeyCategoryItems = useMemo(() => {
    if (effectiveViewMode !== "notes") return [];
    const map: Record<string, number> = {};
    for (const item of noteFilterBaseItems) {
      const category = item.metadata?.note_category;
      if (category) map[category] = (map[category] || 0) + 1;
    }
    const entries = Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
    if (entries.length === 0) return [];
    return [
      { id: "all", label: "All Categories" },
      ...entries.map(([id, count]) => ({
        id,
        label: `${formatMetadataFilterLabel(id)} (${count})`,
      })),
    ];
  }, [noteFilterBaseItems, effectiveViewMode]);

  /* ----- Notes state counts (inbox vs non-inbox) ----- */
  const noteStateItems = useMemo(() => {
    if (effectiveViewMode !== "notes") return [];
    const inboxCount = noteFilterBaseItems.filter(
      (item) => item.metadata?.noteState === "inbox",
    ).length;
    if (inboxCount === 0) return [];
    return [
      { id: "all", label: "All" },
      { id: "inbox", label: `Inbox (${inboxCount})` },
    ];
  }, [noteFilterBaseItems, effectiveViewMode]);

  const noteDomainItems = useMemo(() => {
    if (effectiveViewMode !== "notes") return [];
    return countNoteFilterOptions(
      noteFilterBaseItems,
      (item) => noteFilterClassificationForItem(item)?.domain ?? null,
      noteDomainLabel,
    );
  }, [noteFilterBaseItems, effectiveViewMode]);

  const noteSourceItems = useMemo(() => {
    if (effectiveViewMode !== "notes") return [];
    return countNoteFilterOptions(
      noteFilterBaseItems,
      (item) => noteFilterClassificationForItem(item)?.source ?? null,
      noteSourceLabel,
    );
  }, [noteFilterBaseItems, effectiveViewMode]);

  const noteStatusItems = useMemo(() => {
    if (effectiveViewMode !== "notes" || !noteDomainFilter) return [];
    return countNoteFilterOptions(
      noteFilterBaseItems,
      (item) => {
        const classification = noteFilterClassificationForItem(item);
        if (noteDomainFilter && classification?.domain !== noteDomainFilter) return null;
        return classification?.status ?? null;
      },
      noteStatusLabel,
    );
  }, [noteFilterBaseItems, effectiveViewMode, noteDomainFilter]);

  useEffect(() => {
    if (!noteStatusFilter) return;
    const allowedStatuses = noteStatusItems.map((option) => option.id);
    if (!allowedStatuses.includes(noteStatusFilter)) {
      setNoteStatusFilter(null);
    }
  }, [noteStatusFilter, noteStatusItems]);

  /* ----- Skill tag counts (skills category only) ----- */
  const skillTagItems = useMemo(() => {
    if (effectiveViewMode !== "skills") return [];
    const map: Record<string, number> = {};
    for (const item of items) {
      const tagsStr = item.metadata?.skillTags;
      if (tagsStr) {
        for (const tag of tagsStr.split(",")) {
          const trimmed = tag.trim();
          if (trimmed) map[trimmed] = (map[trimmed] || 0) + 1;
        }
      }
    }
    const entries = Object.entries(map).sort(([, a], [, b]) => b - a);
    if (entries.length === 0) return [];
    return [{ id: "all", label: "All Tags" }, ...entries.map(([t, count]) => ({ id: t, label: `${t} (${count})` }))];
  }, [items, effectiveViewMode]);

  const scopeItems = useMemo(() => {
    if (!isOverlayViewMode(effectiveViewMode)) return [];
    return [
      { id: "all", label: "Scope: All" },
      { id: "shared", label: "Shared" },
      { id: "private", label: "Private" },
      { id: "packet", label: "Packet" },
    ];
  }, [effectiveViewMode]);

  const exposureItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      const status = item.metadata?.classificationStatus;
      if (status) values.add(status);
    }
    return Array.from(values).toSorted().map((id) => ({ id, label: formatMetadataFilterLabel(id) }));
  }, [items]);

  const surfaceItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      const surface = item.metadata?.primarySurface;
      if (surface) values.add(surface);
    }
    return Array.from(values).toSorted().map((id) => ({ id, label: formatMetadataFilterLabel(id) }));
  }, [items]);

  const ownerItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      const owner = item.metadata?.ownerKind;
      if (owner) values.add(owner);
    }
    return Array.from(values).toSorted().map((id) => ({ id, label: formatMetadataFilterLabel(id) }));
  }, [items]);

  const managementItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      const management = capabilityMetadataValue(item.metadata, "management");
      if (management) values.add(management);
    }
    return Array.from(values).toSorted().map((id) => ({ id, label: formatCapabilityLabel(id) }));
  }, [items]);

  const policyScopeItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      const scope = capabilityMetadataValue(item.metadata, "scope");
      if (scope) values.add(scope);
    }
    return Array.from(values).toSorted().map((id) => ({ id, label: formatCapabilityLabel(id) }));
  }, [items]);

  const driftItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      for (const drift of capabilityMetadataList(item.metadata, "drift")) {
        values.add(drift);
      }
    }
    return Array.from(values).toSorted().map((id) => ({ id, label: formatCapabilityLabel(id) }));
  }, [items]);

  const capabilityClientItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      for (const client of capabilityMetadataList(item.metadata, "currentExposure")) {
        values.add(client);
      }
    }
    return Array.from(values).toSorted().map((id) => ({ id, label: formatCapabilityLabel(id) }));
  }, [items]);

  /* ----- Apply tag + type + skillTag + master + plugin + capability + search filters ----- */
  const filtered = useMemo(() => {
    let result = folderScopedItems;
    if (tagFilter && tagKey) {
      result = result.filter((item) => browseFilterValues(item, tagKey).includes(tagFilter));
    }
    if (problemFilter) {
      result = result.filter((item) => itemMatchesProblemFilter(item, problemFilter));
    }
    if (kindFilter !== "all" && effectiveViewMode === "pages") {
      result = result.filter((item) => item.metadata?.kind === kindFilter);
    }
    if (typeFilter) {
      if (effectiveViewMode === "notes") {
        const selectedTypes = new Set(splitMetadataList(typeFilter));
        result = result.filter((item) => {
          const noteType = noteTypeForItem(item);
          return noteType ? selectedTypes.has(noteType) : false;
        });
      } else {
        result = result.filter((item) => item.metadata?.skillType === typeFilter);
      }
    }
    if (journeyCategoryFilter && effectiveViewMode === "notes") {
      result = result.filter((item) => item.metadata?.note_category === journeyCategoryFilter);
    }
    if (noteStateFilter && effectiveViewMode === "notes") {
      result = result.filter((item) => item.metadata?.noteState === noteStateFilter);
    }
    if (effectiveViewMode === "notes" && (noteDomainFilter || noteSourceFilter || noteStatusFilter)) {
      result = result.filter((item) => {
        const classification = noteFilterClassificationForItem(item);
        if (!classification) return false;
        if (noteDomainFilter && classification.domain !== noteDomainFilter) return false;
        if (noteSourceFilter && classification.source !== noteSourceFilter) return false;
        if (noteStatusFilter && classification.status !== noteStatusFilter) return false;
        return true;
      });
    }
    if (skillTagFilter) {
      result = result.filter((item) => {
        const tags = item.metadata?.skillTags;
        return tags ? tags.split(",").map(t => t.trim()).includes(skillTagFilter) : false;
      });
    }
    if (masterFilter) {
      result = result.filter((item) => {
        const clients = splitMetadataList(item.metadata?.skillClients);
        if (clients.length > 0) return clients.includes(masterFilter);
        return item.metadata?.masterClient === masterFilter;
      });
    }
    if (pluginFilter) {
      result = result.filter((item) => item.metadata?.plugin === pluginFilter);
    }
    if (exposureFilter) {
      result = result.filter((item) => item.metadata?.classificationStatus === exposureFilter);
    }
    if (surfaceFilter) {
      result = result.filter((item) => item.metadata?.primarySurface === surfaceFilter);
    }
    if (ownerFilter) {
      result = result.filter((item) => item.metadata?.ownerKind === ownerFilter);
    }
    if (managementFilter) {
      result = result.filter((item) => capabilityMetadataValue(item.metadata, "management") === managementFilter);
    }
    if (policyScopeFilter) {
      result = result.filter((item) => capabilityMetadataValue(item.metadata, "scope") === policyScopeFilter);
    }
    if (driftFilter) {
      result = result.filter((item) => capabilityMetadataList(item.metadata, "drift").includes(driftFilter));
    }
    if (capabilityClientFilter) {
      result = result.filter((item) => capabilityMetadataList(item.metadata, "currentExposure").includes(capabilityClientFilter));
    }
    // Ownership filter
    if (sourceFilter) {
      result = result.filter((item) => {
        const itemOwnership = normalizeSkillOwnership(item.metadata?.ownership ?? item.metadata?.source);
        return itemOwnership === sourceFilter;
      });
    }
    // Archived filter (ADR-608: only meaningful for adrs category)
    if (archivedFilter && effectiveViewMode === "adrs") {
      result = result.filter((item) => {
        const raw = item.metadata?.archived;
        const isArchived = raw === "true" || (typeof raw === "string" && raw.toLowerCase() === "true");
        return archivedFilter === "archived" ? isArchived : !isArchived;
      });
    }
    if (search) {
      const lower = search.toLowerCase();
      result = result.filter(
        (item) =>
          item.title.toLowerCase().includes(lower) ||
          item.description.toLowerCase().includes(lower) ||
          Object.values(item.metadata ?? {}).some((value) =>
            String(value ?? "").toLowerCase().includes(lower),
          ),
      );
    }
    return result;
  }, [folderScopedItems, effectiveViewMode, tagFilter, tagKey, problemFilter, kindFilter, typeFilter, journeyCategoryFilter, noteStateFilter, noteDomainFilter, noteSourceFilter, noteStatusFilter, skillTagFilter, masterFilter, pluginFilter, exposureFilter, surfaceFilter, ownerFilter, managementFilter, policyScopeFilter, driftFilter, capabilityClientFilter, sourceFilter, archivedFilter, search]);

  const sweepFilterSummary = useMemo(
    () => ({
      search,
      scope: scopeFilter ?? "all",
      tag: tagFilter ?? "all",
      kind: kindFilter,
      source: sourceFilter ?? "all",
      viewMode: effectiveViewMode,
    }),
    [search, scopeFilter, tagFilter, kindFilter, sourceFilter, effectiveViewMode],
  );

  const pinLookup = useMemo(
    () => normalizePinEntries(pinsData?.pins, effectiveViewMode),
    [pinsData?.pins, effectiveViewMode],
  );

  const browseIsNarrowed = useMemo(
    () => Boolean(
      problemFilter ||
      (effectiveViewMode === "notes" && (noteDomainFilter || noteSourceFilter || noteStatusFilter)),
    ) || isBrowseNarrowed({
      search,
      tagFilter,
      typeFilter,
      skillTagFilter,
      masterFilter,
      pluginFilter,
      sourceFilter,
      kindFilter,
      archivedFilter,
      scopeFilter,
      exposureFilter,
      surfaceFilter,
      ownerFilter,
      managementFilter,
      policyScopeFilter,
      driftFilter,
      capabilityClientFilter,
    }),
    [
      effectiveViewMode,
      search,
      tagFilter,
      problemFilter,
      typeFilter,
      noteDomainFilter,
      noteSourceFilter,
      noteStatusFilter,
      skillTagFilter,
      masterFilter,
      pluginFilter,
      sourceFilter,
      kindFilter,
      archivedFilter,
      scopeFilter,
      exposureFilter,
      surfaceFilter,
      ownerFilter,
      managementFilter,
      policyScopeFilter,
      driftFilter,
      capabilityClientFilter,
    ],
  );

  const isPinned = useCallback(
    (item: BrowseItem) => isBrowseItemPinned(effectiveViewMode, item, pinLookup),
    [effectiveViewMode, pinLookup],
  );

  const togglePin = useCallback(
    async (item: BrowseItem) => {
      const target = browseItemPinTarget(effectiveViewMode, item);
      const pinned = isBrowseItemPinned(effectiveViewMode, item, pinLookup);
      const toastId = toast.loading(pinned ? "Removing pin..." : "Pinning card...");

      try {
        const args: Record<string, unknown> = pinned
          ? { url: target.url, category: target.category, itemKey: target.itemKey }
          : { ...target };
        const response = await mcpCall<PinMutationResponse>(
          pinned ? "pin-remove" : "pin-add",
          args,
        );
        if (response?.success === false || response?.error || (pinned && response?.removed === false)) {
          throw new Error(response.error || "Pin update failed");
        }
        toast.success(pinned ? "Pin removed" : "Card pinned", { id: toastId });
        pinsRefetch();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Pin update failed";
        toast.error(message, { id: toastId });
      }
    },
    [effectiveViewMode, pinLookup, pinsRefetch],
  );

  /* ----- Sort ----- */
  const sorted = useMemo(
    () => sortBrowseItems(filtered, {
      category: effectiveViewMode,
      pins: pinLookup,
      sortBy,
      narrowed: browseIsNarrowed,
    }),
    [filtered, effectiveViewMode, pinLookup, sortBy, browseIsNarrowed],
  );

  const pinnedItems = useMemo(() => sorted.filter(isPinned), [sorted, isPinned]);

  /* ----- Scoped semantic results (per-tab search) -----
   * Semantic (Enter) search is scoped to the active tab server-side, but we
   * still (a) drop any out-of-journey vault hits the category filter can't see
   * and (b) union the literal scoped results first so exact title/path matches
   * always surface even when content ranking buries them. Dedup by source path
   * so a literal card and its semantic twin collapse (literal wins). */
  const semanticDisplayResults = useMemo(() => {
    if (!semanticResultsActive) return [];
    const dedupeKey = (item: BrowseItem) =>
      item.path || item.metadata?.source_path || item.id;
    const seen = new Set<string>();
    const merged: BrowseItem[] = [];
    for (const item of sorted) {
      const key = dedupeKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      merged.push(item);
    }
    for (const item of semanticResults) {
      if (!itemMatchesViewMode(item, effectiveViewMode)) continue;
      const key = dedupeKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      merged.push(item);
    }
    return merged;
  }, [semanticResultsActive, semanticResults, sorted, effectiveViewMode]);

  /* ----- Brain filter bar items (ADR-772) ----- */
  const brainItems = useMemo(
    () => buildBrainFilterOptions(items, brainDiscovery),
    [items, brainDiscovery],
  );

  /* ----- Active category ----- */
  return {
    isDev,
    effectiveViewMode,
    visibleCategories,
    activeCategory,
    changeView,
    displayMode,
    setDisplayMode,
    search,
    setSearch,
    semanticMode,
    setSemanticMode,
    semanticResults,
    semanticDisplayResults,
    semanticSearchActive,
    semanticResultsActive,
    setSemanticResults,
    semanticLoading,
    semanticSearched,
    setSemanticSearched,
    semanticError,
    semanticBudget,
    setSemanticBudget,
    handleSemanticSearch,
    brainFilter,
    setBrainFilter,
    brainItems,
    focusMode,
    setFocusMode,
    activeBrainId,
    activeFolderContext,
    folderContextOptions,
    folderContextLoading,
    setActiveFolderContext,
    scanFolderForContext,
    tagFilter,
    setTagFilter,
    problemFilter,
    setProblemFilter,
    problemItems,
    typeFilter,
    setTypeFilter,
    typeItems,
    journeyCategoryFilter,
    setJourneyCategoryFilter,
    journeyCategoryItems,
    noteStateFilter,
    setNoteStateFilter,
    noteStateItems,
    noteDomainFilter,
    setNoteDomainFilter,
    noteDomainItems,
    noteSourceFilter,
    setNoteSourceFilter,
    noteSourceItems,
    noteStatusFilter,
    setNoteStatusFilter,
    noteStatusItems,
    skillTagFilter,
    setSkillTagFilter,
    skillTagItems,
    masterFilter,
    setMasterFilter,
    masterClients,
    pluginFilter,
    setPluginFilter,
    pluginNames,
    sourceFilter,
    setSourceFilter,
    kindFilter,
    setKindFilter,
    archivedFilter,
    setArchivedFilter,
    archivedItems: [
      { id: "archived", label: "Archived only" },
      { id: "live", label: "Live only" },
    ],
    scopeFilter,
    setScopeFilter,
    scopeItems,
    exposureFilter,
    setExposureFilter,
    exposureItems,
    surfaceFilter,
    setSurfaceFilter,
    surfaceItems,
    ownerFilter,
    setOwnerFilter,
    ownerItems,
    managementFilter,
    setManagementFilter,
    managementItems,
    policyScopeFilter,
    setPolicyScopeFilter,
    policyScopeItems,
    driftFilter,
    setDriftFilter,
    driftItems,
    capabilityClientFilter,
    setCapabilityClientFilter,
    capabilityClientItems,
    sortBy,
    setSortBy,
    sorted,
    filtered,
    sweepFilteredItems: filtered,
    sweepFilterSummary,
    pinnedItems,
    isPinned,
    togglePin,
    loading,
    error,
    refetch,
    notIndexed,
    stale,
    truncated,
    totalCount,
    visibleCount,
    setVisibleCount,
    pageSize: PAGE_SIZE,
    tagItems,
    lastIndexed,
    categoryFreshness,
    handleRunMcp,
    handleChatResult,
    handleTriggerPrompt,
    selectedSkill,
    selectedSchedule,
    skillDetail,
    scheduledExecutionDetail,
    detailLoading,
    scheduledExecutionDetailLoading,
    selectSkill,
    selectScheduledExecution,
    closeDetail,
  };
}
