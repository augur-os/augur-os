import type { ReactNode } from "react";
import {
  type ViewMode,
  type BrowseCategory,
  type BrowseItem,
  type BrowsePageKindFilter,
  type NoteDomain,
  type NoteSource,
  type NoteStatus,
} from "@/lib/browse/types";
import type { BrowseSortBy } from "@/lib/browse/pinOrdering";
import type { BrainFilter } from "./useBrowseState";
import type { OverlayScopeFilter } from "@/lib/browse/overlay";
import type { BrowseDisplayMode } from "@/lib/browse/displayMode";

export interface BrowseToolbarProps {
  activeCategory: BrowseCategory;
  effectiveViewMode: ViewMode;

  /* Display mode */
  displayMode: BrowseDisplayMode;
  onDisplayModeChange: (mode: BrowseDisplayMode) => void;

  /* Search */
  search: string;
  onSearchChange: (value: string) => void;

  /* Unified search */
  onSemanticSearch: (query: string) => void;
  semanticLoading: boolean;
  semanticResults: BrowseItem[];
  semanticSearched: boolean;
  semanticError: string | null;

  /* Deep search action */
  onDeepSearch?: () => void;
  deepSearchDisabled?: boolean;
  deepSearchBusy?: boolean;

  /* Tags / Quality */
  tagFilter: string | null;
  onTagFilterChange: (tag: string | null) => void;
  tagItems: { id: string; label: string }[];
  problemFilter?: string | null;
  onProblemFilterChange?: (problem: string | null) => void;
  problemItems?: { id: string; label: string }[];

  /* Brain (ADR-772) — optional with defaults, matching the extended-filter props below */
  brainFilter?: BrainFilter;
  onBrainFilterChange?: (brain: BrainFilter) => void;
  brainItems?: { id: string; label: string }[];
  focusMode?: boolean;
  onFocusModeChange?: (value: boolean) => void;
  activeBrainId?: string | null;

  /* Source (skills only) */
  sourceFilter: string | null;
  onSourceFilterChange: (source: string | null) => void;

  /* Page kind */
  kindFilter: BrowsePageKindFilter;
  onKindFilterChange: (kind: BrowsePageKindFilter) => void;

  /* Archived (ADRs only) */
  archivedFilter: string | null;
  onArchivedFilterChange: (value: string | null) => void;
  archivedItems: { id: string; label: string }[];

  /* Scope (overlay views) */
  scopeFilter?: OverlayScopeFilter | null;
  onScopeFilterChange?: (scope: OverlayScopeFilter | null) => void;
  scopeItems?: { id: string; label: string }[];

  /* Capability policy */
  exposureFilter?: string | null;
  onExposureFilterChange?: (status: string | null) => void;
  exposureItems?: { id: string; label: string }[];
  surfaceFilter?: string | null;
  onSurfaceFilterChange?: (surface: string | null) => void;
  surfaceItems?: { id: string; label: string }[];
  ownerFilter?: string | null;
  onOwnerFilterChange?: (owner: string | null) => void;
  ownerItems?: { id: string; label: string }[];
  managementFilter?: string | null;
  onManagementFilterChange?: (management: string | null) => void;
  managementItems?: { id: string; label: string }[];
  policyScopeFilter?: string | null;
  onPolicyScopeFilterChange?: (scope: string | null) => void;
  policyScopeItems?: { id: string; label: string }[];
  driftFilter?: string | null;
  onDriftFilterChange?: (drift: string | null) => void;
  driftItems?: { id: string; label: string }[];
  capabilityClientFilter?: string | null;
  onCapabilityClientFilterChange?: (client: string | null) => void;
  capabilityClientItems?: { id: string; label: string }[];

  /* Client */
  masterFilter: string | null;
  onMasterFilterChange: (client: string | null) => void;
  masterClients: string[];

  /* Plugin */
  pluginFilter: string | null;
  onPluginFilterChange: (plugin: string | null) => void;
  pluginNames: string[];

  /* Type */
  typeFilter: string | null;
  onTypeFilterChange: (type: string | null) => void;
  typeItems: { id: string; label: string }[];

  /* Content category (notes only) */
  journeyCategoryFilter?: string | null;
  onJourneyCategoryFilterChange?: (category: string | null) => void;
  journeyCategoryItems?: { id: string; label: string }[];

  /* Note state (inbox filter chip, notes only) */
  noteStateFilter?: string | null;
  onNoteStateFilterChange?: (state: string | null) => void;
  noteStateItems?: { id: string; label: string }[];

  /* Note classification (notes only) */
  noteDomainFilter?: NoteDomain | null;
  onNoteDomainFilterChange?: (domain: NoteDomain | null) => void;
  noteDomainItems?: { id: NoteDomain; label: string }[];
  noteSourceFilter?: NoteSource | null;
  onNoteSourceFilterChange?: (source: NoteSource | null) => void;
  noteSourceItems?: { id: NoteSource; label: string }[];
  noteStatusFilter?: NoteStatus | null;
  onNoteStatusFilterChange?: (status: NoteStatus | null) => void;
  noteStatusItems?: { id: NoteStatus; label: string }[];

  /* Skill tag (skills only) */
  skillTagFilter: string | null;
  onSkillTagFilterChange: (tag: string | null) => void;
  skillTagItems: { id: string; label: string }[];

  /* Sort */
  sortBy: BrowseSortBy;
  onSortChange: (value: BrowseSortBy) => void;

  /* Filter panel visibility */
  filtersOpen?: boolean;
  onFiltersOpenChange?: (open: boolean) => void;

  /* Multi-select mode */
  selectionMode?: boolean;
  onToggleSelectionMode?: () => void;
}

export interface FilterChip {
  id: string;
  label: string;
  onClear: () => void;
}

export interface FilterControl {
  id: string;
  node: ReactNode;
}

export type FilterOption = { id: string; label: string };
