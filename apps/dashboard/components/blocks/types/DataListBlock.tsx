"use client";

import { useState, useMemo, useCallback } from "react";
import { List, WifiOff } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import RowActionsCell from "../RowActionsCell";
import { SearchBar } from "@/components/plugin/sections/SearchBar";
import { filterBySearch } from "@/components/plugin/sections/SearchBar.utils";
import { FilterBar } from "@/components/plugin/sections/FilterBar";
import { filterByPills } from "@/components/plugin/sections/FilterBar.utils";

interface DataListConfig {
  title?: string;
  filter?: string;
  limit?: number;
}
interface DataListItem {
  id?: string;
  title?: string;
  name?: string;
  label?: string;
  subtitle?: string;
  badge?: string;
}

type DataListData = DataListItem[] | { items?: DataListItem[] };

type NotConnectedPayload = {
  connected: false;
  message?: string;
  setup_hint?: string;
};

function isNotConnected(data: unknown): data is NotConnectedPayload {
  return (
    data !== null &&
    typeof data === "object" &&
    "connected" in (data as object) &&
    (data as Record<string, unknown>).connected === false
  );
}

export default function DataListBlock(props: BlockProps<DataListConfig>) {
  const { config, dataSource, mode, onExpand } = props;
  const { title = "List", limit = 5 } = config;
  const selfFetched = useBlockData<DataListData>(dataSource, config, "data-list");
  const data = (props.data as DataListData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  // ADR-274: search state
  const [searchText, setSearchText] = useState("");
  // ADR-274: filter state
  const [activeFilters, setActiveFilters] = useState<Record<string, Set<string>>>({});

  const handleFilterToggle = useCallback((field: string, value: string) => {
    setActiveFilters((prev) => {
      const current = prev[field] ?? new Set<string>();
      const next = new Set(current);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return { ...prev, [field]: next };
    });
  }, []);

  const notConnected = !loading && isNotConnected(data);

  const rawItems = notConnected
    ? []
    : Array.isArray(data) ? data : (data as { items?: DataListItem[] })?.items || [];

  // ADR-274: apply client-side search filtering
  const searchFields = props.search?.fields ?? ["title", "name", "label"];
  const afterSearch = props.search?.enabled
    ? filterBySearch(rawItems as Record<string, unknown>[], searchText, searchFields)
    : rawItems;

  // ADR-274: apply client-side pill filtering
  const items = useMemo(() => {
    let result = afterSearch as Record<string, unknown>[];
    if (props.filters) {
      for (const filterDef of props.filters) {
        const active = activeFilters[filterDef.field];
        if (active && active.size > 0) {
          result = filterByPills(result, filterDef.field, active);
        }
      }
    }
    return result as DataListItem[];
  }, [afterSearch, props.filters, activeFilters]);

  if (notConnected && isNotConnected(data)) {
    return (
      <BlockShell title={title} icon={List} color="cyan" onExpand={onExpand}>
        <div className="flex flex-col items-center justify-center p-6 gap-2 text-center">
          <WifiOff className="size-5 text-[var(--text-muted)] mb-1" />
          <p className="text-sm text-[var(--text-secondary)]">
            {data.message ?? "Service not connected"}
          </p>
          {data.setup_hint && (
            <p className="text-xs text-[var(--text-muted)]">{data.setup_hint}</p>
          )}
        </div>
      </BlockShell>
    );
  }

  return (
    <BlockShell
      title={title}
      icon={List}
      color="cyan"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4 space-y-1">
        {/* ADR-274: toolbar — search, filters */}
        {(props.search?.enabled || props.filters) && (
          <div className="space-y-2 mb-2">
            {props.search?.enabled && (
              <SearchBar
                placeholder={props.search.placeholder}
                value={searchText}
                onChange={setSearchText}
              />
            )}
            {props.filters?.map((filterDef) => (
              <FilterBar
                key={filterDef.field}
                filter={filterDef}
                activeValues={activeFilters[filterDef.field] ?? new Set<string>()}
                onToggle={(value) => handleFilterToggle(filterDef.field, value)}
              />
            ))}
          </div>
        )}

        {loading &&
          Array.from({ length: Math.min(limit, 4) }, (_, i) => (
            <div
              key={i}
              className="flex items-center gap-3 py-2 border-b border-[var(--border-color)]/30 last:border-0"
            >
              <div className="size-1.5 rounded-full bg-cyan-500/60 shrink-0" />
              <div className="flex-1 h-3 rounded bg-[var(--bg-hover)] animate-pulse" />
            </div>
          ))}

        {!loading && !error && items.length === 0 && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No items
          </p>
        )}
        {!loading && error && items.length === 0 && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading &&
          items.slice(0, limit).map((item, i) => (
            <div
              key={item.id || i}
              className="flex items-center gap-3 py-2 border-b border-[var(--border-color)]/30 last:border-0"
            >
              <div className="size-1.5 rounded-full bg-cyan-500/60 shrink-0" />
              <span className="flex-1 text-sm text-[var(--text-primary)] truncate">
                {item.title || item.name || item.label || `Item ${i + 1}`}
              </span>
              {item.badge && (
                <span className="text-xs text-[var(--text-muted)] bg-[var(--bg-hover)] px-1.5 py-0.5 rounded">
                  {item.badge}
                </span>
              )}
              {props.rowActions && props.rowActions.length > 0 && (
                <div className="ml-auto shrink-0">
                  <RowActionsCell
                    actions={props.rowActions}
                    row={item as Record<string, unknown>}
                    mcpTool={props.dataSource?.mcpTool}
                  />
                </div>
              )}
            </div>
          ))}
      </div>
    </BlockShell>
  );
}
