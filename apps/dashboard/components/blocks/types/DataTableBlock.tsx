"use client";

import { useState, useMemo, useCallback } from "react";
import { Table2, WifiOff } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { useActionRunner } from "@/hooks/useActionRunner";
import { BlockShell } from "../BlockShell";
import RowActionsCell from "../RowActionsCell";
import { EditableCell } from "../EditableCell";
import { SearchBar } from "@/components/plugin/sections/SearchBar";
import { filterBySearch } from "@/components/plugin/sections/SearchBar.utils";
import { FilterBar } from "@/components/plugin/sections/FilterBar";
import { filterByPills } from "@/components/plugin/sections/FilterBar.utils";
import { QuickAddRow } from "@/components/plugin/sections/QuickAddRow";
import { ExportButton } from "@/components/plugin/sections/ExportButton";
import { DetailModal } from "@/components/plugin/sections/DetailModal";
import type { RowActionDefinition } from "@/components/plugin/sections/types";
import { keyedRenderItems } from "@/lib/stable-render-key";

interface DataTableConfig {
  title?: string;
  limit?: number;
  /** ADR-274 D8: Row click opens a detail modal when configured */
  rowAction?: RowActionDefinition;
}

type NotConnectedPayload = {
  connected: false;
  message?: string;
  setup_hint?: string;
};

function isNotConnected(data: unknown): data is NotConnectedPayload {
  return (
    data !== null &&
    typeof data === "object" &&
    !Array.isArray(data) &&
    "connected" in (data as object) &&
    (data as Record<string, unknown>).connected === false
  );
}

type TableRow = Record<string, unknown>;

interface DataTableToolbarProps {
  search: BlockProps<DataTableConfig>["search"];
  filters: BlockProps<DataTableConfig>["filters"];
  exportEnabled: BlockProps<DataTableConfig>["exportEnabled"];
  rows: TableRow[];
  searchText: string;
  activeFilters: Record<string, Set<string>>;
  onSearchTextChange: (value: string) => void;
  onFilterToggle: (field: string, value: string) => void;
}

function DataTableToolbar({
  search,
  filters,
  exportEnabled,
  rows,
  searchText,
  activeFilters,
  onSearchTextChange,
  onFilterToggle,
}: DataTableToolbarProps) {
  if (!search?.enabled && !filters && !exportEnabled) return null;

  return (
    <div className="space-y-2 mb-2">
      {search?.enabled && (
        <SearchBar
          placeholder={search.placeholder}
          value={searchText}
          onChange={onSearchTextChange}
        />
      )}
      {filters?.map((filterDef) => (
        <FilterBar
          key={filterDef.field}
          filter={filterDef}
          activeValues={activeFilters[filterDef.field] ?? new Set<string>()}
          onToggle={(value) => onFilterToggle(filterDef.field, value)}
        />
      ))}
      {exportEnabled && (
        <div className="flex justify-end">
          <ExportButton config={{ enabled: true }} data={rows} />
        </div>
      )}
    </div>
  );
}

interface MobileCardsProps {
  keyedRows: Array<{ item: TableRow; key: string }>;
  columns: string[];
  hasRowModal: boolean;
  rowActions: BlockProps<DataTableConfig>["rowActions"];
  mcpTool: string | undefined;
  onRowClick: (row: TableRow) => void;
  onMobileRowKeyDown: (
    event: React.KeyboardEvent<HTMLElement>,
    row: TableRow,
  ) => void;
}

function DataTableMobileCards({
  keyedRows,
  columns,
  hasRowModal,
  rowActions,
  mcpTool,
  onRowClick,
  onMobileRowKeyDown,
}: MobileCardsProps) {
  return (
    <div data-testid="data-table-mobile-cards" className="grid gap-2 sm:hidden">
      {keyedRows.map(({ item: row, key }) => {
        const fields = (
          <dl className="space-y-2">
            {columns.map((col) => (
              <div key={col} className="grid gap-1">
                <dt className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">{col}</dt>
                <dd className="break-words text-xs text-[var(--text-primary)]">
                  {String(row[col] ?? "")}
                </dd>
              </div>
            ))}
          </dl>
        );

        return (
          <article
            key={key}
            className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3"
          >
            {hasRowModal ? (
              <button
                type="button"
                className="block w-full rounded-md border-0 bg-transparent p-0 text-left"
                onClick={() => onRowClick(row)}
                onKeyDown={(event) => onMobileRowKeyDown(event, row)}
              >
                {fields}
              </button>
            ) : (
              fields
            )}
            {rowActions && rowActions.length > 0 && (
              <div className="mt-3 flex items-center justify-end border-t border-[var(--border-color)]/40 pt-3">
                <RowActionsCell actions={rowActions} row={row} mcpTool={mcpTool} />
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

interface DesktopTableProps {
  keyedRows: Array<{ item: TableRow; key: string }>;
  columns: string[];
  hasRowModal: boolean;
  rowActions: BlockProps<DataTableConfig>["rowActions"];
  editableFields: BlockProps<DataTableConfig>["editableFields"];
  mcpTool: string | undefined;
  onRowClick: (row: TableRow) => void;
}

function DataTableDesktopTable({
  keyedRows,
  columns,
  hasRowModal,
  rowActions,
  editableFields,
  mcpTool,
  onRowClick,
}: DesktopTableProps) {
  return (
    <table className="hidden w-full text-xs sm:table">
      <thead>
        <tr className="border-b border-[var(--border-color)]/50">
          {columns.map((col) => (
            <th
              key={col}
              scope="col"
              className="text-left py-1.5 px-2 text-[var(--text-muted)] font-medium capitalize"
            >
              {col}
            </th>
          ))}
          {rowActions && rowActions.length > 0 && (
            <th scope="col" className="text-left py-1.5 px-2 text-[var(--text-muted)] font-medium">
              Actions
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {keyedRows.map(({ item: row, key }) => (
          <tr
            key={key}
            className={`border-b border-[var(--border-color)]/20${(hasRowModal || (rowActions && rowActions.length > 0)) ? " cursor-pointer hover:bg-[var(--bg-hover)]/50" : ""}`}
            onClick={() => onRowClick(row)}
          >
            {columns.map((col) => {
              const editableField = editableFields?.find((field) => field.field === col);
              return (
                <td
                  key={col}
                  className="py-1.5 px-2 text-[var(--text-primary)] truncate max-w-[120px]"
                >
                  {editableField ? (
                    <EditableCell
                      field={editableField}
                      value={row[col]}
                      rowId={String(row.id ?? key)}
                    />
                  ) : (
                    String(row[col] ?? "")
                  )}
                </td>
              );
            })}
            {rowActions && rowActions.length > 0 && (
              <td className="py-1.5 px-2">
                <RowActionsCell actions={rowActions} row={row} mcpTool={mcpTool} />
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function DataTableBlock(props: BlockProps<DataTableConfig>) {
  const { config, dataSource, mode, onExpand } = props;
  const { title = "Table", limit = 10 } = config;
  const { runAction } = useActionRunner();
  const selfFetched = useBlockData<Record<string, unknown>[]>(
    dataSource,
    config,
    "data-table",
  );
  const data = (props.data as Record<string, unknown>[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  // ADR-274: search state
  const [searchText, setSearchText] = useState("");
  // ADR-274: filter state — map of field → active values
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

  const quickAddAction = props.quickAdd?.action;
  const handleQuickAddSubmit = useCallback(async (values: Record<string, string>) => {
    if (!quickAddAction) return;
    const ok = await runAction({
      id: quickAddAction,
      label: "Add item",
      description: "Add item via quick-add",
      dispatch: "fire",
      page: typeof window !== "undefined" ? window.location.pathname : "",
      args: values,
    });
    if (!ok) throw new Error("Action failed");
  }, [quickAddAction, runAction]);

  // ADR-274 D8: detail modal state
  const [modalItem, setModalItem] = useState<Record<string, unknown> | null>(null);
  const rowActionConfig = config.rowAction;
  const hasRowModal = rowActionConfig?.type === "modal";

  const handleRowClick = useCallback(
    (row: Record<string, unknown>) => {
      if (hasRowModal) {
        setModalItem(row);
      }
    },
    [hasRowModal],
  );
  const handleMobileRowKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLElement>, row: Record<string, unknown>) => {
      if (!hasRowModal || event.target !== event.currentTarget) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handleRowClick(row);
      }
    },
    [handleRowClick, hasRowModal],
  );

  const notConnected = !loading && isNotConnected(data);

  const rawRows = notConnected ? [] : (Array.isArray(data) ? data : []);

  // ADR-274: apply client-side search filtering
  const searchFields = props.search?.fields ?? (rawRows.length > 0 ? Object.keys(rawRows[0]).filter((k) => k !== "id") : []);
  const afterSearch = props.search?.enabled
    ? filterBySearch(rawRows, searchText, searchFields)
    : rawRows;

  // ADR-274: apply client-side pill filtering
  const rows = useMemo(() => {
    let result = afterSearch;
    if (props.filters) {
      for (const filterDef of props.filters) {
        const active = activeFilters[filterDef.field];
        if (active && active.size > 0) {
          result = filterByPills(result, filterDef.field, active);
        }
      }
    }
    return result;
  }, [afterSearch, props.filters, activeFilters]);
  const visibleRows = useMemo(() => rows.slice(0, limit), [rows, limit]);
  const keyedRows = useMemo(() => keyedRenderItems(visibleRows), [visibleRows]);

  const columns =
    rawRows.length > 0
      ? Object.keys(rawRows[0])
          .filter((k) => k !== "id")
          .slice(0, 4)
      : [];

  if (notConnected) {
    return (
      <BlockShell title={title} icon={Table2} color="emerald" onExpand={onExpand}>
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
      icon={Table2}
      color="emerald"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-2 overflow-auto">
        <DataTableToolbar
          search={props.search}
          filters={props.filters}
          exportEnabled={props.exportEnabled}
          rows={rows}
          searchText={searchText}
          activeFilters={activeFilters}
          onSearchTextChange={setSearchText}
          onFilterToggle={handleFilterToggle}
        />

        {/* ADR-274: quick-add row */}
        {props.quickAdd?.enabled && (
          <div className="mb-2">
            <QuickAddRow
              config={{
                enabled: props.quickAdd.enabled,
                fields: props.quickAdd.fields.map((f) => ({
                  name: f.name,
                  type: f.type as 'text' | 'select' | 'number' | 'date',
                  required: f.required,
                  placeholder: f.placeholder,
                  options: f.options,
                })),
                action: props.quickAdd.action,
              }}
              onSubmit={handleQuickAddSubmit}
            />
          </div>
        )}

        {loading &&
          ["data-row-skeleton-a", "data-row-skeleton-b", "data-row-skeleton-c"].map((key) => (
            <div
              key={key}
              className="h-8 mb-1 rounded bg-[var(--bg-hover)] animate-pulse"
            />
          ))}

        {!loading && rows.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No data
          </p>
        )}
        {!loading && rows.length === 0 && error && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading && rows.length > 0 && (
          <>
            <DataTableMobileCards
              keyedRows={keyedRows}
              columns={columns}
              hasRowModal={hasRowModal}
              rowActions={props.rowActions}
              mcpTool={props.dataSource?.mcpTool}
              onRowClick={handleRowClick}
              onMobileRowKeyDown={handleMobileRowKeyDown}
            />
            <DataTableDesktopTable
              keyedRows={keyedRows}
              columns={columns}
              hasRowModal={hasRowModal}
              rowActions={props.rowActions}
              editableFields={props.editableFields}
              mcpTool={props.dataSource?.mcpTool}
              onRowClick={handleRowClick}
            />
          </>
        )}
      </div>

      {/* ADR-274 D8: Detail modal on row click */}
      {hasRowModal && modalItem && rowActionConfig && (
        <DetailModal
          item={modalItem}
          config={rowActionConfig}
          onClose={() => setModalItem(null)}
        />
      )}
    </BlockShell>
  );
}
