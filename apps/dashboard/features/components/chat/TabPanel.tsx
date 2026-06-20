"use client";

import { Search, X } from "lucide-react";

export interface TabDefinition {
  id: string;
  label: string;
  devOnly?: boolean;
}

export interface TabPanelProps {
  tabs: TabDefinition[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  isOperationMode: boolean;
  searchPlaceholder?: string;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  children: React.ReactNode;
}

export function TabPanel({
  tabs,
  activeTab,
  onTabChange,
  isOperationMode,
  searchPlaceholder = "Search...",
  searchValue,
  onSearchChange,
  children,
}: TabPanelProps) {
  const visibleTabs = tabs.filter((tab) => !tab.devOnly || !isOperationMode);
  const showSearch = onSearchChange !== undefined;

  return (
    <div className="flex flex-col">
      {/* Tab bar */}
      <div className="flex items-center gap-0.5 px-2 border-b border-[var(--border-color)] overflow-x-auto scrollbar-none">
        {visibleTabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={`relative inline-flex items-center gap-1.5 px-2.5 py-2 text-[11px] font-medium transition-colors whitespace-nowrap shrink-0 ${
                isActive
                  ? "text-violet-400"
                  : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              <span>{tab.label}</span>
              {tab.devOnly && !isOperationMode && (
                <span className="px-1 py-px rounded text-[9px] font-semibold leading-none bg-amber-500/15 text-amber-400">
                  DEV
                </span>
              )}
              {isActive && (
                <span className="absolute bottom-0 left-1 right-1 h-[2px] rounded-t bg-violet-500" />
              )}
            </button>
          );
        })}
      </div>

      {/* Optional search bar */}
      {showSearch && (
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border-color)]">
          <Search className="size-3.5 text-[var(--text-muted)] shrink-0" />
          <input
            type="text"
            value={searchValue ?? ""}
            onChange={(e) => onSearchChange?.(e.target.value)}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            className="flex-1 bg-transparent text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
          />
          {searchValue && (
            <button
              type="button"
              onClick={() => onSearchChange?.("")}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              aria-label="Clear search"
            >
              <X className="size-3" />
            </button>
          )}
        </div>
      )}

      {/* Tab content */}
      <div>{children}</div>
    </div>
  );
}
