"use client";

import { Search, X, Loader2 } from "lucide-react";
import { ChatSidePopover } from "./ChatSidePopover";
import {
  SectionHeader,
  OverflowSection,
  KnowledgeResultRow,
  FileResultRow,
  BrowseResultRow,
} from "./SearchButton.rows";
import type {
  FileResult,
  KnowledgeResult,
  SearchButtonPopoverProps,
} from "./SearchButton.types";

export function SearchButtonPopover({
  chatContainerRef,
  portalRef,
  inputRef,
  state,
  browseTopResults,
  browseOverflowResults,
  standardTopResults,
  standardOverflowResults,
  onQueryChange,
  onScopeChange,
  onToggleOverflow,
  onAttachFile,
}: SearchButtonPopoverProps) {
  return (
    <ChatSidePopover chatRef={chatContainerRef} portalRef={portalRef}>
      <div className="flex max-h-96 w-80 flex-col overflow-hidden rounded-2xl border border-[var(--border-color)]/70 bg-[var(--bg-popover)]/96 shadow-2xl backdrop-blur-2xl">
        <div className="m-2 mb-1 flex items-center gap-2 rounded-2xl border border-[var(--border-color)]/70 bg-[var(--bg-primary)]/65 px-3 py-2">
          <Search className="size-3.5 text-[var(--text-muted)] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={state.query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder={state.isBrowse ? "Search RAG index..." : "Search knowledge & files..."}
            aria-label="Search knowledge and files"
            className="flex-1 bg-transparent text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
          />
          {state.loading && (
            <Loader2 className="size-3 text-[var(--text-muted)] animate-spin shrink-0" />
          )}
          {state.query && !state.loading && (
            <button
              type="button"
              onClick={() => onQueryChange("")}
              className="flex size-6 items-center justify-center rounded-full text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]"
              aria-label="Clear search query"
            >
              <X className="size-3" />
            </button>
          )}
        </div>

        <div className="mx-2 mb-1 flex items-center gap-1 rounded-full border border-[var(--border-color)]/60 bg-[var(--bg-primary)]/55 px-2 py-1.5">
          <span className="text-[10px] text-[var(--text-muted)] mr-1">Scope:</span>
          {(!state.isBrowse || state.browseSkill) && (
            <button
              type="button"
              onClick={() => onScopeChange("skill")}
              aria-pressed={state.scope === "skill"}
              className={`max-w-[120px] truncate rounded-full px-2.5 py-1 text-[10px] font-medium transition-colors ${
                state.scope === "skill"
                  ? "bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]"
                  : "text-[var(--text-muted)] hover:bg-[var(--bg-card)]/80 hover:text-[var(--text-secondary)]"
              }`}
            >
              {state.scopeSkillLabel}
            </button>
          )}
          <button
            type="button"
            onClick={() => onScopeChange("all")}
            aria-pressed={state.scope === "all"}
            className={`rounded-full px-2.5 py-1 text-[10px] font-medium transition-colors ${
              state.scope === "all" || (state.isBrowse && !state.browseSkill)
                ? "bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]"
                : "text-[var(--text-muted)] hover:bg-[var(--bg-card)]/80 hover:text-[var(--text-secondary)]"
            }`}
          >
            All
          </button>
        </div>

        <div className="overflow-y-auto max-h-72 flex-1">
          {!state.hasSearched && !state.loading && (
            <div className="px-3 py-6 text-center text-xs text-[var(--text-muted)]">
              Type to search…
            </div>
          )}
          {state.loading && !state.hasSearched && (
            <div className="px-3 py-6 text-center text-xs text-[var(--text-muted)]">
              Searching…
            </div>
          )}
          {state.hasSearched && !state.loading && state.totalResults === 0 && (
            <div className="px-3 py-6 text-center text-xs text-[var(--text-muted)]">
              No results found
            </div>
          )}

          {state.isBrowse && state.hasSearched && state.totalResults > 0 && browseTopResults.length > 0 && (
            <div>
              <SectionHeader icon={<Search className="size-3" />} label="Top Results" count={browseTopResults.length} />
              {browseTopResults.map(({ key, category, item }) => (
                <BrowseResultRow key={key} category={category} item={item} onAttach={onAttachFile} />
              ))}
            </div>
          )}
          {state.isBrowse && state.hasSearched && browseOverflowResults.length > 0 && (
            <OverflowSection expanded={state.showOverflow} count={browseOverflowResults.length} onToggle={onToggleOverflow}>
              {browseOverflowResults.map(({ key, category, item }) => (
                <BrowseResultRow key={key} category={category} item={item} onAttach={onAttachFile} />
              ))}
            </OverflowSection>
          )}

          {!state.isBrowse && state.hasSearched && state.totalResults > 0 && standardTopResults.length > 0 && (
            <div>
              <SectionHeader icon={<Search className="size-3" />} label="Top Results" count={standardTopResults.length} />
              {standardTopResults.map(({ key, category, item }) =>
                category === "knowledge" ? (
                  <KnowledgeResultRow key={key} category={category} item={item as KnowledgeResult} onAttach={onAttachFile} />
                ) : (
                  <FileResultRow key={key} category={category} file={item as FileResult} onAttach={onAttachFile} />
                ),
              )}
            </div>
          )}
          {!state.isBrowse && state.hasSearched && standardOverflowResults.length > 0 && (
            <OverflowSection expanded={state.showOverflow} count={standardOverflowResults.length} onToggle={onToggleOverflow}>
              {standardOverflowResults.map(({ key, category, item }) =>
                category === "knowledge" ? (
                  <KnowledgeResultRow key={key} category={category} item={item as KnowledgeResult} onAttach={onAttachFile} />
                ) : (
                  <FileResultRow key={key} category={category} file={item as FileResult} onAttach={onAttachFile} />
                ),
              )}
            </OverflowSection>
          )}
        </div>
      </div>
    </ChatSidePopover>
  );
}
