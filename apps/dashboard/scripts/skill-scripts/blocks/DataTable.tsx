'use client';

import { useState } from 'react';
import { GlassCard } from '@/components/ui/GlassCard';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { keyedRenderItems } from '@/lib/stable-render-key';

interface Column {
  field: string;
  label: string;
}

interface DataTableProps {
  columns?: Column[];
  data?: Record<string, unknown>[];
  /** @deprecated Use `tool` instead */
  apiUrl?: string;
  tool?: string;
  toolArgs?: Record<string, unknown>;
}

type SortDirection = 'asc' | 'desc' | null;

export default function DataTable({ columns = [], data: propData = [], tool, toolArgs }: DataTableProps) {
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>(null);

  const { data: fetchedRows, loading, error } = useMcpQuery<Record<string, unknown>[]>(
    ['data-table', tool ?? ''],
    tool ?? '',
    'live',
    {
      enabled: !!tool,
      args: toolArgs,
      select: (raw: unknown) => {
        const json = raw as Record<string, unknown>;
        return Array.isArray(json) ? json : (json.data ?? json.items ?? []) as Record<string, unknown>[];
      },
    },
  );

  const rows = tool ? (fetchedRows ?? []) : propData;

  function handleSort(field: string) {
    if (sortField === field) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : prev === 'desc' ? null : 'asc'));
      if (sortDir === 'desc') setSortField(null);
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  }

  const sortedRows = [...rows].sort((a, b) => {
    if (!sortField || !sortDir) return 0;
    const av = a[sortField] ?? '';
    const bv = b[sortField] ?? '';
    const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const derivedColumns: Column[] =
    columns.length > 0
      ? columns
      : rows.length > 0
        ? Object.keys(rows[0]).map((k) => ({ field: k, label: k }))
        : [];

  return (
    <GlassCard className="p-4 overflow-hidden">
      {loading && (
        <div className="text-sm py-6 text-center" style={{ color: 'var(--text-muted)' }}>
          Loading…
        </div>
      )}
      {error && (
        <div className="text-sm py-4 text-center text-red-400">Error: {error}</div>
      )}
      {!loading && !error && (
        <section className="overflow-x-auto" aria-label="Data table">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr>
                {derivedColumns.map((col) => (
                  <th
                    key={col.field}
                    onClick={() => handleSort(col.field)}
                    aria-sort={sortField === col.field ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    aria-label={`Sort by ${col.label}`}
                    className="px-3 py-2 text-left font-medium cursor-pointer select-none whitespace-nowrap"
                    style={{
                      color: 'var(--text-secondary)',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    {col.label}
                    {sortField === col.field && (
                      <span className="ml-1 text-xs">{sortDir === 'asc' ? '↑' : '↓'}</span>
                    )}
                    {sortField !== col.field && (
                      <span className="ml-1 text-xs opacity-30">⇅</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedRows.length === 0 ? (
                <tr>
                  <td
                    colSpan={derivedColumns.length || 1}
                    className="px-3 py-6 text-center"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    No data
                  </td>
                </tr>
              ) : (
                keyedRenderItems(sortedRows).map(({ item: row, key }) => (
                  <tr
                    key={key}
                    className="transition-colors hover:bg-white/5"
                    style={{ borderBottom: '1px solid var(--border-color)' }}
                  >
                    {derivedColumns.map((col) => (
                      <td
                        key={col.field}
                        className="px-3 py-2"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        {String(row[col.field] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      )}
    </GlassCard>
  );
}
