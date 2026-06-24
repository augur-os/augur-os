"use client";

import { useCallback, useRef, useState } from "react";
import { ChevronDown, GripVertical, X } from "lucide-react";
import { toast } from "sonner";
import { BrowseCategoryNav } from "@/components/shared/BrowseCategoryNav";
import { ApiRoutesStats, useBrowseCategoryActions } from "@/components/shared/BrowseCategoryActions";
import { BrowseDetailPanel, BrowseItemDetailPanel } from "@/components/shared/BrowseDetailPanel";
import { BackgroundRoutineDetailPanel } from "@/components/shared/BackgroundRoutineDetailPanel";
import { getStalenessLevel } from "@/lib/timestamps";
import { mcpCall } from "@/lib/mcp/client";
import { parseSkillDemos } from "@/lib/browse/cardModel";
import { BrowseToolbar } from "./BrowseToolbar";
import { BrowseContentGrid } from "./BrowseContentGrid";
import { BrowseAddFolderDialog } from "./BrowseAddFolderDialog";
import { BrowseAttachDocumentSourceDialog } from "./BrowseAttachDocumentSourceDialog";
import { BrowseFolderContextMenu } from "./BrowseFolderContextMenu";
import { SelectionActionBar } from "@/components/shared/SelectionActionBar";
import { selectionActionsForViewMode } from "@/lib/browse/selectionActions";
import { CapabilityPolicyPanel } from "./CapabilityPolicyPanel";
import { NoteDropZone } from "@/features/browse/NoteDropZone";
import { NoteFAB } from "@/features/browse/NoteFAB";
import { NoteModal } from "@/features/browse/NoteModal";
import ConfirmDialog from "@/components/blocks/ConfirmDialog";
import {
  canAttachDocumentSourceToContext,
  type BrowsePageController,
} from "./BrowsePageClient.controller";

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  skills: "Explore capability packages across Augur",
  pages: "Dashboard pages across all hubs",
  documents: "User documents and imported files",
  vault: "Notes and knowledge base entries",
  notes: "Captured URLs, files, thoughts, prompts, audio, meetings, and images",
  actions: "Runnable action and dispatch targets",
  commands: "Command docs from Augur and skill command folders",
  prompts: "Prompt templates and reusable AI inputs",
  integrations: "Connected systems, clients, and external tools",
  profile: "Voice-profile interview and personalization state",
  "loops": "Autonomous triggers across schedules, daemon services, launchd agents, GitHub Actions, and MCP background tasks",
  wiki: "Auto-generated AI summary pages and knowledge digests",
  agents: "AI agent configurations and profiles",
  "mcp-tools": "MCP tools and operator-facing integrations",
  "mcp-servers": "Configured MCP servers, live runtime processes, and stale leftovers",
  logs: "Runtime logs for debugging and operational inspection",
  tests: "Test suites and results",
  "api-routes": "Dashboard API endpoints",
  scripts: "Automation and utility scripts",
};

const STALENESS_DOT_COLORS = {
  fresh: "bg-[var(--accent-success)]",
  aging: "bg-[var(--accent-warning)]",
  stale: "bg-[var(--accent-danger)]",
} as const;

const STALENESS_DOT_LABELS = {
  fresh: "Fresh",
  aging: "Aging",
  stale: "Stale",
} as const;

function StalenessDot({ timestamp }: { timestamp: string | undefined }) {
  if (!timestamp) return null;
  const level = getStalenessLevel(timestamp);
  return (
    <span className={`inline-block size-2 rounded-full ${STALENESS_DOT_COLORS[level]} ml-1.5 shrink-0`} title={STALENESS_DOT_LABELS[level]}>
      <span className="sr-only">{STALENESS_DOT_LABELS[level]}</span>
    </span>
  );
}

export function BrowsePageScaffold({ controller }: { controller: BrowsePageController }) {
  return (
    <NoteDropZone onDrop={controller.handleDrop}>
      <BrowseMainContent controller={controller} />
      <NoteFAB
        queue={controller.noteQueue}
        onAddClick={() => controller.setNoteModalOpen(true)}
        onRetry={controller.retryNoteItem}
        suppress={controller.toolbarFiltersOpen}
      />
      <NoteModal
        open={controller.noteModalOpen}
        onClose={() => controller.setNoteModalOpen(false)}
        onSubmitFiles={controller.uploadFiles}
        onSubmitUrl={controller.handleSubmitUrl}
        onSubmitText={controller.handleSubmitText}
      />
      <BrowseAddFolderDialog
        open={controller.addFolderOpen}
        onOpenChange={controller.setAddFolderOpen}
        onScan={controller.scanFolderForContext}
        onInitialize={async (projectRoot) => {
          const result = await mcpCall("brain-init", { project_root: projectRoot, run_sync: false });
          if (result && typeof result === "object" && "success" in result && result.success === false) {
            const payload = result as { error?: unknown };
            const error = typeof payload.error === "string" ? payload.error : "Folder initialization failed.";
            throw new Error(error);
          }
          controller.refetch();
          return result;
        }}
      />
      <BrowseAttachDocumentSourceDialog
        open={controller.attachDocumentSourceOpen}
        brainId={controller.activeFolderContext?.brain_id || ""}
        brainLabel={controller.activeFolderContext?.label || "Project"}
        onOpenChange={controller.setAttachDocumentSourceOpen}
        onAttached={controller.refetch}
      />
      {controller.selectedCapability && (
        <CapabilityPolicyPanel
          item={controller.selectedCapability}
          onClose={() => controller.setSelectedCapability(null)}
          onApplied={() => {
            controller.setSelectedCapability(null);
            controller.refetch();
          }}
        />
      )}
    </NoteDropZone>
  );
}

function BrowseMainContent({ controller }: { controller: BrowsePageController }) {
  return (
    <div className="min-h-0">
      <div className="pl-1 pr-1">
        <BrowseSummaryPanel controller={controller} />
        <BrowseToolbarPanel controller={controller} />
        {controller.effectiveViewMode === "api-routes" && (
          <div className="mt-4">
            <ApiRoutesStats itemCount={controller.filtered.length} />
          </div>
        )}
      </div>
      <BrowseSplitPane controller={controller} />
    </div>
  );
}

function BrowseSummaryPanel({ controller }: { controller: BrowsePageController }) {
  return (
    <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)]/70 p-2.5 sm:p-3 md:rounded-2xl md:p-4">
      <div className="flex flex-col gap-2 md:gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold text-[var(--text-primary)] tracking-tight sm:text-2xl">
              Browse <span className="text-[var(--text-muted)] font-semibold">·</span> {controller.activeCategory.label}
            </h1>
            <span className="inline-flex items-center rounded-full border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)] tabular-nums" suppressHydrationWarning>
              {controller.summaryBadgeText}
            </span>
          </div>
          <p className="mt-1.5 hidden max-w-2xl text-xs text-[var(--text-muted)] sm:block">
            {CATEGORY_DESCRIPTIONS[controller.effectiveViewMode] || "Explore all Augur resources"}.
          </p>
        </div>
        <BrowseSummaryActions controller={controller} />
      </div>
      <BrowseCategoryPicker controller={controller} />
    </section>
  );
}

function BrowseSummaryActions({ controller }: { controller: BrowsePageController }) {
  // One header control: the brain-scope selector IS the menu. Scope switching,
  // index freshness, and category actions all live in its popover so the header
  // carries a single button instead of three competing pills.
  const { items: actionItems, modal: actionsModal } = useBrowseCategoryActions({
    category: controller.effectiveViewMode,
    activeCategory: controller.activeCategory,
    itemCount: controller.filtered.length,
    onRefetch: controller.refetch,
    projectQuestionAction: controller.projectQuestionAction,
    onAddContent: () => controller.setNoteModalOpen(true),
    onSweepVisible: controller.handleSweepVisible,
    sweeping: controller.sweeping,
    onReindex: controller.handleReindex,
    reindexing: controller.reindexing,
    onAttachDocumentSource: canAttachDocumentSourceToContext(controller.activeFolderContext)
      ? () => controller.setAttachDocumentSourceOpen(true)
      : undefined,
  });

  return (
    <div className="flex flex-wrap items-center gap-1.5 md:gap-2 lg:justify-end" suppressHydrationWarning>
      <BrowseFolderContextMenu
        context={controller.activeFolderContext}
        options={controller.folderContextOptions}
        loading={controller.folderContextLoading}
        freshness={
          controller.currentFreshness
            ? { timestamp: controller.currentFreshness, level: controller.stalenessLevel }
            : null
        }
        actionItems={actionItems}
        actionsLabel={`${controller.activeCategory.label} actions`}
        onSelect={async (context) => {
          try {
            const repaired = await controller.setActiveFolderContext(context);
            if (repaired) {
              toast.success(`Repaired and switched to ${context.label}.`);
            }
          } catch (error) {
            const message = error instanceof Error ? error.message : "Unable to switch folder context.";
            toast.error(message);
          }
        }}
        onAddFolder={() => {
          controller.setAddFolderOpen(true);
        }}
      />
      {actionsModal}
    </div>
  );
}

function BrowseCategoryPicker({ controller }: { controller: BrowsePageController }) {
  return (
    <div className="mt-2 border-t border-[var(--border-color)] pt-2 md:mt-4 md:pt-3">
      <div className="relative md:hidden">
        <label htmlFor="browse-mobile-category" className="sr-only">
          Browse category
        </label>
        <select
          id="browse-mobile-category"
          value={controller.effectiveViewMode}
          onChange={(event) => controller.changeView(event.target.value)}
          className="h-10 w-full appearance-none rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 pr-10 text-sm font-medium text-[var(--text-primary)] outline-none transition-colors focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]/20"
          aria-label="Browse category"
        >
          {controller.visibleCategories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden="true" />
      </div>
      <div className="hidden md:block">
        <BrowseCategoryNav
          categories={controller.visibleCategories}
          activeId={controller.effectiveViewMode}
          onSelect={controller.changeView}
          renderTrailing={(category) => (
            <StalenessDot timestamp={controller.categoryFreshness[category.id]} />
          )}
        />
      </div>
    </div>
  );
}

function BrowseToolbarPanel({ controller }: { controller: BrowsePageController }) {
  return (
    <div className="mt-3 rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)]/55 p-3">
      <BrowseToolbar
        activeCategory={controller.activeCategory}
        effectiveViewMode={controller.effectiveViewMode}
        displayMode={controller.displayMode}
        onDisplayModeChange={controller.setDisplayMode}
        search={controller.search}
        onSearchChange={controller.setSearch}
        onSemanticSearch={controller.handleSemanticSearch}
        semanticLoading={controller.semanticLoading}
        semanticResults={controller.activeSemanticResults}
        semanticSearched={controller.semanticSearchActive}
        semanticError={controller.semanticSearchActive ? controller.semanticError : null}
        onDeepSearch={controller.handleDeepSearch}
        deepSearchDisabled={!controller.search.trim()}
        deepSearchBusy={controller.isExecuting && controller.lastActionId === "browse.deep-search"}
        tagFilter={controller.tagFilter}
        onTagFilterChange={controller.setTagFilter}
        tagItems={controller.tagItems}
        problemFilter={controller.problemFilter}
        onProblemFilterChange={controller.setProblemFilter}
        problemItems={controller.problemItems}
        brainFilter={controller.brainFilter}
        onBrainFilterChange={controller.setBrainFilter}
        brainItems={controller.brainItems}
        focusMode={controller.focusMode}
        onFocusModeChange={controller.setFocusMode}
        activeBrainId={controller.activeBrainId}
        scopeFilter={controller.scopeFilter}
        onScopeFilterChange={controller.setScopeFilter}
        scopeItems={controller.scopeItems}
        exposureFilter={controller.exposureFilter}
        onExposureFilterChange={controller.setExposureFilter}
        exposureItems={controller.exposureItems}
        surfaceFilter={controller.surfaceFilter}
        onSurfaceFilterChange={controller.setSurfaceFilter}
        surfaceItems={controller.surfaceItems}
        ownerFilter={controller.ownerFilter}
        onOwnerFilterChange={controller.setOwnerFilter}
        ownerItems={controller.ownerItems}
        managementFilter={controller.managementFilter}
        onManagementFilterChange={controller.setManagementFilter}
        managementItems={controller.managementItems}
        policyScopeFilter={controller.policyScopeFilter}
        onPolicyScopeFilterChange={controller.setPolicyScopeFilter}
        policyScopeItems={controller.policyScopeItems}
        driftFilter={controller.driftFilter}
        onDriftFilterChange={controller.setDriftFilter}
        driftItems={controller.driftItems}
        capabilityClientFilter={controller.capabilityClientFilter}
        onCapabilityClientFilterChange={controller.setCapabilityClientFilter}
        capabilityClientItems={controller.capabilityClientItems}
        sourceFilter={controller.sourceFilter}
        onSourceFilterChange={controller.setSourceFilter}
        kindFilter={controller.kindFilter}
        onKindFilterChange={controller.setKindFilter}
        archivedFilter={controller.archivedFilter}
        onArchivedFilterChange={controller.setArchivedFilter}
        archivedItems={controller.archivedItems}
        masterFilter={controller.masterFilter}
        onMasterFilterChange={controller.setMasterFilter}
        masterClients={controller.masterClients}
        pluginFilter={controller.pluginFilter}
        onPluginFilterChange={controller.setPluginFilter}
        pluginNames={controller.pluginNames}
        typeFilter={controller.typeFilter}
        onTypeFilterChange={controller.setTypeFilter}
        typeItems={controller.typeItems}
        journeyCategoryFilter={controller.journeyCategoryFilter}
        onJourneyCategoryFilterChange={controller.setJourneyCategoryFilter}
        journeyCategoryItems={controller.journeyCategoryItems}
        noteStateFilter={controller.noteStateFilter}
        onNoteStateFilterChange={controller.setNoteStateFilter}
        noteStateItems={controller.noteStateItems}
        noteDomainFilter={controller.noteDomainFilter}
        onNoteDomainFilterChange={controller.setNoteDomainFilter}
        noteDomainItems={controller.noteDomainItems}
        noteSourceFilter={controller.noteSourceFilter}
        onNoteSourceFilterChange={controller.setNoteSourceFilter}
        noteSourceItems={controller.noteSourceItems}
        noteStatusFilter={controller.noteStatusFilter}
        onNoteStatusFilterChange={controller.setNoteStatusFilter}
        noteStatusItems={controller.noteStatusItems}
        skillTagFilter={controller.skillTagFilter}
        onSkillTagFilterChange={controller.setSkillTagFilter}
        skillTagItems={controller.skillTagItems}
        sortBy={controller.sortBy}
        onSortChange={controller.setSortBy}
        filtersOpen={controller.toolbarFiltersOpen}
        onFiltersOpenChange={controller.setToolbarFiltersOpen}
        selectionMode={controller.selectionMode}
        onToggleSelectionMode={controller.toggleSelectionMode}
      />
    </div>
  );
}

function BrowseSplitPane({ controller }: { controller: BrowsePageController }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  // Default split favors the detail panel: cards take 45%, preview ~55%.
  const [splitPercent, setSplitPercent] = useState(45);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMove = (ev: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.min(80, Math.max(25, pct)));
    };
    const onUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);

  const handleKeyboardResize = useCallback((e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 10 : 2;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      setSplitPercent((p) => Math.max(25, p - step));
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      setSplitPercent((p) => Math.min(80, p + step));
    }
  }, []);

  return (
    <div ref={containerRef} className="mt-6 flex min-h-0 items-start overflow-x-clip">
      <BrowseContentPane controller={controller} splitPercent={splitPercent} />
      {controller.hasDetail && (
        <BrowseResizeHandle
          splitPercent={splitPercent}
          onDragStart={handleDragStart}
          onKeyboardResize={handleKeyboardResize}
        />
      )}
      {controller.hasDetail && <BrowseDetailPane controller={controller} />}
    </div>
  );
}

function BrowseContentPane({
  controller,
  splitPercent,
}: {
  controller: BrowsePageController;
  splitPercent: number;
}) {
  return (
    <div className="@container min-w-0 shrink-0 overflow-x-hidden" style={{ width: controller.hasDetail ? `${splitPercent}%` : "100%" }}>
      <div className={`pl-1 ${controller.hasDetail ? "pr-2" : "pr-1"}`}>
        <BrowseContentGrid
          effectiveViewMode={controller.effectiveViewMode}
          activeCategory={controller.activeCategory}
          displayMode={controller.displayMode}
          sorted={controller.sorted}
          pinnedItems={controller.pinnedItems}
          semanticResultsActive={controller.semanticResultsActive}
          semanticResults={controller.activeSemanticResults}
          semanticLoading={controller.semanticLoading}
          loading={controller.loading}
          error={controller.error}
          refetch={controller.refetch}
          notIndexed={controller.notIndexed}
          stale={controller.stale}
          visibleCount={controller.visibleCount}
          onLoadMore={() => controller.setVisibleCount((visible) => visible + controller.pageSize)}
          pageSize={controller.pageSize}
          selectedSkill={controller.selectedSkill}
          selectedSchedule={controller.selectedSchedule}
          search={controller.search}
          onRunMcp={controller.handleRunMcp}
          onChatResult={controller.handleChatResult}
          onSelectSkill={controller.selectSkill}
          onSelectItem={controller.setSelectedBrowseItemForCurrentView}
          onSelectCapability={controller.setSelectedCapability}
          onSelectScheduledExecution={controller.selectScheduledExecution}
          isPinned={controller.isPinned}
          onTogglePin={(item) => {
            void controller.togglePin(item);
          }}
          onTriggerPrompt={controller.handleTriggerPrompt}
          onItemPrompt={controller.handleItemPrompt}
          onItemDirect={controller.handleItemDirect}
          coverageIndex={controller.coverageIndex}
          activeFolderContext={controller.activeFolderContext}
          onAttachDocumentSource={
            canAttachDocumentSourceToContext(controller.activeFolderContext)
              ? () => controller.setAttachDocumentSourceOpen(true)
              : undefined
          }
        />
        {controller.selectionMode && controller.selectedCount > 0 ? (
          <SelectionActionBar
            count={controller.selectedCount}
            actions={selectionActionsForViewMode(controller.effectiveViewMode)}
            onAction={controller.handleSelectionAction}
            onSelectAllVisible={controller.handleSelectAllVisible}
            onClear={controller.handleClearSelection}
          />
        ) : null}
        <ConfirmDialog
          open={!!controller.deleteConfirm}
          message={controller.deleteConfirm?.message ?? ""}
          onConfirm={() => { controller.deleteConfirm?.resolve(true); controller.setDeleteConfirm(null); }}
          onCancel={() => { controller.deleteConfirm?.resolve(false); controller.setDeleteConfirm(null); }}
        />
      </div>
    </div>
  );
}

function BrowseResizeHandle({
  splitPercent,
  onDragStart,
  onKeyboardResize,
}: {
  splitPercent: number;
  onDragStart: (e: React.MouseEvent) => void;
  onKeyboardResize: (e: React.KeyboardEvent) => void;
}) {
  return (
    <button
      type="button"
      onMouseDown={onDragStart}
      onKeyDown={onKeyboardResize}
      className="w-3 shrink-0 cursor-col-resize group relative flex items-center justify-center rounded border-0 bg-transparent p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
      title="Drag or use arrow keys to resize"
      aria-label={`Resize panels, ${splitPercent}% width`}
    >
      <div className="absolute inset-y-0 -left-1.5 -right-1.5" />
      <div className="w-px h-full bg-[var(--border-color)] group-hover:bg-[var(--accent-primary)]/40 group-active:bg-[var(--accent-primary)]/60 transition-colors duration-200" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        <GripVertical className="size-5 text-[var(--text-muted)]" />
      </div>
    </button>
  );
}

function BrowseDetailPane({ controller }: { controller: BrowsePageController }) {
  const offsetClass =
    !controller.semanticResultsActive && controller.pinnedItems.length > 0 ? "mt-5" : "";
  // Rule 32: demo runbooks ride the owning skill's card metadata; surface them
  // in the skill detail panel by reading the selected card's `demos` field.
  const selectedSkillItem = controller.selectedSkill
    ? controller.sorted.find((item) => item.id === controller.selectedSkill) ?? null
    : null;
  const selectedSkillDemos = parseSkillDemos(selectedSkillItem?.metadata?.demos);

  return (
    <div className={`sticky top-0 self-start flex-1 min-w-0 h-[calc(100dvh-6rem)] md:h-[calc(100dvh-8rem)] overflow-hidden rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] ${offsetClass}`}>
      {(controller.selectedSkill && controller.detailLoading) || (controller.selectedSchedule && controller.scheduledExecutionDetailLoading) ? (
        <div className="p-6 space-y-4">
          <div className="h-8 w-48 rounded-lg bg-[var(--bg-secondary)] motion-safe:animate-pulse" />
          <div className="h-32 rounded-lg bg-[var(--bg-secondary)] motion-safe:animate-pulse" />
        </div>
      ) : controller.selectedSchedule && controller.scheduledExecutionDetail ? (
        <BackgroundRoutineDetailPanel
          routine={controller.scheduledExecutionDetail}
          onClose={controller.closeAnyDetail}
          onItemPrompt={controller.handleItemPrompt}
          onItemDirect={controller.handleItemDirect}
        />
      ) : controller.selectedBrowseItem ? (
        <BrowseItemDetailPanel
          item={controller.selectedBrowseItem}
          onClose={controller.closeAnyDetail}
          category={controller.activeCategory.id}
          categoryLabel={controller.activeCategory.singularLabel}
          categoryIcon={controller.activeCategory.icon}
          onItemPrompt={controller.handleItemPrompt}
          onItemDirect={controller.handleItemDirect}
          activeFolderContext={controller.activeFolderContext}
        />
      ) : controller.skillDetail ? (
        <BrowseDetailPanel
          detail={controller.skillDetail}
          onClose={controller.closeAnyDetail}
          coverageFindings={controller.coverageIndex.bySkill.get(controller.skillDetail.skillId)}
          demos={selectedSkillDemos}
          onTriggerPrompt={controller.handleTriggerPrompt}
          onItemPrompt={controller.handleItemPrompt}
          onItemDirect={controller.handleItemDirect}
          activeFolderContext={controller.activeFolderContext}
        />
      ) : (
        <MissingDetail controller={controller} />
      )}
    </div>
  );
}

function MissingDetail({ controller }: { controller: BrowsePageController }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-center">
      <p className="text-sm text-[var(--text-muted)]">
        {controller.selectedSchedule ? "Background routine not found." : "Skill not found."}
      </p>
      <button
        type="button"
        onClick={controller.closeAnyDetail}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] cursor-pointer transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
      >
        <X className="size-3.5" />
        Close
      </button>
    </div>
  );
}
