"use client";

import { useCallback, useEffect, useMemo, useReducer } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useChatStore } from "@/lib/stores/chatStore";
import { getStalenessLevel, getStalenessColors } from "@/lib/timestamps";
import { buildSweepCandidates } from "@/lib/browse/sweepCandidates";
import { buildSweepPrompt } from "@/lib/browse/sweepPrompt";
import { runCliExecPrompt } from "@/lib/browse/cliExecClient";
import { mcpCall } from "@/lib/mcp/client";
import { buildBrowseDeepSearchAction } from "@/lib/browse/deepSearchAction";
import {
  buildProjectInventoryQuestionDraft,
  canAskProjectInventoryQuestion,
  sumProjectProblemCounts,
} from "@/lib/browse/projectQuestion";
import { useBrowseState } from "./useBrowseState";
import { useBrowseSelection } from "@/lib/browse/useBrowseSelection";
import { type SelectionAction } from "@/lib/browse/selectionActions";
import { dispatchSelectionAction } from "@/lib/browse/dispatchSelectionAction";
import {
  completeUrlIngestQueueItem,
  type IngestUrlComposedResult,
  type SaveUrlSourceResult,
  type UrlExtractResult,
} from "./ingestUrlQueue";
import type { NoteQueueItemData } from "@/features/browse/NoteQueueItem";
import { useActionRunner, type ActionDef } from "@/hooks/useActionRunner";
import { type BrowseItem } from "@/lib/browse/types";
import { runDirectItemAction } from "@/lib/browse/directItemActionRunner";
import type { AiItemActionItem, DirectItemAction } from "@/lib/browse/itemActions";
import { indexCategoryForViewMode } from "@/lib/browse/viewModeMapping";
import { useSkillCoverage } from "@/lib/browse/useSkillCoverage";
import type {
  BrowsePageLocalAction,
  BrowsePageLocalState,
  SweepSelectionResponse,
} from "./BrowsePageClient.types";

export function parseSweepSelectionResponse(value: unknown): SweepSelectionResponse {
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as SweepSelectionResponse;
    } catch {
      return { success: false, error: "Selection creation returned invalid JSON." };
    }
  }
  if (typeof value === "object" && value !== null) {
    return value as SweepSelectionResponse;
  }
  return { success: false, error: "Selection creation returned an invalid response." };
}

export function browsePageLocalReducer(
  state: BrowsePageLocalState,
  action: BrowsePageLocalAction,
): BrowsePageLocalState {
  if (action.type !== "set-field") {
    return state;
  }
  const previous = state[action.field];
  const next =
    typeof action.value === "function"
      ? (action.value as (value: typeof previous) => unknown)(previous)
      : action.value;
  return { ...state, [action.field]: next };
}

export function useBrowsePageController() {
  const router = useRouter();
  const { push } = router;
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const browse = useBrowseState({ router, searchParams });
  const { runAction, isExecuting, lastActionId } = useActionRunner();
  const { index: coverageIndex } = useSkillCoverage();
  const [local, dispatch] = useReducer(browsePageLocalReducer, {
    selectedBrowseItemState: { viewMode: browse.effectiveViewMode, item: null },
    reindexing: false,
    sweeping: false,
    noteQueue: [],
    noteModalOpen: false,
    addFolderOpen: false,
    attachDocumentSourceOpen: false,
    toolbarFiltersOpen: false,
    selectedCapability: null,
  });
  const setLocalField = useCallback(
    <K extends keyof BrowsePageLocalState,>(
      field: K,
      value:
        | BrowsePageLocalState[K]
        | ((previous: BrowsePageLocalState[K]) => BrowsePageLocalState[K]),
    ) => {
      dispatch({ type: "set-field", field, value });
    },
    [],
  );
  const selectionMode = useBrowseSelection((s) => s.selectionMode);
  const selectedCount = useBrowseSelection((s) => s.selected.size);
  const toggleSelectionMode = useBrowseSelection((s) => s.toggleSelectionMode);
  const selectedBrowseItem =
    local.selectedBrowseItemState.viewMode === browse.effectiveViewMode
      ? local.selectedBrowseItemState.item
      : null;
  const hasDetail = Boolean(browse.selectedSkill || browse.selectedSchedule || selectedBrowseItem);

  useEffect(() => {
    useBrowseSelection.getState().reset();
  }, [browse.effectiveViewMode]);

  const visibleItems = useMemo(
    () => (browse.semanticResultsActive ? browse.semanticDisplayResults : browse.sorted).slice(0, browse.visibleCount),
    [browse.semanticResultsActive, browse.semanticDisplayResults, browse.sorted, browse.visibleCount],
  );
  const handleSelectionAction = useCallback(
    (action: SelectionAction) =>
      dispatchSelectionAction(
        action,
        useBrowseSelection.getState().selectedItemList(),
        browse.effectiveViewMode,
        {
          onPrompt: browse.handleTriggerPrompt,
          onInfo: (message) => toast.message(message),
          onError: (message) => toast.error(message),
          onAfterDispatch: () => useBrowseSelection.getState().reset(),
        },
      ),
    [browse.effectiveViewMode, browse.handleTriggerPrompt],
  );
  const activeSemanticResults = browse.semanticResultsActive ? browse.semanticDisplayResults : [];
  const setSelectedBrowseItemForCurrentView = useCallback(
    (item: BrowseItem | null) => {
      setLocalField("selectedBrowseItemState", {
        viewMode: browse.effectiveViewMode,
        item,
      });
    },
    [browse.effectiveViewMode, setLocalField],
  );
  const closeAnyDetail = useCallback(() => {
    setSelectedBrowseItemForCurrentView(null);
    browse.closeDetail();
  }, [browse, setSelectedBrowseItemForCurrentView]);
  const openChat = useChatStore((s) => s.openChat);
  const openChatWithPreparedActionDraft = useChatStore((s) => s.openChatWithPreparedActionDraft);
  const handleItemPrompt = useCallback(
    (prompt: string) => {
      const trimmed = prompt.trim();
      if (!trimmed) return;
      openChat({ mode: "ide", initialPrompt: trimmed, draft: true, context: { page: "browse" } });
    },
    [openChat],
  );
  const handleItemDirect = useCallback(
    (action: DirectItemAction, item: AiItemActionItem) => {
      void runDirectItemAction(action, item, {
        callTool: mcpCall,
        confirm: (message) => window.confirm(message),
        invalidate: (queryKey) => queryClient.invalidateQueries({ queryKey: [queryKey] }),
        onLoading: (message) => toast.loading(message),
        onSuccess: (message, id) => toast.success(message, { id }),
        onError: (message, id) => toast.error(message, { id }),
      });
    },
    [queryClient],
  );
  const uploadFiles = useCallback(async (files: File[]) => {
    const formData = new FormData();
    for (const file of files) formData.append("files", file);
    const pending: NoteQueueItemData[] = files.map((file) => ({
      jobId: crypto.randomUUID().slice(0, 8),
      name: file.name,
      status: "pending" as const,
    }));
    setLocalField("noteQueue", (queue) => [...pending, ...queue]);
    try {
      const res = await fetch("/api/ingest/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.success) {
        setLocalField("noteQueue", (queue) =>
          queue.map((item) =>
            pending.some((candidate) => candidate.jobId === item.jobId)
              ? { ...item, status: "completed" as const, destination: "staged" }
              : item,
          ),
        );
      }
    } catch {
      setLocalField("noteQueue", (queue) =>
        queue.map((item) =>
          pending.some((candidate) => candidate.jobId === item.jobId)
            ? { ...item, status: "failed" as const, error: "Upload failed" }
            : item,
        ),
      );
    }
  }, [setLocalField]);
  const handleDrop = useCallback((files: File[]) => uploadFiles(files), [uploadFiles]);
  const handleSubmitUrl = useCallback(async (url: string) => {
    const jobId = crypto.randomUUID().slice(0, 8);
    setLocalField("noteQueue", (queue) => [
      { jobId, name: url, status: "pending" as const, stage: "extracting" },
      ...queue,
    ]);

    try {
      const { mcpCall: callMcp } = await import("@/lib/mcp/client");
      const extracted = (await callMcp("url-extract", { url })) as UrlExtractResult;
      let composed: IngestUrlComposedResult;
      if (!extracted.success || !extracted.body) {
        composed = {
          success: false,
          error: extracted.error || "url-extract returned no body",
        };
      } else {
        const saved = (await callMcp("save-url-source", {
          url: extracted.canonical_url || url,
          title: extracted.title || "",
          body: extracted.body,
          tags: "[]",
        })) as SaveUrlSourceResult;
        composed = saved.success
          ? {
              success: true,
              path: saved.path,
              title: saved.title,
              deduplicated: saved.deduplicated,
            }
          : { success: false, error: saved.error || "save-url-source failed" };
      }
      setLocalField("noteQueue", (queue) =>
        queue.map((item) => completeUrlIngestQueueItem(item, jobId, composed)),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLocalField("noteQueue", (queue) =>
        queue.map((item) =>
          item.jobId === jobId
            ? { ...item, status: "failed" as const, error: message }
            : item,
        ),
      );
    }
  }, [setLocalField]);
  const handleSubmitText = useCallback((text: string) => {
    setLocalField("noteQueue", (queue) => [
      { jobId: crypto.randomUUID().slice(0, 8), name: `${text.slice(0, 40)}…`, status: "pending" as const, stage: "queued" },
      ...queue,
    ]);
  }, [setLocalField]);
  const handleReindex = useCallback(() => {
    setLocalField("reindexing", true);
    const label = `Reindex ${browse.activeCategory.label}`;
    const indexCategory = indexCategoryForViewMode(browse.effectiveViewMode);
    const action: ActionDef = {
      id: `browse-reindex-${indexCategory}`,
      label,
      description: `Rebuild the ${browse.activeCategory.label} browse index.`,
      dispatch: "ide",
      page: "/browse",
      prompt: `/search reindex ${indexCategory}`,
      icon: "SearchCheck",
    };
    void runAction(action)
      .then((ok) => {
        if (ok) browse.refetch();
      })
      .catch((error) => console.error("[browse] reindex dispatch failed:", error))
      .finally(() => setLocalField("reindexing", false));
  }, [browse.activeCategory.label, browse.effectiveViewMode, browse.refetch, runAction, setLocalField]);
  const handleDeepSearch = useCallback(() => {
    const query = browse.search.trim();
    if (!query) return;
    void runAction(buildBrowseDeepSearchAction({
      query,
      activeCategoryId: browse.activeCategory.id,
      activeCategoryLabel: browse.activeCategory.label,
      filters: {
        tag: browse.tagFilter,
        type: browse.typeFilter,
        skillTag: browse.skillTagFilter,
        source: browse.sourceFilter,
        client: browse.masterFilter,
        plugin: browse.pluginFilter,
        scope: browse.scopeFilter ?? null,
        exposure: browse.exposureFilter,
        surface: browse.surfaceFilter,
        owner: browse.ownerFilter,
        management: browse.managementFilter,
        policyScope: browse.policyScopeFilter,
        drift: browse.driftFilter,
        capabilityClient: browse.capabilityClientFilter,
        archived: browse.archivedFilter,
        kind: browse.kindFilter === "all" ? null : browse.kindFilter,
      },
      sortBy: browse.sortBy,
      searched: browse.semanticSearchActive,
      error: browse.semanticSearchActive ? browse.semanticError : null,
      results: browse.semanticResultsActive ? browse.semanticDisplayResults : [],
    }));
  }, [browse, runAction]);
  const handleSweepVisible = useCallback(async () => {
    if (browse.effectiveViewMode !== "notes" && browse.effectiveViewMode !== "documents" && browse.effectiveViewMode !== "pages") {
      return;
    }
    const candidates = buildSweepCandidates(browse.effectiveViewMode, browse.sweepFilteredItems);
    if (candidates.targets.length === 0) {
      toast.error("No sweepable visible items match the current filters/search.");
      return;
    }

    setLocalField("sweeping", true);
    const toastId = toast.loading("Creating sweep selection...");
    try {
      const rawSelection = await mcpCall<unknown>("hygiene-create-selection", {
        source_tab: candidates.source_tab,
        filter_summary: browse.sweepFilterSummary,
        targets: candidates.targets,
      });
      const selection = parseSweepSelectionResponse(rawSelection);
      if (!selection.success || !selection.selection_id) {
        throw new Error(selection.error || "Failed to create sweep selection.");
      }
      const prompt = buildSweepPrompt({
        sourceTab: candidates.source_tab,
        selectionId: selection.selection_id,
        targetCount: candidates.targets.length,
        refusalCount: (selection.refusal_count ?? 0) + candidates.unsupported.length,
        filterSummary: browse.sweepFilterSummary,
      });
      await runCliExecPrompt(prompt);
      toast.success("Sweep prompt dispatched", { id: toastId });
      browse.refetch();
      push("/browse?view=archive");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sweep visible failed";
      toast.error(message, { id: toastId });
    } finally {
      setLocalField("sweeping", false);
    }
  }, [browse.effectiveViewMode, browse.sweepFilteredItems, browse.sweepFilterSummary, browse.refetch, push, setLocalField]);

  const currentFreshness = browse.lastIndexed;
  const projectProblemCount = useMemo(
    () => sumProjectProblemCounts(browse.filtered),
    [browse.filtered],
  );
  const projectQuestionAction = useMemo(() => {
    if (!canAskProjectInventoryQuestion(browse.activeFolderContext)) return undefined;
    return {
      label: "Ask Augur about this project",
      onSelect: () => {
        const draft = buildProjectInventoryQuestionDraft(browse.activeFolderContext, {
          inventoryCount: browse.filtered.length,
          problemCount: projectProblemCount,
        });
        openChatWithPreparedActionDraft(draft, {
          page: "browse",
          folderContext: browse.activeFolderContext,
        });
      },
    };
  }, [browse.activeFolderContext, browse.filtered.length, openChatWithPreparedActionDraft, projectProblemCount]);
  const stalenessLevel = currentFreshness ? getStalenessLevel(currentFreshness) : null;
  const stalenessColors = stalenessLevel ? getStalenessColors(stalenessLevel) : null;
  const summaryBadgeText = browse.loading && browse.sorted.length === 0
    ? `Loading ${browse.activeCategory.label.toLowerCase()}…`
    : `${browse.truncated && browse.totalCount
      ? `${browse.sorted.length.toLocaleString()} of ${browse.totalCount.toLocaleString()}`
      : browse.sorted.length} ${browse.activeCategory.label.toLowerCase()}`;

  return {
    ...browse,
    activeSemanticResults,
    closeAnyDetail,
    coverageIndex,
    currentFreshness,
    handleDeepSearch,
    handleDrop,
    handleItemDirect,
    handleItemPrompt,
    handleReindex,
    handleSelectionAction,
    handleSelectAllVisible: () => useBrowseSelection.getState().selectAllVisible(visibleItems),
    handleClearSelection: () => useBrowseSelection.getState().clear(),
    handleSubmitText,
    handleSubmitUrl,
    handleSweepVisible,
    hasDetail,
    isExecuting,
    lastActionId,
    noteModalOpen: local.noteModalOpen,
    noteQueue: local.noteQueue,
    projectQuestionAction,
    reindexing: local.reindexing,
    retryNoteItem: (item: NoteQueueItemData) => {
      setLocalField("noteQueue", (queue) =>
        queue.filter((entry) => entry.jobId !== item.jobId),
      );
      void handleSubmitUrl(item.name);
    },
    selectedBrowseItem,
    selectedCapability: local.selectedCapability,
    selectedCount,
    selectionMode,
    setAddFolderOpen: (value: boolean) => setLocalField("addFolderOpen", value),
    setAttachDocumentSourceOpen: (value: boolean) => setLocalField("attachDocumentSourceOpen", value),
    setNoteModalOpen: (value: boolean) => setLocalField("noteModalOpen", value),
    setSelectedBrowseItemForCurrentView,
    setSelectedCapability: (item: BrowseItem | null) => setLocalField("selectedCapability", item),
    setToolbarFiltersOpen: (value: boolean) => setLocalField("toolbarFiltersOpen", value),
    stalenessColors,
    stalenessLevel,
    summaryBadgeText,
    sweeping: local.sweeping,
    addFolderOpen: local.addFolderOpen,
    attachDocumentSourceOpen: local.attachDocumentSourceOpen,
    toolbarFiltersOpen: local.toolbarFiltersOpen,
    toggleSelectionMode,
    uploadFiles,
    visibleItems,
  };
}

export type BrowsePageController = ReturnType<typeof useBrowsePageController>;

export function canAttachDocumentSourceToContext(activeFolderContext: BrowsePageController["activeFolderContext"]) {
  return (
    activeFolderContext?.scope === "brain" &&
    Boolean(activeFolderContext.brain_id) &&
    activeFolderContext.brain_id !== "personal"
  );
}
