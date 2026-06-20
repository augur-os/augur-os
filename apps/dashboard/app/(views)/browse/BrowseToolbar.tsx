"use client";

import { useEffect, useState } from "react";
import type { BrowseToolbarProps } from "./BrowseToolbar.types";
import {
  EMPTY_ARRAY,
  optionLabel,
  noteTypeFilterLabel,
  CLIENT_DISPLAY_NAMES,
} from "./BrowseToolbar.helpers";
import { buildActiveFilterChips, buildFilterControls } from "./BrowseToolbar.builders";
import {
  ActiveFilterChips,
  NotesCategoryFilterChips,
  NotesStateFilterChips,
} from "./BrowseToolbar.chips";
import {
  BrowseToolbarMainRow,
  FilterControlsPanel,
  SemanticSearchStatus,
} from "./BrowseToolbar.panels";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export function BrowseToolbar(props: BrowseToolbarProps) {
  const {
    activeCategory, effectiveViewMode, displayMode, onDisplayModeChange,
    search, onSearchChange, onSemanticSearch, semanticLoading,
    semanticResults, semanticSearched, semanticError, onDeepSearch,
    tagFilter, onTagFilterChange, tagItems,
    problemFilter: rawProblemFilter, onProblemFilterChange: rawOnProblemFilterChange, problemItems: rawProblemItems, sourceFilter, onSourceFilterChange, kindFilter, onKindFilterChange,
    archivedFilter, onArchivedFilterChange, archivedItems, masterFilter,
    onMasterFilterChange, masterClients, pluginFilter, onPluginFilterChange,
    pluginNames, typeFilter, onTypeFilterChange, typeItems, skillTagFilter,
    onSkillTagFilterChange, skillTagItems, sortBy, onSortChange,
    filtersOpen: controlledFiltersOpen, onFiltersOpenChange,
  } = props;
  const deepSearchDisabled = props.deepSearchDisabled ?? false;
  const deepSearchBusy = props.deepSearchBusy ?? false;
  const brainFilter = props.brainFilter ?? "all";
  const onBrainFilterChange = props.onBrainFilterChange ?? (() => undefined);
  const brainItems = props.brainItems ?? EMPTY_ARRAY;
  const focusMode = props.focusMode ?? false;
  const onFocusModeChange = props.onFocusModeChange ?? (() => undefined);
  const activeBrainId = props.activeBrainId ?? null;
  const problemFilter = rawProblemFilter ?? null;
  const onProblemFilterChange = rawOnProblemFilterChange ?? (() => undefined);
  const problemItems = rawProblemItems ?? EMPTY_ARRAY;
  const scopeFilter = props.scopeFilter ?? null;
  const onScopeFilterChange = props.onScopeFilterChange ?? (() => undefined);
  const scopeItems = props.scopeItems ?? EMPTY_ARRAY;
  const exposureFilter = props.exposureFilter ?? null;
  const onExposureFilterChange = props.onExposureFilterChange ?? (() => undefined);
  const exposureItems = props.exposureItems ?? EMPTY_ARRAY;
  const surfaceFilter = props.surfaceFilter ?? null;
  const onSurfaceFilterChange = props.onSurfaceFilterChange ?? (() => undefined);
  const surfaceItems = props.surfaceItems ?? EMPTY_ARRAY;
  const ownerFilter = props.ownerFilter ?? null;
  const onOwnerFilterChange = props.onOwnerFilterChange ?? (() => undefined);
  const ownerItems = props.ownerItems ?? EMPTY_ARRAY;
  const managementFilter = props.managementFilter ?? null;
  const onManagementFilterChange = props.onManagementFilterChange ?? (() => undefined);
  const managementItems = props.managementItems ?? EMPTY_ARRAY;
  const policyScopeFilter = props.policyScopeFilter ?? null;
  const onPolicyScopeFilterChange = props.onPolicyScopeFilterChange ?? (() => undefined);
  const policyScopeItems = props.policyScopeItems ?? EMPTY_ARRAY;
  const driftFilter = props.driftFilter ?? null;
  const onDriftFilterChange = props.onDriftFilterChange ?? (() => undefined);
  const driftItems = props.driftItems ?? EMPTY_ARRAY;
  const capabilityClientFilter = props.capabilityClientFilter ?? null;
  const onCapabilityClientFilterChange = props.onCapabilityClientFilterChange ?? (() => undefined);
  const capabilityClientItems = props.capabilityClientItems ?? EMPTY_ARRAY;
  const journeyCategoryFilter = props.journeyCategoryFilter ?? null;
  const onJourneyCategoryFilterChange = props.onJourneyCategoryFilterChange ?? (() => undefined);
  const journeyCategoryItems = props.journeyCategoryItems ?? EMPTY_ARRAY;
  const noteStateFilter = props.noteStateFilter ?? null;
  const onNoteStateFilterChange = props.onNoteStateFilterChange ?? (() => undefined);
  const noteStateItems = props.noteStateItems ?? EMPTY_ARRAY;
  const noteDomainFilter = props.noteDomainFilter ?? null;
  const onNoteDomainFilterChange = props.onNoteDomainFilterChange ?? (() => undefined);
  const noteDomainItems = props.noteDomainItems ?? EMPTY_ARRAY;
  const noteSourceFilter = props.noteSourceFilter ?? null;
  const onNoteSourceFilterChange = props.onNoteSourceFilterChange ?? (() => undefined);
  const noteSourceItems = props.noteSourceItems ?? EMPTY_ARRAY;
  const noteStatusFilter = props.noteStatusFilter ?? null;
  const onNoteStatusFilterChange = props.onNoteStatusFilterChange ?? (() => undefined);
  const noteStatusItems = props.noteStatusItems ?? EMPTY_ARRAY;
  useBrowseSearchShortcut();

  const sourceOptions = effectiveViewMode === "skills"
    ? [
        { id: "all", label: "Ownership: All" },
        { id: "augur", label: "Augur" },
        { id: "external", label: "External" },
        { id: "adopted", label: "Adopted" },
      ]
    : [];

  const clientOptions = masterClients.length > 0
    ? [{ id: "all", label: "Client: All" }, ...masterClients.map((client) => ({ id: client, label: CLIENT_DISPLAY_NAMES[client] || client }))]
    : [];

  const pluginOptions = pluginNames.length > 0
    ? [{ id: "all", label: "Plugin: All" }, ...pluginNames.map((plugin) => ({ id: plugin, label: plugin }))]
    : [];
  const typeChipLabel = effectiveViewMode === "notes"
    ? noteTypeFilterLabel(typeFilter)
    : optionLabel(typeItems, typeFilter);
  const activeNoteClassificationFilterCount = effectiveViewMode === "notes"
    ? [noteDomainFilter, noteSourceFilter, noteStatusFilter].filter(Boolean).length
    : 0;

  const activeFilterCount = [tagFilter, problemFilter, brainFilter !== "all" ? brainFilter : null, focusMode ? "focus" : null, scopeFilter, exposureFilter, surfaceFilter, ownerFilter, managementFilter, policyScopeFilter, driftFilter, capabilityClientFilter, sourceFilter, archivedFilter, masterFilter, pluginFilter, typeFilter, journeyCategoryFilter, noteStateFilter, skillTagFilter, kindFilter !== "all" ? kindFilter : null].filter(Boolean).length + activeNoteClassificationFilterCount;
  const [uncontrolledFiltersOpen, setUncontrolledFiltersOpen] = useState(false);
  const filtersOpen = controlledFiltersOpen ?? uncontrolledFiltersOpen;
  const setFiltersOpen = (next: boolean | ((current: boolean) => boolean)) => {
    const resolved = typeof next === "function" ? next(filtersOpen) : next;
    if (controlledFiltersOpen === undefined) {
      setUncontrolledFiltersOpen(resolved);
    }
    onFiltersOpenChange?.(resolved);
  };
  const isDeepSearchDisabled = deepSearchDisabled || deepSearchBusy || !search.trim() || !onDeepSearch;
  const clearAllFilters = () => {
    onTagFilterChange(null);
    onProblemFilterChange(null);
    onBrainFilterChange("all");
    onFocusModeChange(false);
    onScopeFilterChange(null);
    onSourceFilterChange(null);
    onArchivedFilterChange(null);
    onExposureFilterChange(null);
    onSurfaceFilterChange(null);
    onOwnerFilterChange(null);
    onManagementFilterChange(null);
    onPolicyScopeFilterChange(null);
    onDriftFilterChange(null);
    onCapabilityClientFilterChange(null);
    onMasterFilterChange(null);
    onPluginFilterChange(null);
    onTypeFilterChange(null);
    onJourneyCategoryFilterChange(null);
    onNoteStateFilterChange(null);
    onNoteDomainFilterChange(null);
    onNoteSourceFilterChange(null);
    onNoteStatusFilterChange(null);
    onSkillTagFilterChange(null);
    onKindFilterChange("all");
  };

  const activeFilterChips = buildActiveFilterChips({
    activeBrainId,
    archivedFilter,
    archivedItems,
    brainFilter,
    brainItems,
    capabilityClientFilter,
    capabilityClientItems,
    clientOptions,
    driftFilter,
    driftItems,
    effectiveViewMode,
    exposureFilter,
    exposureItems,
    focusMode,
    kindFilter,
    managementFilter,
    managementItems,
    masterFilter,
    onArchivedFilterChange,
    onBrainFilterChange,
    onCapabilityClientFilterChange,
    onNoteDomainFilterChange,
    onNoteSourceFilterChange,
    onNoteStatusFilterChange,
    onDriftFilterChange,
    onExposureFilterChange,
    onFocusModeChange,
    onKindFilterChange,
    onManagementFilterChange,
    onMasterFilterChange,
    onOwnerFilterChange,
    onPluginFilterChange,
    onPolicyScopeFilterChange,
    onProblemFilterChange,
    onScopeFilterChange,
    onSkillTagFilterChange,
    onSourceFilterChange,
    onSurfaceFilterChange,
    onTagFilterChange,
    onTypeFilterChange,
    noteDomainFilter,
    noteDomainItems,
    noteSourceFilter,
    noteSourceItems,
    noteStatusFilter,
    noteStatusItems,
    ownerFilter,
    ownerItems,
    pluginFilter,
    pluginOptions,
    policyScopeFilter,
    policyScopeItems,
    problemFilter,
    problemItems,
    scopeFilter,
    scopeItems,
    skillTagFilter,
    skillTagItems,
    sourceFilter,
    sourceOptions,
    surfaceFilter,
    surfaceItems,
    tagFilter,
    tagItems,
    typeChipLabel,
    typeFilter,
    journeyCategoryFilter,
    journeyCategoryItems,
    onJourneyCategoryFilterChange,
  });

  const filterControls = buildFilterControls({
    archivedFilter,
    archivedItems,
    brainFilter,
    brainItems,
    capabilityClientFilter,
    capabilityClientItems,
    clientOptions,
    driftFilter,
    driftItems,
    effectiveViewMode,
    exposureFilter,
    exposureItems,
    focusMode,
    kindFilter,
    managementFilter,
    managementItems,
    masterFilter,
    onArchivedFilterChange,
    onBrainFilterChange,
    onCapabilityClientFilterChange,
    onNoteDomainFilterChange,
    onNoteSourceFilterChange,
    onNoteStatusFilterChange,
    onDriftFilterChange,
    onExposureFilterChange,
    onKindFilterChange,
    onManagementFilterChange,
    onMasterFilterChange,
    onOwnerFilterChange,
    onPluginFilterChange,
    onProblemFilterChange,
    onPolicyScopeFilterChange,
    onScopeFilterChange,
    onSkillTagFilterChange,
    onSourceFilterChange,
    onSurfaceFilterChange,
    onTagFilterChange,
    onTypeFilterChange,
    noteDomainFilter,
    noteDomainItems,
    noteSourceFilter,
    noteSourceItems,
    noteStatusFilter,
    noteStatusItems,
    ownerFilter,
    ownerItems,
    pluginFilter,
    pluginOptions,
    policyScopeFilter,
    policyScopeItems,
    problemFilter,
    problemItems,
    scopeFilter,
    scopeItems,
    skillTagFilter,
    skillTagItems,
    sourceFilter,
    sourceOptions,
    surfaceFilter,
    surfaceItems,
    tagFilter,
    tagItems,
    typeFilter,
    typeItems,
  });

  return (
    <>
      <BrowseToolbarMainRow
        activeCategory={activeCategory}
        activeFilterCount={activeFilterCount}
        deepSearchBusy={deepSearchBusy}
        displayMode={displayMode}
        filtersOpen={filtersOpen}
        isDeepSearchDisabled={isDeepSearchDisabled}
        onDeepSearch={onDeepSearch}
        onDisplayModeChange={onDisplayModeChange}
        onFiltersOpenToggle={() => setFiltersOpen((current) => !current)}
        onSearchChange={onSearchChange}
        onSemanticSearch={onSemanticSearch}
        onSortChange={onSortChange}
        search={search}
        sortBy={sortBy}
      />
      <ActiveFilterChips chips={activeFilterChips} onClearAll={clearAllFilters} />
      <NotesCategoryFilterChips
        activeCategory={journeyCategoryFilter}
        onChange={onJourneyCategoryFilterChange}
        options={journeyCategoryItems}
        show={effectiveViewMode === "notes"}
      />
      <NotesStateFilterChips
        activeState={noteStateFilter}
        onChange={onNoteStateFilterChange}
        options={noteStateItems}
        show={effectiveViewMode === "notes"}
      />
      <FilterControlsPanel
        activeFilterCount={activeFilterCount}
        controls={filterControls}
        open={filtersOpen}
        onClearAll={clearAllFilters}
        onSortChange={onSortChange}
        sortBy={sortBy}
      />
      <SemanticSearchStatus
        error={semanticError}
        loading={semanticLoading}
        onRetry={() => onSemanticSearch(search)}
        resultCount={semanticResults.length}
        search={search}
        searched={semanticSearched}
      />
    </>
  );
}

function useBrowseSearchShortcut() {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const target = event.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) return;
        event.preventDefault();
        document.getElementById("browse-search")?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);
}
