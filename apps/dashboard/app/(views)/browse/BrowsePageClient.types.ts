import { type BrowseItem } from "@/lib/browse/types";
import type { NoteQueueItemData } from "@/features/browse/NoteQueueItem";

export type SweepSelectionResponse = {
  success?: boolean;
  selection_id?: string;
  error?: string;
  refusal_count?: number;
};

export type SelectedBrowseItemState = {
  viewMode: string;
  item: BrowseItem | null;
};

export interface BrowsePageLocalState {
  selectedBrowseItemState: SelectedBrowseItemState;
  reindexing: boolean;
  sweeping: boolean;
  noteQueue: NoteQueueItemData[];
  noteModalOpen: boolean;
  addFolderOpen: boolean;
  attachDocumentSourceOpen: boolean;
  toolbarFiltersOpen: boolean;
  selectedCapability: BrowseItem | null;
}

export type BrowsePageLocalAction = {
  type: "set-field";
  field: keyof BrowsePageLocalState;
  value: unknown;
};
