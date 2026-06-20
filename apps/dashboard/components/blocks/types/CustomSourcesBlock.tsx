"use client";

import { Database } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { keyedRenderItems } from "@/lib/stable-render-key";
import { BlockShell } from "../BlockShell";

interface CustomSourcesConfig {
  title?: string;
  display?: "table" | "cards";
  limit?: number;
}

export default function CustomSourcesBlock(props: BlockProps<CustomSourcesConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Custom Sources", display = "table", limit = 10 } = config;
  const selfFetched = useBlockData<Record<string, unknown>[]>(
    dataSource,
    config,
    "custom-sources",
  );
  const data = (props.data as Record<string, unknown>[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  const rows = Array.isArray(data) ? data : [];
  const columns =
    rows.length > 0
      ? Object.keys(rows[0])
          .filter((k) => k !== "id")
          .slice(0, 5)
      : [];
  const visibleRows = rows.slice(0, limit);
  const keyedRows = keyedRenderItems(visibleRows);

  return (
    <BlockShell title={title} icon={Database} color="amber" onExpand={onExpand} staleError={error}>
      <div className="p-3 overflow-auto">
        {loading &&
          ["source-row-skeleton-a", "source-row-skeleton-b", "source-row-skeleton-c"].map((key) => (
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


        {/* Card display mode */}
        {!loading && rows.length > 0 && display === "cards" && (
          <div className="grid grid-cols-2 gap-2">
            {keyedRows.map(({ item: row, key }) => (
              <div
                key={key}
                className="rounded-lg bg-[var(--bg-hover)]/30 p-3"
              >
                {columns.slice(0, 3).map((col) => (
                  <div key={col} className="flex gap-1.5 text-xs truncate">
                    <span className="shrink-0 font-medium text-[var(--text-muted)]">
                      {col}:
                    </span>
                    <span className="truncate text-[var(--text-primary)]">
                      {String(row[col] ?? "-")}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Table display mode (default) */}
        {!loading && rows.length > 0 && display !== "cards" && (
          <table className="w-full text-xs">
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
              </tr>
            </thead>
            <tbody>
              {keyedRows.map(({ item: row, key }) => (
                <tr
                  key={key}
                  className="border-b border-[var(--border-color)]/20"
                >
                  {columns.map((col) => (
                    <td
                      key={col}
                      className="py-1.5 px-2 text-[var(--text-primary)] truncate max-w-[120px]"
                    >
                      {String(row[col] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!loading && rows.length > limit && (
          <p className="mt-2 text-[10px] text-[var(--text-muted)] text-right">
            +{rows.length - limit} more
          </p>
        )}
      </div>
    </BlockShell>
  );
}
