import { create } from "zustand";
import type { BrowseItem } from "@/lib/browse/types";

export interface BrowseSelectionState {
  selectionMode: boolean;
  /** Selected items keyed by id. Full objects are stored so a later dispatch
   * still has the data even if the item scrolled out of the filtered set. */
  selected: Map<string, BrowseItem>;

  enter: () => void;
  exit: () => void;
  toggleSelectionMode: () => void;
  toggle: (item: BrowseItem) => void;
  selectAllVisible: (items: BrowseItem[]) => void;
  clear: () => void;
  reset: () => void;

  isSelected: (id: string) => boolean;
  selectedItemList: () => BrowseItem[];
}

export const useBrowseSelection = create<BrowseSelectionState>((set, get) => ({
  selectionMode: false,
  selected: new Map(),

  enter: () => set({ selectionMode: true }),
  exit: () => set({ selectionMode: false, selected: new Map() }),
  toggleSelectionMode: () =>
    set((s) =>
      s.selectionMode
        ? { selectionMode: false, selected: new Map() }
        : { selectionMode: true },
    ),

  toggle: (item) =>
    set((s) => {
      const next = new Map(s.selected);
      if (next.has(item.id)) next.delete(item.id);
      else next.set(item.id, item);
      return { selected: next };
    }),

  selectAllVisible: (items) =>
    set((s) => {
      const next = new Map(s.selected);
      for (const item of items) next.set(item.id, item);
      return { selected: next };
    }),

  clear: () => set({ selected: new Map() }),
  reset: () => set({ selectionMode: false, selected: new Map() }),

  isSelected: (id) => get().selected.has(id),
  selectedItemList: () => Array.from(get().selected.values()),
}));
