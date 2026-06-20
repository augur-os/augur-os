"use client";

import { FileText, BookOpen, Puzzle, FolderOpen, ChevronDown, ChevronRight } from "lucide-react";
import { FileContextMenu } from "./FileContextMenu";
import type {
  BrowseIndexItem,
  BrowseSearchResults,
  FileResult,
  KnowledgeResult,
} from "./SearchButton.types";

export const BROWSE_SECTION_CONFIG: {
  key: keyof BrowseSearchResults;
  label: string;
  icon: React.ReactNode;
}[] = [
  { key: "skills", label: "Skills", icon: <Puzzle className="size-3" /> },
  { key: "vault", label: "Notes", icon: <BookOpen className="size-3" /> },
  { key: "wiki", label: "Wiki", icon: <FileText className="size-3" /> },
  { key: "documents", label: "Documents", icon: <FolderOpen className="size-3" /> },
];

export function SectionHeader({
  icon,
  label,
  count,
}: {
  icon: React.ReactNode;
  label: string;
  count: number;
}) {
  return (
    <div className="mx-2 mb-1 mt-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
      {icon}
      <span>{label}</span>
      <span className="rounded-full bg-[var(--bg-primary)]/85 px-1.5 py-px text-[9px] font-semibold">
        {count}
      </span>
    </div>
  );
}

export function OverflowSection({
  expanded,
  count,
  onToggle,
  children,
}: {
  expanded: boolean;
  count: number;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-[var(--border-color)]/60 pt-2 mt-1">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="mx-2 mb-1 flex w-[calc(100%-1rem)] items-center gap-1.5 rounded-full border border-[var(--border-color)]/65 bg-[var(--bg-primary)]/55 px-3 py-2 text-[11px] font-medium text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-card)]/80 hover:text-[var(--text-primary)]"
      >
        {expanded ? (
          <ChevronDown className="size-3 shrink-0" />
        ) : (
          <ChevronRight className="size-3 shrink-0" />
        )}
        <span>More results</span>
        <span className="ml-auto rounded-full bg-[var(--accent-primary)]/10 px-1.5 py-px text-[10px] font-semibold text-[var(--text-muted)]">
          {count}
        </span>
      </button>
      {expanded ? children : null}
    </div>
  );
}

export function KnowledgeResultRow({
  category,
  item,
  onAttach,
}: {
  category: "knowledge";
  item: KnowledgeResult;
  onAttach: (filePath: string) => void;
}) {
  const fileName = item.filePath.split("/").pop() || item.title;

  return (
    <FileContextMenu
      filePath={item.filePath}
      fileName={fileName}
      onAttach={onAttach}
    >
      <div className="mx-2 mb-1 rounded-xl border border-transparent px-3 py-2 transition-colors hover:border-[var(--border-color)]/60 hover:bg-[var(--bg-hover)]/75">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[var(--text-primary)] truncate flex-1">
            {item.title}
          </span>
          <span className="shrink-0 rounded-full bg-violet-500/15 px-1.5 py-px text-[10px] font-medium text-violet-400">
            {category === "knowledge" ? item.source : category}
          </span>
        </div>
        <div className="text-xs text-[var(--text-muted)] truncate mt-0.5">
          {item.snippet}
        </div>
      </div>
    </FileContextMenu>
  );
}

export function FileResultRow({
  category,
  file,
  onAttach,
}: {
  category: "files" | "logs";
  file: FileResult;
  onAttach: (filePath: string) => void;
}) {
  return (
    <FileContextMenu
      filePath={file.absolutePath}
      fileName={file.name}
      onAttach={onAttach}
    >
      <div className="mx-2 mb-1 rounded-xl border border-transparent px-3 py-2 transition-colors group hover:border-[var(--border-color)]/60 hover:bg-[var(--bg-hover)]/75">
        <div className="flex items-center gap-1.5">
          <div className="text-xs font-mono text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] truncate flex-1">
            {file.name}
          </div>
          <span className="shrink-0 rounded-full bg-[var(--bg-primary)]/85 px-1.5 py-px text-[10px] font-medium text-[var(--text-muted)]">
            {category}
          </span>
        </div>
        <div className="text-xs text-[var(--text-muted)] truncate">
          {file.relativePath}
        </div>
      </div>
    </FileContextMenu>
  );
}

export function BrowseResultRow({
  category,
  item,
  onAttach,
}: {
  category: keyof BrowseSearchResults;
  item: BrowseIndexItem;
  onAttach: (filePath: string) => void;
}) {
  const filePath = item.source_path || "";
  const fileName = filePath.split("/").pop() || item.title;

  return (
    <FileContextMenu
      filePath={filePath}
      fileName={fileName}
      onAttach={onAttach}
    >
      <div className="mx-2 mb-1 rounded-xl border border-transparent px-3 py-2 transition-colors group hover:border-[var(--border-color)]/60 hover:bg-[var(--bg-hover)]/75">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] truncate flex-1">
            {item.title}
          </span>
          <span className="shrink-0 rounded-full bg-[var(--accent-primary)]/10 px-1.5 py-px text-[10px] font-medium text-[var(--accent-primary)]">
            {BROWSE_SECTION_CONFIG.find((section) => section.key === category)?.label ?? category}
          </span>
        </div>
        {item.description && (
          <div className="text-xs text-[var(--text-muted)] truncate mt-0.5">
            {item.description}
          </div>
        )}
      </div>
    </FileContextMenu>
  );
}
