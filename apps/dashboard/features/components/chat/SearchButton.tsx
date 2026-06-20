"use client";

import { Suspense, useReducer, useEffect, useRef, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";
import { TOOL_BUTTON_ACTIVE_CLASS, TOOL_BUTTON_BASE_CLASS, TOOL_BUTTON_IDLE_CLASS } from "@/components/chat/utils";
import {
  buildBrowseResultStream,
  buildBrowseTopResults,
  buildStandardResultStream,
  buildStandardTopResults,
  sortBrowseItems,
} from "./panelRanking";
import {
  BROWSE_SEARCH_CATEGORIES,
  INITIAL_SEARCH_UI_STATE,
} from "./SearchButton.types";
import type {
  BrowseIndexItem,
  BrowseSearchResults,
  SearchButtonProps,
} from "./SearchButton.types";
import {
  loadStandardSearchResults,
  readSearchParam,
  searchUiReducer,
} from "./SearchButton.search";
import { SearchButtonPopover } from "./SearchButton.popover";

export type { SearchButtonProps } from "./SearchButton.types";

export function SearchButton(props: SearchButtonProps) {
  return (
    <Suspense fallback={null}>
      <SearchButtonInner {...props} />
    </Suspense>
  );
}

function SearchButtonInner({
  isOperationMode,
  pathname,
  isOpen,
  onToggle,
  onAttachFile,
  chatContainerRef,
  portalRef,
  popoverRef,
}: SearchButtonProps) {
  const searchParams = useSearchParams();
  const [searchUi, dispatchSearchUi] = useReducer(
    searchUiReducer,
    INITIAL_SEARCH_UI_STATE,
  );
  const {
    query,
    scope,
    results,
    browseResults,
    loading,
    hasSearched,
    showOverflow,
  } = searchUi;
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isBrowse = pathname === "/browse";
  const browseSkill = isBrowse ? readSearchParam(searchParams, "skill") : null;

  const buttonClass = isOpen ? TOOL_BUTTON_ACTIVE_CLASS : TOOL_BUTTON_IDLE_CLASS;

  // Auto-focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      // Small delay to let the popover render
      const timer = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Reset state when panel closes
  useEffect(() => {
    if (!isOpen) {
      const timer = window.setTimeout(() => {
        dispatchSearchUi({ type: "reset" });
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [isOpen]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      dispatchSearchUi({ type: "hide-overflow" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [query, scope, isBrowse, browseSkill]);

  // --- Browse page: search via browse-index (RAG) across categories ---
  const executeBrowseSearch = useCallback(
    async (searchQuery: string) => {
      if (!searchQuery.trim()) {
        dispatchSearchUi({ type: "clear-browse" });
        return;
      }

      dispatchSearchUi({ type: "start-search" });

      try {
        // Search all browse categories in parallel via browse-index MCP tool
        const responses = await Promise.all(
          BROWSE_SEARCH_CATEGORIES.map((category) =>
            mcpCall<{ items?: BrowseIndexItem[] }>("browse-index", {
              category,
              search: searchQuery,
              limit: 15,
            }).catch(() => ({ items: [] as BrowseIndexItem[] })),
          ),
        );

        const grouped: BrowseSearchResults = {
          skills: [],
          vault: [],
          wiki: [],
          documents: [],
          actions: [],
        };

        BROWSE_SEARCH_CATEGORIES.forEach((category, i) => {
          const items = responses[i]?.items ?? [];
          // When a skill is selected and scope is "skill", filter to that skill
          const filtered = scope === "skill" && browseSkill
            ? items.filter(
                (item) =>
                  item.id === browseSkill ||
                  item.hub === browseSkill ||
                  item.metadata?.skill === browseSkill,
              )
            : items;
          grouped[category] = sortBrowseItems(filtered, searchQuery, browseSkill);
        });

        dispatchSearchUi({ type: "browse-results", browseResults: grouped });
      } catch {
        dispatchSearchUi({ type: "browse-error" });
      }
    },
    [scope, browseSkill],
  );

  // --- Standard skill page: search via API endpoints ---
  const executeStandardSearch = useCallback(
    async (searchQuery: string) => {
      if (!searchQuery.trim()) {
        dispatchSearchUi({ type: "clear-standard" });
        return;
      }

      dispatchSearchUi({ type: "start-search" });

      try {
        const grouped = await loadStandardSearchResults({
          searchQuery,
          scope,
          pathname,
          isOperationMode,
        });
        dispatchSearchUi({ type: "standard-results", results: grouped });
      } catch {
        dispatchSearchUi({ type: "standard-error" });
      }
    },
    [pathname, scope, isOperationMode],
  );

  const executeSearch = isBrowse ? executeBrowseSearch : executeStandardSearch;

  // Debounced search — only fire when query is non-empty
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!isOpen || !query.trim()) {
      if (!query.trim() && isOpen) {
        const timer = window.setTimeout(() => {
          dispatchSearchUi({ type: "clear-standard" });
        }, 0);
        return () => window.clearTimeout(timer);
      }
      return;
    }

    debounceRef.current = setTimeout(() => {
      executeSearch(query);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, isOpen, executeSearch]);

  const totalResults = isBrowse
    ? browseResults.skills.length +
      browseResults.vault.length +
      browseResults.wiki.length +
      browseResults.documents.length +
      browseResults.actions.length
    : results.knowledge.length + results.files.length + results.logs.length;

  const browseTopResults = useMemo(
    () => buildBrowseTopResults(browseResults, query, browseSkill, 4),
    [browseResults, query, browseSkill],
  );
  const browseResultStream = useMemo(
    () => buildBrowseResultStream(browseResults, query, browseSkill),
    [browseResults, query, browseSkill],
  );
  const standardTopResults = useMemo(
    () => buildStandardTopResults(results, query, 4),
    [results, query],
  );
  const standardResultStream = useMemo(
    () => buildStandardResultStream(results, query),
    [results, query],
  );
  const browseOverflowResults = useMemo(
    () => browseResultStream.slice(browseTopResults.length),
    [browseResultStream, browseTopResults.length],
  );
  const standardOverflowResults = useMemo(
    () => standardResultStream.slice(standardTopResults.length),
    [standardResultStream, standardTopResults.length],
  );

  // Scope label adapts to context
  const scopeSkillLabel = isBrowse && browseSkill ? browseSkill : "This skill";

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={onToggle}
        className={`${TOOL_BUTTON_BASE_CLASS} ${buttonClass}`}
        title="Search knowledge, files, and decisions"
      >
        <Search className="size-3" />
        <span>Search</span>
      </button>

      {isOpen && (
        <SearchButtonPopover
          chatContainerRef={chatContainerRef}
          portalRef={portalRef}
          inputRef={inputRef}
          state={{
            query,
            scope,
            loading,
            hasSearched,
            showOverflow,
            isBrowse,
            browseSkill,
            scopeSkillLabel,
            totalResults,
          }}
          browseTopResults={browseTopResults}
          browseOverflowResults={browseOverflowResults}
          standardTopResults={standardTopResults}
          standardOverflowResults={standardOverflowResults}
          onQueryChange={(nextQuery) =>
            dispatchSearchUi({ type: "set-query", query: nextQuery })
          }
          onScopeChange={(nextScope) =>
            dispatchSearchUi({ type: "set-scope", scope: nextScope })
          }
          onToggleOverflow={() =>
            dispatchSearchUi({ type: "toggle-overflow" })
          }
          onAttachFile={onAttachFile}
        />
      )}
    </div>
  );
}
