"use client";

import { Suspense, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { Layers, Wand2, Zap, MessageSquare } from "lucide-react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { ChatSidePopover } from "./ChatSidePopover";
import { TabPanel } from "./TabPanel";
import type { TabDefinition } from "./TabPanel";
import { TOOL_BUTTON_ACTIVE_CLASS, TOOL_BUTTON_IDLE_CLASS } from "@/components/chat/utils";
import type { McpTool, SlashCommand } from "./types";

export interface ActionsButtonProps {
  isOperationMode: boolean;
  pathname: string;
  isOpen: boolean;
  onToggle: () => void;
  // MCP tools (passed from parent FloatingChat which already fetches them)
  mcpTools: McpTool[];
  mcpToolsLoading: boolean;
  onInsertTool: (toolName: string) => void;
  // Slash commands (passed from parent)
  commands: SlashCommand[];
  onRunCommand: (command: SlashCommand) => void;
  // Magic / Analyze Page
  onMagicClick: () => void;
  magicLoading: boolean;
  pendingInsightCount: number;
  // Popover refs
  chatContainerRef: React.RefObject<HTMLDivElement | null>;
  portalRef: React.RefObject<HTMLDivElement | null>;
  popoverRef: React.RefObject<HTMLDivElement | null>;
}

/** Tabs for standard skill pages */
const SKILL_TABS: TabDefinition[] = [
  { id: "actions", label: "Actions" },
  { id: "mcp-tools", label: "MCP Tools" },
  { id: "commands", label: "Commands", devOnly: true },
];

/** Tabs for /browse page — all executable/operational items */
const BROWSE_TABS: TabDefinition[] = [
  { id: "actions", label: "Actions" },
  { id: "prompts", label: "Prompts" },
  { id: "mcp-tools", label: "Tools" },
  { id: "commands", label: "Cmds", devOnly: true },
];

/** RAG browse-index item shape */
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
}

type SearchParamsReader = Pick<URLSearchParams, "get">;

function readSearchParam(searchParams: SearchParamsReader, name: string): string | null {
  return searchParams.get(name);
}

export function ActionsButton(props: ActionsButtonProps) {
  return (
    <Suspense fallback={null}>
      <ActionsButtonInner {...props} />
    </Suspense>
  );
}

function ActionsButtonInner({
  isOperationMode,
  pathname,
  isOpen,
  onToggle,
  mcpTools,
  mcpToolsLoading,
  onInsertTool,
  commands,
  onRunCommand,
  onMagicClick,
  magicLoading,
  pendingInsightCount,
  chatContainerRef,
  portalRef,
  popoverRef,
}: ActionsButtonProps) {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState("actions");
  const [search, setSearch] = useState("");

  // On /browse, resolve the selected skill from URL params so we can show
  // that skill's actions instead of matching tools against "browse".
  const isBrowse = pathname === "/browse";
  const browseSkill = isBrowse ? readSearchParam(searchParams, "skill") : null;

  const activeTabs = isBrowse ? BROWSE_TABS : SKILL_TABS;
  const resolvedActiveTab = activeTabs.some((tab) => tab.id === activeTab)
    ? activeTab
    : (activeTabs[0]?.id ?? "actions");

  const lowerSearch = search.toLowerCase();

  const filteredTools = useMemo(
    () =>
      lowerSearch
        ? mcpTools.filter(
            (t) =>
              t.name.toLowerCase().includes(lowerSearch) ||
              (t.description || "").toLowerCase().includes(lowerSearch),
          )
        : mcpTools,
    [mcpTools, lowerSearch],
  );

  const filteredCommands = useMemo(() => {
    const filtered = lowerSearch
      ? commands.filter(
          (c) =>
            c.name.toLowerCase().includes(lowerSearch) ||
            c.description.toLowerCase().includes(lowerSearch) ||
            (c.category || "").toLowerCase().includes(lowerSearch),
        )
      : commands;

    return filtered.reduce(
      (acc, cmd) => {
        const cat = cmd.category || "general";
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(cmd);
        return acc;
      },
      {} as Record<string, SlashCommand[]>,
    );
  }, [commands, lowerSearch]);

  // Page-relevant MCP tools: tools whose name contains a segment of the pathname.
  // On /browse with a selected skill, match against the skill name instead.
  const filteredPageTools = useMemo(() => {
    const segments = isBrowse && browseSkill
      ? [browseSkill.toLowerCase()]
      : pathname.split("/").filter((s) => s.length > 2).map((s) => s.toLowerCase());
    if (segments.length === 0) return [];
    return mcpTools.filter((t) => {
      const name = t.name.toLowerCase();
      const desc = (t.description || "").toLowerCase();
      const pageMatch = segments.some((seg) => name.includes(seg) || desc.includes(seg));
      if (!pageMatch) return false;
      if (!lowerSearch) return true;
      return name.includes(lowerSearch) || desc.includes(lowerSearch);
    });
  }, [mcpTools, pathname, lowerSearch, isBrowse, browseSkill]);

  // Check if "Analyze Page" matches the search filter
  const analyzePageVisible =
    !lowerSearch ||
    "analyze page".includes(lowerSearch) ||
    "magic".includes(lowerSearch);

  // --- Browse page: fetch prompts from RAG ---
  const { data: promptsData, loading: promptsLoading } = useMcpQuery<BrowseIndexResponse>(
    ["browse-prompts", browseSkill ?? ""],
    "browse-index",
    "config",
    {
      args: {
        category: "prompts",
        ...(browseSkill ? { search: browseSkill } : {}),
        limit: 30,
      },
      enabled: isBrowse && resolvedActiveTab === "prompts",
    },
  );

  const filteredPrompts = useMemo(() => {
    const items = promptsData?.items ?? [];
    if (!lowerSearch) return items;
    return items.filter(
      (p) =>
        p.title.toLowerCase().includes(lowerSearch) ||
        p.description.toLowerCase().includes(lowerSearch),
    );
  }, [promptsData, lowerSearch]);

  const buttonClass = isOpen
    ? TOOL_BUTTON_ACTIVE_CLASS
    : TOOL_BUTTON_IDLE_CLASS;

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={onToggle}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${buttonClass}`}
        title="Discover and execute actions, tools, and commands"
      >
        <Layers className="size-3" />
        <span>Actions</span>
        {pendingInsightCount > 0 && (
          <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
        )}
      </button>

      {isOpen && (
        <ChatSidePopover chatRef={chatContainerRef} portalRef={portalRef}>
          <div className="w-80 max-h-96 bg-[var(--bg-popover)] backdrop-blur-xl border border-[var(--border-color)]/60 rounded-xl shadow-2xl overflow-hidden">
            <TabPanel
              tabs={activeTabs}
              activeTab={resolvedActiveTab}
              onTabChange={setActiveTab}
              isOperationMode={isOperationMode}
              searchPlaceholder="Search actions, tools, commands..."
              searchValue={search}
              onSearchChange={setSearch}
            >
              <div className="overflow-y-auto max-h-72">
                {resolvedActiveTab === "actions" && (
                  <ActionsTab
                    isOperationMode={isOperationMode}
                    analyzePageVisible={analyzePageVisible}
                    onMagicClick={onMagicClick}
                    magicLoading={magicLoading}
                    pendingInsightCount={pendingInsightCount}
                    pageTools={filteredPageTools}
                    mcpToolsLoading={mcpToolsLoading}
                    search={search}
                    onInsertTool={onInsertTool}
                    isBrowse={isBrowse}
                    browseSkill={browseSkill}
                  />
                )}
                {resolvedActiveTab === "prompts" && (
                  <RagListTab
                    items={filteredPrompts}
                    loading={promptsLoading}
                    search={search}
                    icon={<MessageSquare className="size-3 text-[var(--accent-primary)] shrink-0" />}
                    emptyLabel="prompts"
                    onSelect={onInsertTool}
                  />
                )}
                {resolvedActiveTab === "mcp-tools" && (
                  <ToolsTab
                    tools={filteredTools}
                    loading={mcpToolsLoading}
                    search={search}
                    onInsertTool={onInsertTool}
                  />
                )}
                {resolvedActiveTab === "commands" && (
                  <CommandsTab
                    grouped={filteredCommands}
                    search={search}
                    onRunCommand={(cmd) => {
                      onRunCommand(cmd);
                      onToggle();
                    }}
                  />
                )}
              </div>
            </TabPanel>
          </div>
        </ChatSidePopover>
      )}
    </div>
  );
}

/* ---------- Actions Tab ---------- */

interface SkillActionItem {
  id: string;
  label: string;
  description?: string;
  icon?: string;
  dispatch?: string;
}

function ActionsTab({
  isOperationMode,
  analyzePageVisible,
  onMagicClick,
  magicLoading,
  pendingInsightCount,
  pageTools,
  mcpToolsLoading,
  search,
  onInsertTool,
  isBrowse,
  browseSkill,
}: {
  isOperationMode: boolean;
  analyzePageVisible: boolean;
  onMagicClick: () => void;
  magicLoading: boolean;
  pendingInsightCount: number;
  pageTools: McpTool[];
  mcpToolsLoading: boolean;
  search: string;
  onInsertTool: (toolName: string) => void;
  isBrowse: boolean;
  browseSkill: string | null;
}) {
  const showAnalyzePage = !isOperationMode && analyzePageVisible;
  const lowerSearch = search.toLowerCase();

  // On /browse with a selected skill, fetch that skill's declared actions via RAG
  const { data: skillActionsRaw, loading: skillActionsLoading } = useMcpQuery<{
    actions?: SkillActionItem[];
  }>(
    ["skill-actions-browse", browseSkill ?? ""],
    "list-skill-actions",
    "config",
    {
      args: { skill_name: browseSkill || "" },
      enabled: isBrowse && !!browseSkill,
    },
  );

  const skillActions = useMemo(() => {
    const actions = skillActionsRaw?.actions ?? [];
    if (!lowerSearch) return actions;
    return actions.filter(
      (a) =>
        a.label.toLowerCase().includes(lowerSearch) ||
        (a.description || "").toLowerCase().includes(lowerSearch),
    );
  }, [skillActionsRaw, lowerSearch]);

  return (
    <div className="flex flex-col">
      {/* Pinned: Analyze Page (dev only) */}
      {showAnalyzePage && (
        <div className="border-b border-[var(--border-color)]">
          <button
            type="button"
            onClick={onMagicClick}
            disabled={magicLoading}
            className="w-full text-left px-3 py-2 hover:bg-[var(--bg-hover)] transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <Wand2 className="size-3.5 text-violet-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-[var(--text-primary)]">
                Analyze Page
              </div>
              <div className="text-xs text-[var(--text-muted)]">
                {magicLoading
                  ? "Analyzing..."
                  : "Suggest improvements for this page"}
              </div>
            </div>
            {pendingInsightCount > 0 && (
              <span className="px-1.5 py-px rounded-full bg-orange-500/20 text-[10px] text-orange-400 font-semibold min-w-[16px] text-center">
                {pendingInsightCount}
              </span>
            )}
          </button>
        </div>
      )}

      {/* Skill actions from RAG (browse page with selected skill) */}
      {isBrowse && browseSkill && (
        <>
          {skillActionsLoading ? (
            <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
              Loading skill actions…
            </div>
          ) : skillActions.length > 0 ? (
            <>
              <div className="px-3 py-1.5 text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                Skill Actions
              </div>
              {skillActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => onInsertTool(`/${action.id}`)}
                  className="w-full text-left px-3 py-1.5 hover:bg-[var(--bg-secondary)] transition-colors group"
                >
                  <div className="flex items-center gap-1.5">
                    <Zap className="size-3 text-[var(--accent-primary)] shrink-0" />
                    <span className="text-xs font-medium text-[var(--text-primary)] group-hover:text-[var(--accent-primary)]">
                      {action.label}
                    </span>
                    {action.dispatch && (
                      <span className="text-[9px] text-[var(--text-muted)] ml-auto">
                        {action.dispatch}
                      </span>
                    )}
                  </div>
                  {action.description && (
                    <div className="text-xs text-[var(--text-muted)] truncate pl-[18px]">
                      {action.description}
                    </div>
                  )}
                </button>
              ))}
            </>
          ) : !search ? (
            <div className="p-3 text-center text-xs text-[var(--text-muted)]">
              No actions declared for this skill
            </div>
          ) : null}
        </>
      )}

      {/* Browse page with no skill selected */}
      {isBrowse && !browseSkill && !showAnalyzePage && (
        <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
          Select a skill to see its actions
        </div>
      )}

      {/* Page-relevant MCP tools */}
      {mcpToolsLoading ? (
        <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
          Loading page actions…
        </div>
      ) : pageTools.length > 0 ? (
        <>
          <div className="px-3 py-1.5 text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
            Page Tools
          </div>
          {pageTools.map((tool, index) => (
            <button
              key={`${tool.name}-${index}`}
              type="button"
              onClick={() => onInsertTool(tool.name)}
              className="w-full text-left px-3 py-1.5 hover:bg-[var(--bg-secondary)] transition-colors group"
            >
              <div className="text-xs font-mono text-[var(--text-primary)] group-hover:text-[var(--accent-primary)]">
                {tool.name}
              </div>
              {tool.description && (
                <div className="text-xs text-[var(--text-muted)] truncate">
                  {tool.description}
                </div>
              )}
            </button>
          ))}
        </>
      ) : !isBrowse && !showAnalyzePage ? (
        <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
          {search ? "No matching actions" : "No page-specific actions"}
        </div>
      ) : null}
    </div>
  );
}

/* ---------- MCP Tools Tab ---------- */

function ToolsTab({
  tools,
  loading,
  search,
  onInsertTool,
}: {
  tools: McpTool[];
  loading: boolean;
  search: string;
  onInsertTool: (toolName: string) => void;
}) {
  if (loading) {
    return (
      <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
        Loading tools…
      </div>
    );
  }

  if (tools.length === 0) {
    return (
      <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
        {search ? "No matching tools" : "No tools available"}
      </div>
    );
  }

  return (
    <>
      {tools.map((tool, index) => (
        <button
          key={`${tool.name}-${index}`}
          type="button"
          onClick={() => onInsertTool(tool.name)}
          className="w-full text-left px-3 py-1.5 hover:bg-[var(--bg-secondary)] transition-colors group"
        >
          <div className="text-xs font-mono text-[var(--text-primary)] group-hover:text-[var(--accent-primary)]">
            {tool.name}
          </div>
          {tool.description && (
            <div className="text-xs text-[var(--text-muted)] truncate">
              {tool.description}
            </div>
          )}
        </button>
      ))}
    </>
  );
}

/* ---------- RAG List Tab (Prompts) ---------- */

function RagListTab({
  items,
  loading,
  search,
  icon,
  emptyLabel,
  onSelect,
}: {
  items: BrowseIndexItem[];
  loading: boolean;
  search: string;
  icon: React.ReactNode;
  emptyLabel: string;
  onSelect: (value: string) => void;
}) {
  if (loading) {
    return (
      <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
        Loading {emptyLabel}…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
        {search ? `No matching ${emptyLabel}` : `No ${emptyLabel} indexed`}
      </div>
    );
  }

  return (
    <>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item.source_path || item.id)}
          className="w-full text-left px-3 py-1.5 hover:bg-[var(--bg-secondary)] transition-colors group"
        >
          <div className="flex items-center gap-1.5">
            {icon}
            <span className="text-xs font-medium text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] truncate">
              {item.title}
            </span>
            {item.hub && item.hub !== "system" && (
              <span className="text-[9px] text-[var(--text-muted)] ml-auto shrink-0">
                {item.hub}
              </span>
            )}
          </div>
          {item.description && (
            <div className="text-xs text-[var(--text-muted)] truncate pl-[18px]">
              {item.description}
            </div>
          )}
        </button>
      ))}
    </>
  );
}

/* ---------- Commands Tab ---------- */

function CommandsTab({
  grouped,
  search,
  onRunCommand,
}: {
  grouped: Record<string, SlashCommand[]>;
  search: string;
  onRunCommand: (command: SlashCommand) => void;
}) {
  if (Object.keys(grouped).length === 0) {
    return (
      <div className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
        {search
          ? `No commands match \u201c${search}\u201d`
          : "No commands available"}
      </div>
    );
  }

  return (
    <>
      {Object.entries(grouped).map(([category, cmds]) => (
        <div key={category}>
          <div className="px-3 py-1.5 text-[9px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
            {category}
          </div>
          {cmds.map((cmd) => (
            <button
              key={`${category}-${cmd.id || cmd.name}`}
              type="button"
              onClick={() => onRunCommand(cmd)}
              className="w-full text-left px-3 py-1.5 hover:bg-[var(--bg-hover)] transition-colors flex items-start gap-2"
            >
              <code className="text-[11px] font-mono text-emerald-400 whitespace-nowrap">
                {cmd.name}
              </code>
              <span className="text-xs text-[var(--text-muted)] flex-1 leading-normal">
                {cmd.description}
              </span>
            </button>
          ))}
        </div>
      ))}
    </>
  );
}
