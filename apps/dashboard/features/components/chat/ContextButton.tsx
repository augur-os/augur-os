"use client";

import { Suspense, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { BookOpen, File, Loader2, Pin } from "lucide-react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { ChatSidePopover } from "./ChatSidePopover";
import { TabPanel, type TabDefinition } from "./TabPanel";
import { PageScopedList } from "./PageScopedList";
import { FileContextMenu } from "./FileContextMenu";
import { TOOL_BUTTON_ACTIVE_CLASS, TOOL_BUTTON_IDLE_CLASS, formatFileSize, formatAge, matchesFileQuery } from "@/components/chat/utils";

export interface ContextButtonProps {
  isOperationMode: boolean;
  pathname: string;
  isOpen: boolean;
  onToggle: () => void;
  onAttachFile: (filePath: string) => void;
  chatContainerRef: React.RefObject<HTMLDivElement | null>;
  portalRef: React.RefObject<HTMLDivElement | null>;
  popoverRef: React.RefObject<HTMLDivElement | null>;
}

type ContextFileListItemExtraProps = {
  onAttach: (path: string) => void;
};

interface ContextFileItem {
  name: string;
  relativePath: string;
  absolutePath: string;
  size: number;
  modified: number;
  extension: string;
  isDirectory: boolean;
}

interface ContextApiResponse {
  files?: ContextFileItem[];
  hubFiles?: ContextFileItem[];
  hubName?: string;
  reference?: ContextFileItem[];
}

/** RAG browse-index entry shape */
interface BrowseIndexItem {
  id: string;
  title: string;
  description: string;
  hub: string;
  source_path?: string;
  metadata?: Record<string, string>;
}

interface BrowseIndexResponse {
  items?: BrowseIndexItem[];
  count?: number;
  status?: string;
}

type SearchParamsReader = Pick<URLSearchParams, "get">;

function readSearchParam(searchParams: SearchParamsReader, name: string): string | null {
  return searchParams.get(name);
}

/** Tabs for standard skill pages (filesystem-based) */
const SKILL_TABS: TabDefinition[] = [
  { id: "vault", label: "Vault" },
  { id: "documents", label: "Documents" },
  { id: "assets", label: "Assets" },
  { id: "docs", label: "Docs" },
  { id: "runtime", label: "Runtime", devOnly: true },
];

/** Tabs for /browse page — knowledge/reference only (RAG-based) */
const BROWSE_TABS: TabDefinition[] = [
  { id: "vault", label: "Notes" },
  { id: "wiki", label: "Wiki" },
  { id: "documents", label: "Documents" },
  { id: "skills", label: "Skills" },
];

/** Maps browse tab IDs to browse-index RAG categories */
const BROWSE_TAB_CATEGORY: Record<string, string> = {
  vault: "vault",
  wiki: "wiki",
  documents: "documents",
  skills: "skills",
};

function FileItem({
  file,
  onAttach,
}: {
  file: ContextFileItem;
  onAttach: (filePath: string) => void;
}) {
  return (
    <FileContextMenu
      filePath={file.absolutePath}
      fileName={file.name}
      onAttach={onAttach}
    >
      <div className="w-full text-left px-3 py-2 hover:bg-[var(--bg-secondary)] transition-colors group border-b border-[var(--border-color)] last:border-b-0">
        <div className="flex items-center gap-2">
          <File className="size-3 text-[var(--text-muted)] shrink-0" />
          <span className="text-xs font-mono text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] truncate">
            {file.name}
          </span>
          <span className="text-[9px] text-[var(--text-muted)] ml-auto shrink-0">
            {formatAge(file.modified)}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-0.5 pl-5">
          <span className="text-[9px] text-[var(--text-muted)] truncate">
            {file.relativePath}
          </span>
          <span className="text-[9px] text-[var(--text-muted)] shrink-0">
            {formatFileSize(file.size)}
          </span>
        </div>
      </div>
    </FileContextMenu>
  );
}

function ReferenceSection({
  files,
  onAttach,
}: {
  files: ContextFileItem[];
  onAttach: (filePath: string) => void;
}) {
  if (files.length === 0) return null;

  return (
    <div className="border-t border-[var(--border-color)]">
      <div className="flex items-center gap-1.5 px-3 py-1.5">
        <Pin className="size-2.5 text-[var(--text-muted)]" />
        <span className="text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
          Reference
        </span>
      </div>
      {files.map((file) => (
        <FileItem key={file.absolutePath} file={file} onAttach={onAttach} />
      ))}
    </div>
  );
}

function ContextFileListItem({
  item,
  onAttach,
}: {
  item: ContextFileItem;
  index: number;
  onAttach: ContextFileListItemExtraProps["onAttach"];
}) {
  return <FileItem file={item} onAttach={onAttach} />;
}

export function ContextButton(props: ContextButtonProps) {
  return (
    <Suspense fallback={null}>
      <ContextButtonInner {...props} />
    </Suspense>
  );
}

function ContextButtonInner({
  isOperationMode,
  pathname,
  isOpen,
  onToggle,
  onAttachFile,
  chatContainerRef,
  portalRef,
  popoverRef,
}: ContextButtonProps) {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState("vault");
  const [search, setSearch] = useState("");

  const mode = isOperationMode ? "operation" : "development";

  // On /browse, use browse-index (RAG) instead of get-context-files (filesystem).
  // get-context-files only works for hub pages where pathname resolves to a skill.
  const isBrowse = pathname === "/browse";
  const browseSkill = isBrowse ? readSearchParam(searchParams, "skill") : null;
  const activeTabs = isBrowse ? BROWSE_TABS : SKILL_TABS;
  const resolvedActiveTab = activeTabs.some((tab) => tab.id === activeTab)
    ? activeTab
    : (activeTabs[0]?.id ?? "vault");

  // --- Standard hub page path: use get-context-files ---
  const { data, loading: standardLoading } = useMcpQuery<ContextApiResponse>(
    ["context-files", pathname, resolvedActiveTab, mode],
    "get-context-files",
    "live",
    {
      args: { page: pathname, tab: resolvedActiveTab, mode, expand: "hub" },
      enabled: !isBrowse,
    },
  );

  // --- Browse page: use browse-index (RAG) for all tabs ---
  const browseCategory = BROWSE_TAB_CATEGORY[resolvedActiveTab] ?? "";
  const { data: browseData, loading: browseLoading } = useMcpQuery<BrowseIndexResponse>(
    ["browse-context", browseCategory, browseSkill ?? ""],
    "browse-index",
    "config",
    {
      args: {
        category: browseCategory,
        ...(browseSkill ? { search: browseSkill } : {}),
        limit: 30,
      },
      enabled: isBrowse && !!browseCategory,
    },
  );

  // Convert browse-index items to ContextFileItem shape for the existing UI
  const browseFiles = useMemo<ContextFileItem[]>(() => {
    if (!browseData?.items) return [];
    return browseData.items.map((item) => ({
      name: item.title || item.id,
      relativePath: item.source_path?.replace(/^.*?\/Projects\/Augur\//, "") ?? item.description,
      absolutePath: item.source_path ?? "",
      size: 0,
      modified: item.metadata?.modified ? new Date(item.metadata.modified).getTime() : 0,
      extension: item.source_path?.split(".").pop() ? `.${item.source_path.split(".").pop()}` : "",
      isDirectory: false,
    }));
  }, [browseData]);

  const loading = isBrowse ? browseLoading : standardLoading;
  const files = useMemo(
    () => (isBrowse ? browseFiles : (data?.files ?? [])),
    [isBrowse, browseFiles, data],
  );
  const hubFiles = useMemo(
    () => (isBrowse ? [] : (data?.hubFiles ?? [])),
    [isBrowse, data],
  );
  const hubName = data?.hubName ?? "Hub";
  const reference = isBrowse ? [] : (data?.reference ?? []);

  const filtered = useMemo(() => {
    if (!search) return { files, hubFiles };
    return {
      files: files.filter((f) => matchesFileQuery(f, search)),
      hubFiles: hubFiles.filter((f) => matchesFileQuery(f, search)),
    };
  }, [files, hubFiles, search]);

  const handleTabChange = useCallback((tabId: string) => {
    setActiveTab(tabId);
    setSearch("");
  }, []);

  const buttonClass = isOpen
    ? TOOL_BUTTON_ACTIVE_CLASS
    : TOOL_BUTTON_IDLE_CLASS;

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={onToggle}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${buttonClass}`}
        title="Browse context files for this page"
      >
        <BookOpen className="size-3" />
        <span>Context</span>
      </button>

      {isOpen && (
        <ChatSidePopover chatRef={chatContainerRef} portalRef={portalRef}>
          <div className="w-80 max-h-96 bg-[var(--bg-popover)] backdrop-blur-xl border border-[var(--border-color)]/60 rounded-xl shadow-2xl overflow-hidden flex flex-col">
            <TabPanel
              tabs={isBrowse ? BROWSE_TABS : SKILL_TABS}
              activeTab={resolvedActiveTab}
              onTabChange={handleTabChange}
              isOperationMode={isOperationMode}
              searchPlaceholder={`Search ${activeTab}...`}
              searchValue={search}
              onSearchChange={setSearch}
            >
              <div className="overflow-y-auto max-h-64">
                {loading ? (
                  <div className="flex items-center justify-center gap-2 px-3 py-6 text-xs text-[var(--text-muted)]">
                    <Loader2 className="size-3 animate-spin" />
                    <span>Loading files…</span>
                  </div>
                ) : (
                  <>
                    <PageScopedList<ContextFileItem, ContextFileListItemExtraProps>
                      items={filtered.files}
                      hubItems={filtered.hubFiles}
                      hubName={hubName}
                      ItemComponent={ContextFileListItem}
                      itemProps={{ onAttach: onAttachFile }}
                      emptyMessage={
                        search
                          ? `No files matching "${search}"`
                          : "No files available"
                      }
                      hubEmptyMessage="No additional files in this hub"
                    />
                    <ReferenceSection
                      files={reference}
                      onAttach={onAttachFile}
                    />
                  </>
                )}
              </div>
            </TabPanel>
          </div>
        </ChatSidePopover>
      )}
    </div>
  );
}
