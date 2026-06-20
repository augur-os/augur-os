import type { BrowseItem, ViewMode } from "@/lib/browse/types";
import type { SelectionAction } from "./selectionActions";

export interface SelectionDispatchHandlers {
  onPrompt: (initialPrompt: string) => void;
  onInfo?: (message: string) => void;
  onError?: (message: string) => void;
  onAfterDispatch?: () => void;
}

export async function dispatchSelectionAction(
  action: SelectionAction,
  items: BrowseItem[],
  viewMode: ViewMode,
  handlers: SelectionDispatchHandlers,
): Promise<void> {
  if (items.length === 0) return;
  try {
    const result = await action.build(items, viewMode);
    if (result.dropped && result.dropped > 0) {
      handlers.onInfo?.(
        `${result.dropped} item(s) skipped — not supported by ${action.label}.`,
      );
    }
    if (result.initialPrompt) {
      handlers.onPrompt(result.initialPrompt);
      handlers.onAfterDispatch?.();
    } else {
      handlers.onError?.(
        `Nothing to ${action.label.toLowerCase()} in the current selection.`,
      );
    }
  } catch (error) {
    handlers.onError?.(
      error instanceof Error ? error.message : `${action.label} failed.`,
    );
  }
}
