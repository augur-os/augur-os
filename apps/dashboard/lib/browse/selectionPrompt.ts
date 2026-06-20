import type { BrowseItem, ViewMode } from "@/lib/browse/types";

const VIEW_MODE_LABELS: Partial<Record<ViewMode, string>> = {
  notes: "Notes",
  documents: "Documents",
  wiki: "Wiki",
  pages: "Pages",
};

function itemReference(item: BrowseItem): string {
  const ref =
    item.metadata?.source_path ||
    item.metadata?.filePath ||
    item.path ||
    item.id;
  const title = (item.title || item.id).replace(/\s+/g, " ").trim();
  return `"${title}" — ${ref}`;
}

export interface SelectionPromptOptions {
  /** Trailing instruction line. Omitted → a placeholder invites the user to type. */
  intent?: string;
}

export function buildSelectionPrompt(
  items: BrowseItem[],
  viewMode: ViewMode,
  options: SelectionPromptOptions = {},
): string {
  const label = VIEW_MODE_LABELS[viewMode] ?? viewMode;
  const noun = items.length === 1 ? "item" : "items";
  const header = `Selected ${items.length} ${noun} from Browse · ${label}:`;
  const lines = items.map((item, i) => `${i + 1}. ${itemReference(item)}`);
  const intent = options.intent ?? "<describe what you'd like to do with these>";
  return [header, ...lines, "", intent].join("\n");
}
