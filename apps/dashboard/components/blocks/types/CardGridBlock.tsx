"use client";

import { useState, useMemo, useCallback } from "react";
import { LayoutGrid } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";
import RowActionsCell from "../RowActionsCell";
import { SearchBar } from "@/components/plugin/sections/SearchBar";
import { filterBySearch } from "@/components/plugin/sections/SearchBar.utils";
import { FilterBar } from "@/components/plugin/sections/FilterBar";
import { filterByPills } from "@/components/plugin/sections/FilterBar.utils";
import {
  ViewModeToggle,
  useViewMode,
} from "@/components/plugin/sections/ViewModeToggle";
import type { ViewMode } from "@/components/plugin/sections/types";
import { detectFields, autoFormat, badgeColor } from "@/lib/blocks/auto-detect";
import type { FieldRole, BadgeColor } from "@/lib/blocks/auto-detect";
import { Badge } from "@/components/ui/Badge";

interface CardGridConfig {
  title?: string;
  limit?: number;
  /** ADR-274 D5: Available view modes (list, grid, card) */
  viewModes?: ViewMode[];
  /** ADR-274 D5: Default view mode */
  defaultView?: ViewMode;
}
interface CardItem {
  id?: string;
  title?: string;
  name?: string;
  description?: string;
  count?: number;
}

const BADGE_VARIANT_MAP: Record<BadgeColor, "success" | "destructive" | "outline" | "default"> = {
  green: "success",
  red: "destructive",
  amber: "outline",
  gray: "outline",
  blue: "default",
};

/** Convert snake_case keys to Title Case labels */
function smartLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface CardGridItemViewProps {
  item: CardItem;
  index: number;
  titleField: string | null;
  subtitleField: string | null;
  badgeField: string | null;
  timestampField: string | null;
  detailFields: string[];
  fieldRoles: Map<string, FieldRole>;
  rowActions: BlockProps<CardGridConfig>["rowActions"];
  mcpTool: string | undefined;
}

function CardGridItemCard({
  item,
  index,
  titleField,
  subtitleField,
  badgeField,
  timestampField,
  detailFields,
  fieldRoles,
  rowActions,
  mcpTool,
}: CardGridItemViewProps) {
  const rec = item as Record<string, unknown>;
  const itemTitle = titleField
    ? String(rec[titleField] ?? "")
    : (item.title || item.name || `Card ${index + 1}`);
  const itemSubtitle = subtitleField
    ? String(rec[subtitleField] ?? "")
    : item.description;
  const itemBadge = badgeField ? String(rec[badgeField] ?? "") : undefined;
  const itemTimestamp = timestampField
    ? autoFormat(rec[timestampField], "timestamp")
    : undefined;

  return (
    <div
      className={`p-3 rounded-lg bg-[var(--bg-hover)]/30 border border-[var(--border-color)]/20 relative${rowActions?.length ? " cursor-pointer hover:bg-[var(--bg-hover)]/40 transition-colors" : ""}`}
    >
      {itemBadge && (
        <div className="absolute top-2 right-2">
          <Badge variant={BADGE_VARIANT_MAP[badgeColor(itemBadge)]} size="sm">
            {itemBadge}
          </Badge>
        </div>
      )}
      <div className="text-sm font-medium text-[var(--text-primary)] truncate pr-16">
        {itemTitle}
      </div>
      {itemSubtitle && (
        <div className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-2">
          {itemSubtitle}
        </div>
      )}
      {detailFields.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {detailFields.map((key) => {
            const role = fieldRoles.get(key) ?? "detail";
            return (
              <div key={key} className="flex items-center justify-between text-xs">
                <span className="text-[var(--text-muted)]">{smartLabel(key)}</span>
                <span className="text-[var(--text-secondary)] font-medium truncate ml-2 max-w-[60%] text-right">
                  {autoFormat(rec[key], role)}
                </span>
              </div>
            );
          })}
        </div>
      )}
      {itemTimestamp && (
        <div className="text-[10px] text-[var(--text-muted)] mt-1.5">
          {itemTimestamp}
        </div>
      )}
      {rowActions && rowActions.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[var(--border-color)]">
          <RowActionsCell actions={rowActions} row={rec} mcpTool={mcpTool} />
        </div>
      )}
    </div>
  );
}

function CardGridItemList({
  item,
  index,
  titleField,
  subtitleField,
  badgeField,
  timestampField,
  rowActions,
  mcpTool,
}: CardGridItemViewProps) {
  const rec = item as Record<string, unknown>;
  const itemTitle = titleField
    ? String(rec[titleField] ?? "")
    : (item.title || item.name || `Item ${index + 1}`);
  const itemSubtitle = subtitleField
    ? String(rec[subtitleField] ?? "")
    : item.description;
  const itemBadge = badgeField ? String(rec[badgeField] ?? "") : undefined;
  const itemTimestamp = timestampField
    ? autoFormat(rec[timestampField], "timestamp")
    : undefined;

  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 rounded-lg border border-[var(--border-color)]/20 bg-[var(--bg-hover)]/30${rowActions?.length ? " cursor-pointer hover:bg-[var(--bg-hover)]/40 transition-colors" : ""}`}
    >
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--text-primary)] truncate">
          {itemTitle}
        </div>
        {itemSubtitle && (
          <div className="text-xs text-[var(--text-muted)] truncate">
            {itemSubtitle}
          </div>
        )}
      </div>
      {itemBadge && (
        <Badge variant={BADGE_VARIANT_MAP[badgeColor(itemBadge)]} size="sm">
          {itemBadge}
        </Badge>
      )}
      {itemTimestamp && (
        <span className="text-[10px] text-[var(--text-muted)] shrink-0">
          {itemTimestamp}
        </span>
      )}
      {rowActions && rowActions.length > 0 && (
        <RowActionsCell actions={rowActions} row={rec} mcpTool={mcpTool} />
      )}
    </div>
  );
}

export default function CardGridBlock(props: BlockProps<CardGridConfig>) {
  const { config, dataSource, onExpand, instanceId } = props;
  const { title = "Cards", limit = 6, viewModes, defaultView } = config;

  // ADR-274 D5: view modes — prefer manifest-level props, then config
  const manifestViewModes = props.viewModes as ViewMode[] | undefined;
  const manifestDefaultView = props.defaultView as ViewMode | undefined;
  const resolvedModes = manifestViewModes ?? (viewModes && viewModes.length > 0 ? viewModes : null);
  const resolvedDefault = manifestDefaultView ?? defaultView ?? "grid";
  const [activeMode, setActiveMode] = useViewMode(
    `block-${instanceId}`,
    resolvedModes ?? ["grid"],
    resolvedDefault,
  );

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

  const selfFetched = useBlockData<CardItem[]>(
    dataSource,
    config,
    "card-grid",
  );
  const data = (props.data as CardItem[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const rawItems = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  // Auto-detect field roles from first item
  const fieldRoles = useMemo(() => {
    if (!rawItems || rawItems.length === 0) return new Map<string, FieldRole>();
    const first = rawItems[0] as Record<string, unknown>;
    return detectFields(first);
  }, [rawItems]);

  const titleField = useMemo(() => {
    for (const [key, role] of fieldRoles) if (role === "title") return key;
    return null;
  }, [fieldRoles]);

  const subtitleField = useMemo(() => {
    for (const [key, role] of fieldRoles) if (role === "subtitle") return key;
    return null;
  }, [fieldRoles]);

  const badgeField = useMemo(() => {
    for (const [key, role] of fieldRoles) if (role === "badge") return key;
    return null;
  }, [fieldRoles]);

  const timestampField = useMemo(() => {
    for (const [key, role] of fieldRoles) if (role === "timestamp") return key;
    return null;
  }, [fieldRoles]);

  const detailFields = useMemo(() => {
    const skip = new Set([titleField, subtitleField, badgeField, timestampField].filter(Boolean));
    const result: string[] = [];
    for (const [key, role] of fieldRoles) {
      if (skip.has(key)) continue;
      if (role === "nested" || role === "array" || role === "icon") continue;
      result.push(key);
      if (result.length >= 4) break;
    }
    return result;
  }, [fieldRoles, titleField, subtitleField, badgeField, timestampField]);

  // ADR-274: apply client-side search filtering — auto-detect search fields when not configured
  const effectiveSearchFields = useMemo(() => {
    if (props.search?.fields && props.search.fields.length > 0) return props.search.fields;
    if (!props.search?.enabled || !rawItems || rawItems.length === 0) return [];
    const first = rawItems[0] as Record<string, unknown>;
    return Object.keys(first).filter((k) => typeof first[k] === "string");
  }, [props.search, rawItems]);
  const searchFields = effectiveSearchFields.length > 0 ? effectiveSearchFields : ["title", "name", "description"];
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
    return result as CardItem[];
  }, [afterSearch, props.filters, activeFilters]);

  return (
    <BlockShell
      title={title}
      icon={LayoutGrid}
      color="purple"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4">
        {/* ADR-274: toolbar — search, filters, view mode toggle */}
        {(props.search?.enabled || props.filters || (resolvedModes && resolvedModes.length > 1)) && (
          <div className="space-y-2 mb-3">
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
            {resolvedModes && resolvedModes.length > 1 && (
              <div className="flex justify-end">
                <ViewModeToggle
                  sectionId={`block-${instanceId}`}
                  modes={resolvedModes}
                  defaultMode={resolvedDefault}
                  activeMode={activeMode}
                  onChange={setActiveMode}
                />
              </div>
            )}
          </div>
        )}

        {/* Content */}
        {activeMode === "list" ? (
          <div className="space-y-1.5">
            {loading &&
              Array.from({ length: Math.min(limit, 4) }, (_, i) => (
                <div
                  key={i}
                  className="h-12 rounded-lg bg-[var(--bg-hover)] animate-pulse"
                />
              ))}

            {!loading && items.length === 0 && !error && (
              <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
                No items
              </p>
            )}
            {!loading && items.length === 0 && error && (
              <div className="text-center py-6">
                <p className="text-xs text-red-400/80">Failed to load data</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
              </div>
            )}
            {!loading &&
              items.slice(0, limit).map((item, i) => (
                <CardGridItemList
                  key={item.id || i}
                  item={item}
                  index={i}
                  titleField={titleField}
                  subtitleField={subtitleField}
                  badgeField={badgeField}
                  timestampField={timestampField}
                  detailFields={detailFields}
                  fieldRoles={fieldRoles}
                  rowActions={props.rowActions}
                  mcpTool={props.dataSource?.mcpTool}
                />
              ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {loading &&
              Array.from({ length: Math.min(limit, 4) }, (_, i) => (
                <div
                  key={i}
                  className="h-16 rounded-lg bg-[var(--bg-hover)] animate-pulse"
                />
              ))}

            {!loading && items.length === 0 && !error && (
              <p className="col-span-2 text-xs text-[var(--text-muted)] italic text-center py-4">
                No items
              </p>
            )}
            {!loading && items.length === 0 && error && (
              <div className="col-span-2 text-center py-6">
                <p className="text-xs text-red-400/80">Failed to load data</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
              </div>
            )}
            {!loading &&
              items.slice(0, limit).map((item, i) => (
                <CardGridItemCard
                  key={item.id || i}
                  item={item}
                  index={i}
                  titleField={titleField}
                  subtitleField={subtitleField}
                  badgeField={badgeField}
                  timestampField={timestampField}
                  detailFields={detailFields}
                  fieldRoles={fieldRoles}
                  rowActions={props.rowActions}
                  mcpTool={props.dataSource?.mcpTool}
                />
              ))}
          </div>
        )}
      </div>
    </BlockShell>
  );
}
