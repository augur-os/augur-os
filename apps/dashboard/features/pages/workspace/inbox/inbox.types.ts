import { Download, Monitor } from "lucide-react";
import { useBrainInbox } from "./hooks";

export type BrainInboxState = ReturnType<typeof useBrainInbox>;
export type FolderPreset = { name: string; path: string };

export const FOLDER_PRESETS = [
  {
    name: "Downloads",
    path: "~/Downloads",
    icon: Download,
    detail: "New PDFs, exports, receipts, and downloaded docs.",
  },
  {
    name: "Desktop",
    path: "~/Desktop",
    icon: Monitor,
    detail: "Screenshots, dropped files, and temporary work piles.",
  },
];
