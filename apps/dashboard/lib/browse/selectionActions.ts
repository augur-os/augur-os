import type { BrowseItem, ViewMode } from "@/lib/browse/types";
import { mcpCall } from "@/lib/mcp/client";
import { buildSelectionPrompt } from "./selectionPrompt";
import { buildSweepCandidates } from "./sweepCandidates";
import { buildSweepPrompt } from "./sweepPrompt";

export interface SelectionDispatch {
  /** Prompt to hand to the chat. Empty string means "nothing to do" (skip dispatch). */
  initialPrompt: string;
  /** Count of selected items the action could not handle. */
  dropped?: number;
}

export interface SelectionAction {
  id: string;
  label: string;
  icon: string;
  appliesTo: (viewMode: ViewMode) => boolean;
  build: (
    items: BrowseItem[],
    viewMode: ViewMode,
  ) => SelectionDispatch | Promise<SelectionDispatch>;
}

const CONTENT_VIEW_MODES = new Set<ViewMode>(["notes", "documents", "wiki", "pages"]);
const SWEEP_VIEW_MODES = new Set<ViewMode>(["notes", "documents", "pages"]);
const DELETE_VIEW_MODES = new Set<ViewMode>(["notes", "documents", "pages", "wiki", "archive"]);

interface SweepSelectionResponse {
  success?: boolean;
  selection_id?: string;
  error?: string;
  refusal_count?: number;
}

function parseSweepSelectionResponse(value: unknown): SweepSelectionResponse {
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

export const SELECTION_ACTIONS: SelectionAction[] = [
  {
    id: "send-to-chat",
    label: "Send to chat",
    icon: "MessageSquare",
    appliesTo: () => true,
    build: (items, viewMode) => ({
      initialPrompt: buildSelectionPrompt(items, viewMode),
    }),
  },
  {
    id: "summarize",
    label: "Summarize",
    icon: "Sparkles",
    appliesTo: (viewMode) => CONTENT_VIEW_MODES.has(viewMode),
    build: (items, viewMode) => ({
      initialPrompt: buildSelectionPrompt(items, viewMode, {
        intent:
          "Summarize and synthesize these items into one coherent overview. Call out shared themes, contradictions, and anything worth following up.",
      }),
    }),
  },
  {
    id: "sweep",
    label: "Sweep",
    icon: "Archive",
    appliesTo: (viewMode) => SWEEP_VIEW_MODES.has(viewMode),
    build: async (items, viewMode) => {
      const mode = viewMode === "pages" ? "pages" : viewMode === "documents" ? "documents" : "notes";
      const candidates = buildSweepCandidates(mode, items);
      if (candidates.targets.length === 0) {
        return { initialPrompt: "", dropped: items.length };
      }
      const filterSummary = { source: "browse-multi-select", view: viewMode };
      const raw = await mcpCall<unknown>("hygiene-create-selection", {
        source_tab: candidates.source_tab,
        filter_summary: filterSummary,
        targets: candidates.targets,
      });
      const selection = parseSweepSelectionResponse(raw);
      if (!selection.success || !selection.selection_id) {
        throw new Error(selection.error || "Failed to create sweep selection.");
      }
      const dropped = candidates.unsupported.length;
      return {
        initialPrompt: buildSweepPrompt({
          sourceTab: candidates.source_tab,
          selectionId: selection.selection_id,
          targetCount: candidates.targets.length,
          refusalCount: (selection.refusal_count ?? 0) + dropped,
          filterSummary,
        }),
        dropped,
      };
    },
  },
  {
    id: "delete",
    label: "Delete",
    icon: "Trash2",
    appliesTo: (viewMode) => DELETE_VIEW_MODES.has(viewMode),
    // Intercepted by id in the controller (handleSelectionAction) which runs
    // triage -> confirm -> trash/sweep. build() is never invoked for delete.
    build: () => ({ initialPrompt: "" }),
  },
];

export function selectionActionsForViewMode(viewMode: ViewMode): SelectionAction[] {
  return SELECTION_ACTIONS.filter((action) => action.appliesTo(viewMode));
}
