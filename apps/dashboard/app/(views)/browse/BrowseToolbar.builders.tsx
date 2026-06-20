"use client";

import {
  type ViewMode,
  type BrowsePageKindFilter,
  type NoteDomain,
  type NoteSource,
  type NoteStatus,
} from "@/lib/browse/types";
import type { BrainFilter } from "./useBrowseState";
import type { OverlayScopeFilter } from "@/lib/browse/overlay";
import type { FilterChip, FilterControl, FilterOption } from "./BrowseToolbar.types";
import { tagSectionLabel, optionLabel, PAGE_KIND_OPTIONS } from "./BrowseToolbar.helpers";
import { FilterSelect, KindSegmentedControl } from "./BrowseToolbar.controls";
import { NotesTypeFilterControl } from "./BrowseToolbar.chips";

export function buildActiveFilterChips({
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
  onDriftFilterChange,
  onExposureFilterChange,
  onFocusModeChange,
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
  onNoteDomainFilterChange,
  onNoteSourceFilterChange,
  onNoteStatusFilterChange,
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
}: {
  activeBrainId: string | null;
  archivedFilter: string | null;
  archivedItems: FilterOption[];
  brainFilter: BrainFilter;
  brainItems: FilterOption[];
  capabilityClientFilter: string | null;
  capabilityClientItems: FilterOption[];
  clientOptions: FilterOption[];
  driftFilter: string | null;
  driftItems: FilterOption[];
  effectiveViewMode: ViewMode;
  exposureFilter: string | null;
  exposureItems: FilterOption[];
  focusMode: boolean;
  kindFilter: BrowsePageKindFilter;
  managementFilter: string | null;
  managementItems: FilterOption[];
  masterFilter: string | null;
  onArchivedFilterChange: (value: string | null) => void;
  onBrainFilterChange: (brain: BrainFilter) => void;
  onCapabilityClientFilterChange: (client: string | null) => void;
  onDriftFilterChange: (drift: string | null) => void;
  onExposureFilterChange: (status: string | null) => void;
  onFocusModeChange: (value: boolean) => void;
  onKindFilterChange: (kind: BrowsePageKindFilter) => void;
  onManagementFilterChange: (management: string | null) => void;
  onMasterFilterChange: (client: string | null) => void;
  onOwnerFilterChange: (owner: string | null) => void;
  onPluginFilterChange: (plugin: string | null) => void;
  onProblemFilterChange: (problem: string | null) => void;
  onPolicyScopeFilterChange: (scope: string | null) => void;
  onScopeFilterChange: (scope: OverlayScopeFilter | null) => void;
  onSkillTagFilterChange: (tag: string | null) => void;
  onSourceFilterChange: (source: string | null) => void;
  onSurfaceFilterChange: (surface: string | null) => void;
  onTagFilterChange: (tag: string | null) => void;
  onTypeFilterChange: (type: string | null) => void;
  noteDomainFilter: NoteDomain | null;
  noteDomainItems: FilterOption[];
  noteSourceFilter: NoteSource | null;
  noteSourceItems: FilterOption[];
  noteStatusFilter: NoteStatus | null;
  noteStatusItems: FilterOption[];
  onNoteDomainFilterChange: (domain: NoteDomain | null) => void;
  onNoteSourceFilterChange: (source: NoteSource | null) => void;
  onNoteStatusFilterChange: (status: NoteStatus | null) => void;
  ownerFilter: string | null;
  ownerItems: FilterOption[];
  pluginFilter: string | null;
  pluginOptions: FilterOption[];
  policyScopeFilter: string | null;
  policyScopeItems: FilterOption[];
  problemFilter: string | null;
  problemItems: FilterOption[];
  scopeFilter: OverlayScopeFilter | null;
  scopeItems: FilterOption[];
  skillTagFilter: string | null;
  skillTagItems: FilterOption[];
  sourceFilter: string | null;
  sourceOptions: FilterOption[];
  surfaceFilter: string | null;
  surfaceItems: FilterOption[];
  tagFilter: string | null;
  tagItems: FilterOption[];
  typeChipLabel: string | null;
  typeFilter: string | null;
  journeyCategoryFilter: string | null;
  journeyCategoryItems: FilterOption[];
  onJourneyCategoryFilterChange: (category: string | null) => void;
}): FilterChip[] {
  return [
    tagFilter ? {
      id: "primary-tag",
      label: `${tagSectionLabel(effectiveViewMode)}: ${optionLabel(tagItems, tagFilter)}`,
      onClear: () => onTagFilterChange(null),
    } : null,
    problemFilter ? {
      id: "problem",
      label: `Problems: ${optionLabel(problemItems, problemFilter)}`,
      onClear: () => onProblemFilterChange(null),
    } : null,
    focusMode ? {
      id: "focus",
      label: `Focus: ${activeBrainId ?? "active brain"}`,
      onClear: () => onFocusModeChange(false),
    } : null,
    brainFilter !== "all" && !focusMode ? {
      id: "brain",
      label: `Brain: ${optionLabel(brainItems, brainFilter)}`,
      onClear: () => onBrainFilterChange("all"),
    } : null,
    archivedFilter && effectiveViewMode === "adrs" ? {
      id: "archived",
      label: `Status: ${optionLabel(archivedItems, archivedFilter)}`,
      onClear: () => onArchivedFilterChange(null),
    } : null,
    scopeFilter ? {
      id: "scope",
      label: `Scope: ${optionLabel(scopeItems, scopeFilter)}`,
      onClear: () => onScopeFilterChange(null),
    } : null,
    exposureFilter ? {
      id: "exposure",
      label: `Exposure: ${optionLabel(exposureItems, exposureFilter)}`,
      onClear: () => onExposureFilterChange(null),
    } : null,
    surfaceFilter ? {
      id: "surface",
      label: `Surface: ${optionLabel(surfaceItems, surfaceFilter)}`,
      onClear: () => onSurfaceFilterChange(null),
    } : null,
    ownerFilter ? {
      id: "owner",
      label: `Owner: ${optionLabel(ownerItems, ownerFilter)}`,
      onClear: () => onOwnerFilterChange(null),
    } : null,
    managementFilter ? {
      id: "management",
      label: `Management: ${optionLabel(managementItems, managementFilter)}`,
      onClear: () => onManagementFilterChange(null),
    } : null,
    policyScopeFilter ? {
      id: "policy-scope",
      label: `Policy Scope: ${optionLabel(policyScopeItems, policyScopeFilter)}`,
      onClear: () => onPolicyScopeFilterChange(null),
    } : null,
    driftFilter ? {
      id: "drift",
      label: `Drift: ${optionLabel(driftItems, driftFilter)}`,
      onClear: () => onDriftFilterChange(null),
    } : null,
    capabilityClientFilter ? {
      id: "capability-client",
      label: `Capability Client: ${optionLabel(capabilityClientItems, capabilityClientFilter)}`,
      onClear: () => onCapabilityClientFilterChange(null),
    } : null,
    sourceFilter ? {
      id: "ownership",
      label: `Ownership: ${optionLabel(sourceOptions, sourceFilter)}`,
      onClear: () => onSourceFilterChange(null),
    } : null,
    masterFilter ? {
      id: "client",
      label: `Client: ${optionLabel(clientOptions, masterFilter)}`,
      onClear: () => onMasterFilterChange(null),
    } : null,
    pluginFilter ? {
      id: "plugin",
      label: `Plugin: ${optionLabel(pluginOptions, pluginFilter)}`,
      onClear: () => onPluginFilterChange(null),
    } : null,
    typeFilter ? {
      id: "type",
      label: `Type: ${typeChipLabel}`,
      onClear: () => onTypeFilterChange(null),
    } : null,
    journeyCategoryFilter && effectiveViewMode === "notes" ? {
      id: "journey-category",
      label: `Category: ${optionLabel(journeyCategoryItems, journeyCategoryFilter)}`,
      onClear: () => onJourneyCategoryFilterChange(null),
    } : null,
    noteDomainFilter && effectiveViewMode === "notes" ? {
      id: "note-domain",
      label: `Domain: ${optionLabel(noteDomainItems, noteDomainFilter)}`,
      onClear: () => onNoteDomainFilterChange(null),
    } : null,
    noteSourceFilter && effectiveViewMode === "notes" ? {
      id: "note-source",
      label: `Source: ${optionLabel(noteSourceItems, noteSourceFilter)}`,
      onClear: () => onNoteSourceFilterChange(null),
    } : null,
    noteStatusFilter && effectiveViewMode === "notes" ? {
      id: "note-status",
      label: `Status: ${optionLabel(noteStatusItems, noteStatusFilter)}`,
      onClear: () => onNoteStatusFilterChange(null),
    } : null,
    skillTagFilter ? {
      id: "skill-tag",
      label: `Tag: ${optionLabel(skillTagItems, skillTagFilter)}`,
      onClear: () => onSkillTagFilterChange(null),
    } : null,
    kindFilter !== "all" && effectiveViewMode === "pages" ? {
      id: "kind",
      label: `Kind: ${PAGE_KIND_OPTIONS.find((option) => option.id === kindFilter)?.label ?? kindFilter}`,
      onClear: () => onKindFilterChange("all"),
    } : null,
  ].filter((chip): chip is FilterChip => chip !== null);
}

export function buildFilterControls({
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
  onNoteDomainFilterChange,
  onNoteSourceFilterChange,
  onNoteStatusFilterChange,
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
}: {
  archivedFilter: string | null;
  archivedItems: FilterOption[];
  brainFilter: BrainFilter;
  brainItems: FilterOption[];
  capabilityClientFilter: string | null;
  capabilityClientItems: FilterOption[];
  clientOptions: FilterOption[];
  driftFilter: string | null;
  driftItems: FilterOption[];
  effectiveViewMode: ViewMode;
  exposureFilter: string | null;
  exposureItems: FilterOption[];
  focusMode: boolean;
  kindFilter: BrowsePageKindFilter;
  managementFilter: string | null;
  managementItems: FilterOption[];
  masterFilter: string | null;
  onArchivedFilterChange: (value: string | null) => void;
  onBrainFilterChange: (brain: BrainFilter) => void;
  onCapabilityClientFilterChange: (client: string | null) => void;
  onDriftFilterChange: (drift: string | null) => void;
  onExposureFilterChange: (status: string | null) => void;
  onKindFilterChange: (kind: BrowsePageKindFilter) => void;
  onManagementFilterChange: (management: string | null) => void;
  onMasterFilterChange: (client: string | null) => void;
  onOwnerFilterChange: (owner: string | null) => void;
  onPluginFilterChange: (plugin: string | null) => void;
  onProblemFilterChange: (problem: string | null) => void;
  onPolicyScopeFilterChange: (scope: string | null) => void;
  onScopeFilterChange: (scope: OverlayScopeFilter | null) => void;
  onSkillTagFilterChange: (tag: string | null) => void;
  onSourceFilterChange: (source: string | null) => void;
  onSurfaceFilterChange: (surface: string | null) => void;
  onTagFilterChange: (tag: string | null) => void;
  onTypeFilterChange: (type: string | null) => void;
  noteDomainFilter: NoteDomain | null;
  noteDomainItems: FilterOption[];
  noteSourceFilter: NoteSource | null;
  noteSourceItems: FilterOption[];
  noteStatusFilter: NoteStatus | null;
  noteStatusItems: FilterOption[];
  onNoteDomainFilterChange: (domain: NoteDomain | null) => void;
  onNoteSourceFilterChange: (source: NoteSource | null) => void;
  onNoteStatusFilterChange: (status: NoteStatus | null) => void;
  ownerFilter: string | null;
  ownerItems: FilterOption[];
  pluginFilter: string | null;
  pluginOptions: FilterOption[];
  policyScopeFilter: string | null;
  policyScopeItems: FilterOption[];
  problemFilter: string | null;
  problemItems: FilterOption[];
  scopeFilter: OverlayScopeFilter | null;
  scopeItems: FilterOption[];
  skillTagFilter: string | null;
  skillTagItems: FilterOption[];
  sourceFilter: string | null;
  sourceOptions: FilterOption[];
  surfaceFilter: string | null;
  surfaceItems: FilterOption[];
  tagFilter: string | null;
  tagItems: FilterOption[];
  typeFilter: string | null;
  typeItems: FilterOption[];
}): FilterControl[] {
  return [
    ...(effectiveViewMode === "pages" ? [{
      id: "kind",
      node: (
        <KindSegmentedControl
          value={kindFilter}
          onChange={onKindFilterChange}
        />
      ),
    }] : [{
      id: "primary-tag",
      node: (
        <FilterSelect
          label={tagSectionLabel(effectiveViewMode)}
          value={tagFilter}
          onChange={onTagFilterChange}
          options={tagItems}
        />
      ),
    }]),
    ...(problemItems.length > 0 ? [{
      id: "problem",
      node: (
        <FilterSelect
          label="Problems"
          value={problemFilter}
          onChange={onProblemFilterChange}
          options={problemItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(brainItems.length > 0 && !focusMode ? [{
      id: "brain",
      node: (
        <FilterSelect
          label="Brain"
          value={brainFilter === "all" ? null : brainFilter}
          onChange={(value) => onBrainFilterChange((value ?? "all") as BrainFilter)}
          options={brainItems}
        />
      ),
    }] : []),
    ...(effectiveViewMode === "adrs" ? [{
      id: "archived",
      node: (
        <FilterSelect
          label="Status"
          value={archivedFilter}
          onChange={onArchivedFilterChange}
          options={archivedItems}
        />
      ),
    }] : []),
    ...(scopeItems.length > 0 ? [{
      id: "scope",
      node: (
        <FilterSelect
          label="Scope"
          value={scopeFilter}
          onChange={(value) => onScopeFilterChange(value as OverlayScopeFilter | null)}
          options={scopeItems}
        />
      ),
    }] : []),
    ...(exposureItems.length > 0 ? [{
      id: "exposure",
      node: (
        <FilterSelect
          label="Exposure"
          value={exposureFilter}
          onChange={onExposureFilterChange}
          options={exposureItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(surfaceItems.length > 0 ? [{
      id: "surface",
      node: (
        <FilterSelect
          label="Surface"
          value={surfaceFilter}
          onChange={onSurfaceFilterChange}
          options={surfaceItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(ownerItems.length > 0 ? [{
      id: "owner",
      node: (
        <FilterSelect
          label="Owner"
          value={ownerFilter}
          onChange={onOwnerFilterChange}
          options={ownerItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(managementItems.length > 0 ? [{
      id: "management",
      node: (
        <FilterSelect
          label="Management"
          value={managementFilter}
          onChange={onManagementFilterChange}
          options={managementItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(policyScopeItems.length > 0 ? [{
      id: "policy-scope",
      node: (
        <FilterSelect
          label="Policy Scope"
          value={policyScopeFilter}
          onChange={onPolicyScopeFilterChange}
          options={policyScopeItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(driftItems.length > 0 ? [{
      id: "drift",
      node: (
        <FilterSelect
          label="Drift"
          value={driftFilter}
          onChange={onDriftFilterChange}
          options={driftItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(capabilityClientItems.length > 0 ? [{
      id: "capability-client",
      node: (
        <FilterSelect
          label="Capability Client"
          value={capabilityClientFilter}
          onChange={onCapabilityClientFilterChange}
          options={capabilityClientItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(sourceOptions.length > 0 ? [{
      id: "ownership",
      node: (
        <FilterSelect
          label="Ownership"
          value={sourceFilter}
          onChange={onSourceFilterChange}
          options={sourceOptions}
        />
      ),
    }] : []),
    ...(effectiveViewMode === "notes" ? [{
      id: "note-domain",
      node: (
        <FilterSelect
          label="Domain"
          value={noteDomainFilter}
          onChange={(value) => onNoteDomainFilterChange(value as NoteDomain | null)}
          options={noteDomainItems}
          showWhenSingle
        />
      ),
    }, {
      id: "note-source",
      node: (
        <FilterSelect
          label="Source"
          value={noteSourceFilter}
          onChange={(value) => onNoteSourceFilterChange(value as NoteSource | null)}
          options={noteSourceItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(effectiveViewMode === "notes" && noteStatusItems.length > 0 ? [{
      id: "note-status",
      node: (
        <FilterSelect
          label="Status"
          value={noteStatusFilter}
          onChange={(value) => onNoteStatusFilterChange(value as NoteStatus | null)}
          options={noteStatusItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(clientOptions.length > 0 ? [{
      id: "client",
      node: (
        <FilterSelect
          label="Client"
          value={masterFilter}
          onChange={onMasterFilterChange}
          options={clientOptions}
        />
      ),
    }] : []),
    ...(pluginOptions.length > 0 ? [{
      id: "plugin",
      node: (
        <FilterSelect
          label="Plugin"
          value={pluginFilter}
          onChange={onPluginFilterChange}
          options={pluginOptions}
        />
      ),
    }] : []),
    ...(typeItems.length > 0 ? [{
      id: "type",
      node: (
        effectiveViewMode === "notes" ? (
          <NotesTypeFilterControl
            value={typeFilter}
            onChange={onTypeFilterChange}
            options={typeItems}
          />
        ) : (
          <FilterSelect
            label="Type"
            value={typeFilter}
            onChange={onTypeFilterChange}
            options={typeItems}
          />
        )
      ),
    }] : []),
    ...(skillTagItems.length > 0 ? [{
      id: "skill-tag",
      node: (
        <FilterSelect
          label="Tag"
          value={skillTagFilter}
          onChange={onSkillTagFilterChange}
          options={skillTagItems}
        />
      ),
    }] : []),
  ];
}
