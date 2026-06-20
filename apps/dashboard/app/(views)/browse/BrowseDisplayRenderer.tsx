"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { BrowseCardShell } from "@/components/shared/BrowseCardShell";
import { BrowseListRowCard } from "@/components/shared/BrowseListRowCard";
import { buildBrowseCardModel } from "@/lib/browse/cardModel";
import { executeBrowseAction } from "@/lib/browse/executeAction";
import type { BrowseChatResult } from "@/lib/browse/executeAction";
import type { BrowseDisplayMode } from "@/lib/browse/displayMode";
import type { AiItemActionItem, DirectItemAction } from "@/lib/browse/itemActions";
import type { BrowseCardAction, BrowseCategory, BrowseItem, ViewMode } from "@/lib/browse/types";
import { useBrowseSelection } from "@/lib/browse/useBrowseSelection";
import { browseItemKey } from "@/lib/browse/overlay";

interface BrowseDisplayRendererProps {
  activeCategory: BrowseCategory;
  viewMode: ViewMode;
  displayMode: BrowseDisplayMode;
  items: BrowseItem[];
  selectedSkill: string | null;
  selectedSchedule: string | null;
  onRunMcp: (target: string) => void;
  onChatResult: (result: BrowseChatResult) => void;
  onSelectSkill: (skillId: string) => void;
  onSelectItem: (item: BrowseItem) => void;
  onSelectCapability: (item: BrowseItem) => void;
  onSelectScheduledExecution: (executionId: string) => void;
  isPinned: (item: BrowseItem) => boolean;
  onTogglePin: (item: BrowseItem) => void;
  onTriggerPrompt: (resolvedPrompt: string) => void;
  /** Hands a resolved, item-aware AI-action prompt to the chat as an editable draft. */
  onItemPrompt?: (prompt: string) => void;
  /** Runs a generated direct MCP action against an item. */
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
}

function selectedForItem(item: BrowseItem, viewMode: ViewMode, selectedSkill: string | null, selectedSchedule: string | null) {
  if (viewMode === "skills") return selectedSkill === item.id;
  if (viewMode === "background-routines") return selectedSchedule === item.id;
  return false;
}

function actionById(actions: BrowseCardAction[], actionId: string): BrowseCardAction | undefined {
  return actions.find((action) => action.id === actionId);
}

export function BrowseDisplayRenderer({
  activeCategory,
  viewMode,
  displayMode,
  items,
  selectedSkill,
  selectedSchedule,
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
}: BrowseDisplayRendererProps) {
  const router = useRouter();
  const models = useMemo(
    () => items.map((item) => buildBrowseCardModel(item, { viewMode })),
    [items, viewMode],
  );
  const selectionMode = useBrowseSelection((s) => s.selectionMode);
  const selectedMap = useBrowseSelection((s) => s.selected);
  const toggleSelect = useBrowseSelection((s) => s.toggle);
  // Container-query columns (parent grid wrapper is an `@container`): the card
  // grid responds to its OWN width, not the viewport — so it collapses to a
  // single column when the detail panel is open and the column is narrow,
  // instead of cramming 2–3 squished cards into the shrunken pane.
  const containerClass = displayMode === "list"
    ? "space-y-2"
    : "grid grid-cols-1 gap-4 @2xl:grid-cols-2 @5xl:grid-cols-3";

  const executeAction = (action: BrowseCardAction | BrowseItem["primaryAction"]) => {
    void executeBrowseAction(action, {
      router,
      onRunMcp,
      onChatResult,
      onCliHelp: async (target) => {
        onTriggerPrompt(target);
      },
    });
  };

  return (
    <div
      data-testid={displayMode === "list" ? "browse-display-list" : "browse-display-grid"}
      data-category={activeCategory.id}
      className={containerClass}
    >
      {models.map((model) => {
        const item = model.rawItem;
        const handleSelect = () => {
          if (viewMode === "skills") {
            onSelectSkill(item.id);
            return;
          }
          if (viewMode === "background-routines") {
            onSelectScheduledExecution(item.id);
            return;
          }
          onSelectItem(item);
        };

        const sharedProps = {
          model,
          selected: selectedForItem(item, viewMode, selectedSkill, selectedSchedule),
          pinned: isPinned(item),
          onPin: () => onTogglePin(item),
          onSelect: handleSelect,
          onPrimaryAction: () => executeAction(model.primaryAction),
          onAction: (actionId: string) => {
            const action = actionById(model.overflowActions, actionId);
            if (action) executeAction(action);
          },
          onPolicy: item.metadata?.capabilityId ? () => onSelectCapability(item) : undefined,
          selectionMode,
          isMultiSelected: selectedMap.has(item.id),
          onToggleMultiSelect: () => toggleSelect(item),
          category: activeCategory.id,
          onItemPrompt,
          onItemDirect,
        };

        // Key by the same identity useBrowseState dedups on. In overlay view
        // modes two distinct cards legitimately share `item.id` (e.g. a note in
        // both the shared and private vault scope), so a bare-id key collides —
        // React's "two children with the same key" warning, which silently
        // drops or duplicates cards.
        const reactKey = browseItemKey(item, viewMode);
        return displayMode === "list" ? (
          <BrowseListRowCard key={reactKey} {...sharedProps} />
        ) : (
          <BrowseCardShell key={reactKey} {...sharedProps} />
        );
      })}
    </div>
  );
}
