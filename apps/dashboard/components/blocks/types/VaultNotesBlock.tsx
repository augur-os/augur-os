"use client";

import { useState, useMemo, useCallback } from "react";
import {
  FileText, ChevronDown, ChevronRight, Loader2,
  FolderOpen, Folder, StickyNote, Lightbulb, Newspaper,
  Settings, BookOpen, Hash,
} from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import { Input } from "@/components/ui/Input";
import { formatTimeAgo } from "@/lib/timestamps";
import { stripMdExtension, truncate } from "@/lib/utils/format";

interface VaultNotesConfig {
  title?: string;
  limit?: number;
  directory_filter?: string;
  collapsed?: boolean;
  sort?: "modified_desc" | "directory";
}

interface VaultNote {
  name: string;
  modified?: string;
  preview?: string;
  content?: string;
  type?: string;
  lines?: number;
}

interface VaultGroup {
  directory: string;
  count: number;
  files: VaultNote[];
}

interface VaultStats {
  total_files: number;
  total_dirs: number;
}

const TYPE_ICONS: Record<string, typeof FileText> = {
  note: StickyNote,
  idea: Lightbulb,
  post: Newspaper,
  config: Settings,
  doc: BookOpen,
  interview: Hash,
};

function getTypeIcon(type?: string) {
  if (!type) return FileText;
  return TYPE_ICONS[type] || FileText;
}

export default function VaultNotesBlock(props: BlockProps<VaultNotesConfig>) {
  const { config, dataSource, onExpand } = props;
  const {
    title = "Vault Notes",
    limit = 50,
    directory_filter,
    collapsed: startCollapsed = false,
    sort = "modified_desc",
  } = config;

  const selfFetched = useBlockData<Record<string, unknown>>(dataSource, config, "vault-notes");
  const rawData = (props.data as Record<string, unknown> | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const { groups, stats, notes } = useMemo(() => {
    if (!rawData) return { groups: [] as VaultGroup[], stats: null, notes: [] as VaultNote[] };

    const raw = rawData as Record<string, unknown>;

    if (Array.isArray(raw.groups) && raw.groups.length > 0) {
      let grps = raw.groups as VaultGroup[];

      if (directory_filter) {
        const allowed = new Set(directory_filter.split(",").map((d) => d.trim()));
        grps = grps.filter((g) => allowed.has(g.directory) || allowed.has(g.directory.split("/")[0]));
      }

      return {
        groups: grps,
        stats: (raw.stats as VaultStats) || null,
        notes: (raw.notes as VaultNote[]) || [],
      };
    }

    const flatNotes = Array.isArray(raw) ? (raw as VaultNote[]) : (raw.notes as VaultNote[]) || [];
    return {
      groups: flatNotes.length > 0 ? [{ directory: ".", count: flatNotes.length, files: flatNotes }] : [],
      stats: null,
      notes: flatNotes,
    };
  }, [rawData, directory_filter]);

  const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(
    () => new Set(startCollapsed ? groups.map((g) => g.directory) : []),
  );
  const [searchText, setSearchText] = useState("");

  // Suppress unused variable warning for sort — reserved for future MCP-side ordering
  void sort;

  const filteredGroups = useMemo(() => {
    if (!searchText) return groups;
    const lower = searchText.toLowerCase();
    return groups.flatMap((g) => {
      const files = g.files.filter(
        (f) =>
          f.name.toLowerCase().includes(lower) ||
          (f.preview ?? "").toLowerCase().includes(lower) ||
          (f.type ?? "").toLowerCase().includes(lower),
      );
      return files.length > 0 ? [{ ...g, files }] : [];
    });
  }, [groups, searchText]);

  const totalFiles = stats?.total_files ?? notes.length;

  const toggleNote = useCallback((name: string) => {
    setExpandedNotes((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  const toggleDir = useCallback((dir: string) => {
    setCollapsedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dir)) {
        next.delete(dir);
      } else {
        next.add(dir);
      }
      return next;
    });
  }, []);

  return (
    <BlockShell title={title} icon={FileText} color="purple" onExpand={onExpand} staleError={error}>
      <div className="p-3">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-12 mb-2 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
          ))}

        {!loading && totalFiles === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">No notes</p>
        )}

        {!loading && totalFiles > 3 && (
          <div className="mb-2">
            <Input
              type="text"
              placeholder="Search notes..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]"
            />
          </div>
        )}

        {!loading && filteredGroups.length > 0 && (
          <div className="flex flex-col gap-2">
            {filteredGroups.map((group) => {
              const isDirCollapsed = collapsedDirs.has(group.directory);
              const showDirHeader = group.directory !== "." || filteredGroups.length > 1;

              return (
                <div key={group.directory}>
                  {showDirHeader && (
                    <button type="button"
                      onClick={() => toggleDir(group.directory)}
                      className="flex w-full items-center gap-1.5 p-1 text-left hover:bg-[var(--bg-hover)]/40 rounded transition-colors"
                    >
                      {isDirCollapsed ? (
                        <Folder className="size-3.5 text-[var(--text-muted)]" />
                      ) : (
                        <FolderOpen className="size-3.5 text-[var(--accent-primary)]" />
                      )}
                      <span className="text-xs font-medium text-[var(--text-primary)]">
                        {group.directory === "." ? "Root" : group.directory}
                      </span>
                      <span className="text-[10px] text-[var(--text-muted)] ml-auto">
                        {group.count}
                      </span>
                    </button>
                  )}

                  {!isDirCollapsed && (
                    <div className="flex flex-col gap-1 mt-0.5">
                      {group.files.slice(0, limit).map((note) => {
                        const isExpanded = expandedNotes.has(note.name);
                        const Icon = getTypeIcon(note.type);

                        return (
                          <div key={note.name} className="rounded-lg bg-[var(--bg-hover)]/30 overflow-hidden">
                            <button type="button"
                              onClick={() => toggleNote(note.name)}
                              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left hover:bg-[var(--bg-hover)]/60 transition-colors"
                              aria-expanded={isExpanded}
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                {isExpanded ? (
                                  <ChevronDown className="size-3 text-[var(--text-muted)] flex-shrink-0" />
                                ) : (
                                  <ChevronRight className="size-3 text-[var(--text-muted)] flex-shrink-0" />
                                )}
                                <Icon className="size-3 text-[var(--text-muted)] flex-shrink-0" />
                                <span className="text-xs font-medium text-[var(--text-primary)] truncate">
                                  {stripMdExtension(note.name.split("/").pop() || note.name)}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                {note.lines && (
                                  <span className="text-[10px] text-[var(--text-muted)]">
                                    {note.lines}L
                                  </span>
                                )}
                                {note.modified && (
                                  <span className="text-[10px] text-[var(--text-muted)]">
                                    {formatTimeAgo(note.modified)}
                                  </span>
                                )}
                              </div>
                            </button>

                            {!isExpanded && note.preview && (
                              <p className="px-3 pb-2 text-[10px] text-[var(--text-muted)] leading-relaxed">
                                {truncate(note.preview)}
                              </p>
                            )}

                            {isExpanded && (
                              <div className="border-t border-[var(--border-color)]/30 px-3 py-2">
                                {note.content ? (
                                  <div className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                                    {note.content}
                                  </div>
                                ) : note.preview ? (
                                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                                    {note.preview}
                                  </p>
                                ) : (
                                  <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                                    <Loader2 className="size-3 animate-spin" />
                                    Loading…
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}

            {searchText && filteredGroups.length === 0 && (
              <p className="py-3 text-center text-xs text-[var(--text-muted)]">No notes match your search</p>
            )}
          </div>
        )}
      </div>
    </BlockShell>
  );
}
