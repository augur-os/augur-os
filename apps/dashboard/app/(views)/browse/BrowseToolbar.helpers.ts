import {
  type ViewMode,
  type BrowsePageKindFilter,
  type NoteTypeFilter,
} from "@/lib/browse/types";

export const EMPTY_ARRAY: never[] = [];

/* ------------------------------------------------------------------ */
/*  Tag pill helpers                                                  */
/* ------------------------------------------------------------------ */

export function tagSectionLabel(category: ViewMode): string {
  switch (category) {
    case "integrations": return "Status";
    case "skills": return "Quality";
    case "commands": return "Quality";
    case "notes":
    case "archive":
    case "system-metadata": return "Format";
    case "pages": return "Kind";
    case "wiki": return "Tag";
    default: return "Filter";
  }
}

/* ------------------------------------------------------------------ */
/*  Styled filter select                                               */
/* ------------------------------------------------------------------ */

export const selectClass = "px-3 py-2.5 min-h-[44px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] text-xs text-[var(--text-secondary)] cursor-pointer hover:bg-[var(--bg-hover)] transition-colors duration-200 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50";
export const selectActiveClass = "px-3 py-2.5 min-h-[44px] rounded-lg border border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-xs text-[var(--accent-primary)] cursor-pointer hover:bg-[var(--accent-primary)]/15 transition-colors duration-200 shrink-0 ring-1 ring-[var(--accent-primary)]/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50";

export function optionLabel(options: { id: string; label: string }[], value: string | null) {
  if (!value) return null;
  return options.find((option) => option.id === value)?.label ?? value;
}

export const PAGE_KIND_OPTIONS: Array<{ id: BrowsePageKindFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "live", label: "Live" },
  { id: "saved", label: "Saved" },
  { id: "generated", label: "Generated" },
];
const NOTE_TYPE_LABELS: Record<NoteTypeFilter, string> = {
  url: "URL",
  file: "File",
  thought: "Thought",
  "voice-memo": "Voice Memo",
  meeting: "Meeting",
  image: "Image",
  prompt: "Prompt",
};

export function noteTypeFilterLabel(value: string | null): string | null {
  if (!value) return null;
  const labels = value
    .split(",")
    .flatMap((type) => {
      const trimmed = type.trim();
      const label = NOTE_TYPE_LABELS[trimmed as NoteTypeFilter] ?? trimmed;
      return label ? [label] : [];
    });
  return labels.join(", ");
}

export const CLIENT_DISPLAY_NAMES: Record<string, string> = {
  "claude": "Claude",
  "claude-code": "Claude",
  "claude-plugin": "Claude",
  "codex": "Codex",
  "gemini": "Gemini",
  "cursor": "Cursor",
  "copilot": "Copilot",
  "opencode": "OpenCode",
  "augur": "Augur",
};
