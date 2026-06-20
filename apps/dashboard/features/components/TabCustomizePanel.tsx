"use client";

import { type CSSProperties, useCallback, useEffect, useReducer, useRef } from "react";
import { GripVertical, Lock, X, Trash2, Eye, EyeOff, Trash } from "lucide-react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { HubConfig, TabItem } from "@/lib/tabs/types";
import {
  persistTabNavOrder,
  type TabNavOrderItem,
} from "@/features/components/layout-config/nav-order";

export interface TabCustomizePanelProps {
  hubId: string;
  hubConfig: HubConfig;
  maxTabs: number;
  onClose: () => void;
  onSave: (updatedConfig: HubConfig) => void;
}

type WorkingTab = {
  id: string;
  label: string;
  originalLabel: string;
  order: number;
  isOverview: boolean;
  skillId: string;
  icon?: string;
  href?: string;
  hidden: boolean;
  deleted: boolean;
};

interface TabCustomizeState {
  workingTabs: WorkingTab[];
  error: string | null;
  saving: boolean;
  editingId: string | null;
  editValue: string;
  confirmDelete: string | null;
}

type TabCustomizeAction =
  | { type: "drag-end"; activeId: string; overId: string }
  | { type: "start-edit"; tab: WorkingTab }
  | { type: "change-edit"; value: string }
  | { type: "confirm-edit" }
  | { type: "cancel-edit" }
  | { type: "toggle-visibility"; id: string }
  | { type: "request-delete"; id: string }
  | { type: "confirm-delete"; id: string }
  | { type: "clear-delete"; id?: string }
  | { type: "undo-delete"; id: string }
  | { type: "reset"; hubConfig: HubConfig }
  | { type: "save-start" }
  | { type: "save-error"; restoredTabs: WorkingTab[]; error: string };

function transformToCSS(
  transform: { x: number; y: number; scaleX: number; scaleY: number } | null,
): string | undefined {
  if (!transform) return undefined;
  return `translate3d(${Math.round(transform.x)}px, ${Math.round(transform.y)}px, 0) scaleX(${transform.scaleX}) scaleY(${transform.scaleY})`;
}

function buildWorkingTabs(hubConfig: HubConfig): WorkingTab[] {
  const allTabs: TabItem[] = [
    ...(hubConfig.tabs || []),
    ...(hubConfig.overflow || []),
  ];

  return allTabs.map((tab, idx) => ({
    id: tab.id || tab.href || `tab-${idx}`,
    label: tab.label,
    originalLabel: tab.label,
    order: idx,
    isOverview: idx === 0,
    skillId: tab.skillId || "",
    icon: typeof tab.icon === "string" ? tab.icon : undefined,
    href: tab.href,
    hidden: false,
    deleted: false,
  }));
}

function reorderWorkingTabs(
  tabs: WorkingTab[],
  activeId: string,
  overId: string,
): WorkingTab[] {
  const sortable = tabs.filter((tab) => !tab.isOverview && !tab.deleted);
  const oldIndex = sortable.findIndex((tab) => tab.id === activeId);
  const newIndex = sortable.findIndex((tab) => tab.id === overId);
  if (oldIndex === -1 || newIndex === -1) return tabs;

  const reordered = arrayMove(sortable, oldIndex, newIndex);
  const overview = tabs.find((tab) => tab.isOverview);
  const deleted = tabs.filter((tab) => tab.deleted);
  const result: WorkingTab[] = [];
  if (overview) result.push({ ...overview, order: 0 });
  reordered.forEach((tab, index) => result.push({ ...tab, order: index + 1 }));
  result.push(...deleted);
  return result;
}

function tabCustomizeReducer(
  state: TabCustomizeState,
  action: TabCustomizeAction,
): TabCustomizeState {
  switch (action.type) {
    case "drag-end":
      return {
        ...state,
        workingTabs: reorderWorkingTabs(state.workingTabs, action.activeId, action.overId),
      };
    case "start-edit":
      return { ...state, editingId: action.tab.id, editValue: action.tab.label };
    case "change-edit":
      return { ...state, editValue: action.value };
    case "confirm-edit": {
      if (!state.editingId) return state;
      const trimmed = state.editValue.trim();
      return {
        ...state,
        workingTabs: trimmed
          ? state.workingTabs.map((tab) =>
              tab.id === state.editingId ? { ...tab, label: trimmed } : tab,
            )
          : state.workingTabs,
        editingId: null,
        editValue: "",
      };
    }
    case "cancel-edit":
      return { ...state, editingId: null, editValue: "" };
    case "toggle-visibility":
      return {
        ...state,
        workingTabs: state.workingTabs.map((tab) =>
          tab.id === action.id ? { ...tab, hidden: !tab.hidden } : tab,
        ),
      };
    case "request-delete":
      return { ...state, confirmDelete: action.id };
    case "confirm-delete":
      return {
        ...state,
        confirmDelete: null,
        workingTabs: state.workingTabs.map((tab) =>
          tab.id === action.id ? { ...tab, deleted: true } : tab,
        ),
      };
    case "clear-delete":
      if (action.id && state.confirmDelete !== action.id) return state;
      return { ...state, confirmDelete: null };
    case "undo-delete":
      return {
        ...state,
        workingTabs: state.workingTabs.map((tab) =>
          tab.id === action.id ? { ...tab, deleted: false } : tab,
        ),
      };
    case "reset":
      return {
        workingTabs: buildWorkingTabs(action.hubConfig),
        error: null,
        saving: false,
        editingId: null,
        editValue: "",
        confirmDelete: null,
      };
    case "save-start":
      return { ...state, saving: true, error: null };
    case "save-error":
      return {
        ...state,
        workingTabs: action.restoredTabs,
        saving: false,
        error: action.error,
      };
    default:
      return state;
  }
}

function SortableTabRow({
  tab,
  editingId,
  editValue,
  onStartEdit,
  onChangeEdit,
  onConfirmEdit,
  onCancelEdit,
  onToggleVisibility,
  onDelete,
}: {
  tab: WorkingTab;
  editingId: string | null;
  editValue: string;
  onStartEdit: (tab: WorkingTab) => void;
  onChangeEdit: (value: string) => void;
  onConfirmEdit: () => void;
  onCancelEdit: () => void;
  onToggleVisibility: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tab.id });
  const inputRef = useRef<HTMLInputElement>(null);
  const isEditing = editingId === tab.id;

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const style: CSSProperties = {
    transform: transformToCSS(transform),
    transition,
    opacity: isDragging ? 0.5 : tab.hidden ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 px-2 py-1.5 rounded-md border border-[var(--border-color)]/60 bg-[var(--bg-primary)]/80 group hover:border-[var(--border-color)]"
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-[var(--text-muted)] hover:text-[var(--text-secondary)] touch-none flex-shrink-0"
        aria-label={`Drag to reorder ${tab.label}`}
      >
        <GripVertical className="size-3.5" />
      </button>
      <div className="flex-1 min-w-0">
        {isEditing ? (
          <input
            ref={inputRef}
            type="text"
            aria-label={`Rename ${tab.label}`}
            value={editValue}
            onChange={(event) => onChangeEdit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") onConfirmEdit();
              if (event.key === "Escape") onCancelEdit();
            }}
            onBlur={onConfirmEdit}
            className="w-full bg-transparent text-xs text-[var(--text-primary)] border border-dashed border-[var(--accent-primary)] rounded px-1 py-0.5 outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => onStartEdit(tab)}
            className={`text-xs cursor-text truncate text-left w-full ${
              tab.hidden
                ? "text-[var(--text-muted)] line-through"
                : "text-[var(--text-primary)] hover:text-[var(--accent-primary)]"
            }`}
            title="Click to rename"
            aria-label={`Rename ${tab.label}`}
          >
            {tab.label}
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={() => onToggleVisibility(tab.id)}
        className="flex-shrink-0 text-[var(--text-muted)] hover:text-[var(--text-secondary)] opacity-40 group-hover:opacity-100 transition-opacity"
        title={tab.hidden ? "Show tab" : "Hide tab"}
        aria-label={tab.hidden ? `Show ${tab.label}` : `Hide ${tab.label}`}
      >
        {tab.hidden ? <EyeOff className="size-3" /> : <Eye className="size-3" />}
      </button>
      <button
        type="button"
        onClick={() => onDelete(tab.id)}
        className="flex-shrink-0 text-[var(--text-muted)] hover:text-red-600 opacity-40 group-hover:opacity-100 transition-opacity"
        title="Delete tab"
        aria-label={`Delete ${tab.label}`}
      >
        <Trash2 className="size-3" />
      </button>
    </div>
  );
}

function useTabCustomizeController({
  hubId,
  hubConfig,
  maxTabs,
  onClose,
  onSave,
}: TabCustomizePanelProps) {
  const [state, dispatch] = useReducer(tabCustomizeReducer, {
    workingTabs: buildWorkingTabs(hubConfig),
    error: null,
    saving: false,
    editingId: null,
    editValue: "",
    confirmDelete: null,
  });
  const snapshotRef = useRef<WorkingTab[]>(state.workingTabs);
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const overviewTab = state.workingTabs.find((tab) => tab.isOverview) ?? null;
  const sortableTabs = state.workingTabs.filter((tab) => !tab.isOverview && !tab.deleted);
  const sortableIds = sortableTabs.map((tab) => tab.id);
  const deletedTabs = state.workingTabs.filter((tab) => tab.deleted && !tab.isOverview);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    dispatch({
      type: "drag-end",
      activeId: String(active.id),
      overId: String(over.id),
    });
  }, []);

  const handleDelete = useCallback((id: string) => {
    if (state.confirmDelete === id) {
      dispatch({ type: "confirm-delete", id });
      return;
    }
    dispatch({ type: "request-delete", id });
    window.setTimeout(() => {
      dispatch({ type: "clear-delete", id });
    }, 3000);
  }, [state.confirmDelete]);

  const handleReset = useCallback(() => {
    dispatch({ type: "reset", hubConfig });
  }, [hubConfig]);

  const handleDone = useCallback(async () => {
    const original = buildWorkingTabs(hubConfig);
    const originalById = new Map(original.map((tab) => [tab.id, tab]));
    const changes: TabNavOrderItem[] = [];

    for (const wt of state.workingTabs) {
      if (wt.isOverview) continue;
      const orig = originalById.get(wt.id);
      if (!orig) continue;

      if (wt.deleted) {
        changes.push({
          pageId: wt.id,
          skillId: wt.skillId,
          order: wt.order,
          delete: true,
        });
        continue;
      }

      const labelChanged = wt.label !== orig.label;
      const orderChanged = wt.order !== orig.order;
      const visChanged = wt.hidden !== orig.hidden;
      if (labelChanged || orderChanged || visChanged) {
        changes.push({
          pageId: wt.id,
          skillId: wt.skillId,
          order: wt.order,
          ...(labelChanged ? { title: wt.label } : {}),
          ...(visChanged ? { visible: !wt.hidden } : {}),
        });
      }
    }

    if (changes.length === 0) {
      onClose();
      return;
    }

    snapshotRef.current = [...state.workingTabs];
    dispatch({ type: "save-start" });

    try {
      const result = await persistTabNavOrder(hubId, changes);
      if (result.error || result.success === false) {
        throw new Error(result.error ?? "Failed to save tab changes");
      }
      onSave(buildUpdatedHubConfig(hubConfig, state.workingTabs, maxTabs));
      onClose();
    } catch (err) {
      dispatch({
        type: "save-error",
        restoredTabs: snapshotRef.current,
        error: err instanceof Error ? err.message : "Failed to save tab changes",
      });
    }
  }, [state.workingTabs, hubConfig, hubId, maxTabs, onSave, onClose]);

  return {
    confirmDelete: state.confirmDelete,
    deletedTabs,
    editValue: state.editValue,
    editingId: state.editingId,
    error: state.error,
    handleDelete,
    handleDone,
    handleDragEnd,
    handleReset,
    overviewTab,
    saving: state.saving,
    sensors,
    sortableIds,
    sortableTabs,
    dispatch,
  };
}

function buildUpdatedHubConfig(
  hubConfig: HubConfig,
  workingTabs: WorkingTab[],
  maxTabs: number,
): HubConfig {
  const liveTabs = workingTabs.filter((tab) => !tab.deleted && !tab.hidden);
  const updatedTabs: TabItem[] = [];
  const updatedOverflow: TabItem[] = [];

  for (const wt of liveTabs) {
    const tabItem: TabItem = {
      id: wt.id,
      label: wt.label,
      order: wt.order,
      skillId: wt.skillId,
      ...(wt.icon ? { icon: wt.icon } : {}),
      ...(wt.href ? { href: wt.href } : {}),
    };
    if (wt.order < maxTabs) {
      updatedTabs.push(tabItem);
    } else {
      updatedOverflow.push(tabItem);
    }
  }

  return {
    ...hubConfig,
    tabs: updatedTabs,
    overflow: updatedOverflow.length > 0 ? updatedOverflow : undefined,
  };
}

type TabCustomizeController = ReturnType<typeof useTabCustomizeController>;

export default function TabCustomizePanel(props: TabCustomizePanelProps) {
  const controller = useTabCustomizeController(props);

  return (
    <div className="w-72 border border-[var(--border-color)] rounded-lg bg-[var(--bg-secondary)] shadow-lg overflow-hidden">
      <TabCustomizeHeader
        onClose={props.onClose}
        onDone={controller.handleDone}
        onReset={controller.handleReset}
        saving={controller.saving}
      />
      {controller.error && (
        <div className="px-3 py-1.5 bg-red-500/10 border-b border-red-500/20 text-red-600 text-xs">
          {controller.error}
        </div>
      )}
      <TabCustomizeList controller={controller} />
      <TabCustomizeFooter />
    </div>
  );
}

function TabCustomizeHeader({
  onClose,
  onDone,
  onReset,
  saving,
}: {
  onClose: () => void;
  onDone: () => void;
  onReset: () => void;
  saving: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border-color)]">
      <span className="text-xs font-semibold text-[var(--text-primary)]">
        Customize Tabs
      </span>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onReset}
          className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors px-1.5 py-0.5 rounded"
          aria-label="Reset tab customizations"
        >
          Reset
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={saving}
          className="text-xs font-medium text-white bg-[var(--accent-primary)] hover:opacity-90 disabled:opacity-50 transition-opacity px-2 py-0.5 rounded"
          aria-label="Save tab customizations"
        >
          {saving ? "Saving…" : "Done"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-0.5"
          aria-label="Close customize panel"
        >
          <X className="size-3" />
        </button>
      </div>
    </div>
  );
}

function TabCustomizeList({ controller }: { controller: TabCustomizeController }) {
  return (
    <div className="p-2 flex flex-col gap-1 max-h-[360px] overflow-y-auto">
      {controller.overviewTab && <PinnedOverviewTab tab={controller.overviewTab} />}
      <DndContext
        sensors={controller.sensors}
        collisionDetection={closestCenter}
        onDragEnd={controller.handleDragEnd}
      >
        <SortableContext
          items={controller.sortableIds}
          strategy={verticalListSortingStrategy}
        >
          {controller.sortableTabs.map((tab) =>
            controller.confirmDelete === tab.id ? (
              <ConfirmDeleteRow
                key={tab.id}
                tab={tab}
                onCancel={() => controller.dispatch({ type: "clear-delete", id: tab.id })}
                onConfirm={controller.handleDelete}
              />
            ) : (
              <SortableTabRow
                key={tab.id}
                tab={tab}
                editingId={controller.editingId}
                editValue={controller.editValue}
                onStartEdit={(nextTab) =>
                  controller.dispatch({ type: "start-edit", tab: nextTab })
                }
                onChangeEdit={(value) =>
                  controller.dispatch({ type: "change-edit", value })
                }
                onConfirmEdit={() => controller.dispatch({ type: "confirm-edit" })}
                onCancelEdit={() => controller.dispatch({ type: "cancel-edit" })}
                onToggleVisibility={(id) =>
                  controller.dispatch({ type: "toggle-visibility", id })
                }
                onDelete={controller.handleDelete}
              />
            ),
          )}
        </SortableContext>
      </DndContext>
      <DeletedTabsList
        tabs={controller.deletedTabs}
        onUndo={(id) => controller.dispatch({ type: "undo-delete", id })}
      />
    </div>
  );
}

function PinnedOverviewTab({ tab }: { tab: WorkingTab }) {
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-md border border-[var(--border-color)]/40 bg-[var(--bg-primary)]/40 opacity-50">
      <Lock className="size-3.5 text-[var(--text-muted)]" />
      <span className="flex-1 text-xs text-[var(--text-muted)]">
        {tab.label}
      </span>
    </div>
  );
}

function ConfirmDeleteRow({
  tab,
  onCancel,
  onConfirm,
}: {
  tab: WorkingTab;
  onCancel: () => void;
  onConfirm: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-md border border-red-500/30 bg-red-500/5">
      <span className="text-xs text-red-600 flex-1">
        Delete &quot;{tab.label}&quot;?
      </span>
      <button
        type="button"
        onClick={() => onConfirm(tab.id)}
        className="text-xs font-medium text-red-600 hover:text-red-300 px-1.5"
        aria-label={`Confirm delete ${tab.label}`}
      >
        Delete tab
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] px-1.5"
        aria-label={`Cancel delete ${tab.label}`}
      >
        Keep tab
      </button>
    </div>
  );
}

function DeletedTabsList({
  tabs,
  onUndo,
}: {
  tabs: WorkingTab[];
  onUndo: (id: string) => void;
}) {
  if (tabs.length === 0) {
    return null;
  }

  return (
    <>
      <div className="flex items-center gap-2 pt-1">
        <div className="flex-1 h-px bg-[var(--border-color)]/40" />
        <span className="text-xs uppercase tracking-wider text-[var(--text-muted)]">
          deleted
        </span>
        <div className="flex-1 h-px bg-[var(--border-color)]/40" />
      </div>
      {tabs.map((tab) => (
        <div key={tab.id} className="flex items-center gap-2 px-2 py-1 rounded-md opacity-40">
          <span className="flex-1 text-xs text-[var(--text-muted)] line-through truncate">
            {tab.label}
          </span>
          <button
            type="button"
            onClick={() => onUndo(tab.id)}
            className="text-xs text-[var(--accent-primary)] hover:underline flex-shrink-0"
            aria-label={`Undo delete ${tab.label}`}
          >
            Undo
          </button>
        </div>
      ))}
    </>
  );
}

function TabCustomizeFooter() {
  return (
    <div className="px-3 py-1.5 border-t border-[var(--border-color)]">
      <p className="text-xs text-[var(--text-muted)] flex items-center gap-1 flex-wrap">
        Drag to reorder · Click to rename · <Eye className="size-3 inline-block" aria-hidden="true" /> toggle visibility · <Trash className="size-3 inline-block" aria-hidden="true" /> delete
      </p>
    </div>
  );
}
