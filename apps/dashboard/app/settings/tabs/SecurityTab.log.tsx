"use client";

import {
  Shield,
  Download,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SectionTitle } from "./SecurityTab.shared";
import type { AuditLog, SecurityTabController } from "./SecurityTab.controller";

export function AuditLogSection({ controller }: { controller: SecurityTabController }) {
  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <SectionTitle
          icon={Shield}
          title="Audit Log"
          description="Track all security-relevant actions"
          iconClassName="text-[var(--accent-danger)]"
        />
        <div className="flex gap-2">
          <ExportButton
            exporting={controller.exporting}
            label="Export JSON"
            onClick={() => controller.handleExport("json")}
          />
          <ExportButton
            exporting={controller.exporting}
            label="Export CSV"
            onClick={() => controller.handleExport("csv")}
          />
        </div>
      </div>
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl overflow-hidden">
        <AuditFilters controller={controller} />
        <AuditLogsTable
          loading={controller.loading}
          logs={controller.logs}
        />
      </div>
    </section>
  );
}

function ExportButton({
  exporting,
  label,
  onClick,
}: {
  exporting: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      variant="outline"
      onClick={onClick}
      disabled={exporting}
      className="gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {exporting ? (
        <Loader2 className="size-4 animate-spin" />
      ) : (
        <Download className="size-4" />
      )}
      {label}
    </Button>
  );
}

function AuditFilters({ controller }: { controller: SecurityTabController }) {
  return (
    <div className="p-4 bg-[var(--bg-secondary)] border-b border-[var(--border-color)]">
      <div className="flex flex-wrap items-end gap-4">
        <FilterTextInput
          id="audit-filter-action"
          label="Search Action"
          value={controller.filters.action}
          placeholder="e.g., login..."
          ariaLabel="Search action"
          onChange={(action) => controller.updateFilters({ action })}
        />
        <FilterTextInput
          id="audit-filter-user"
          label="User"
          value={controller.filters.user}
          placeholder="User email or ID"
          ariaLabel="Filter by user"
          onChange={(user) => controller.updateFilters({ user })}
        />
        <fieldset>
          <legend className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">
            Time Range
          </legend>
          <div className="flex gap-2">
            <Input
              id="audit-filter-start-date"
              type="date"
              value={controller.filters.start_date}
              onChange={(event) => controller.updateFilters({ start_date: event.target.value })}
              aria-label="Start date"
              className="h-9 w-36"
            />
            <Input
              id="audit-filter-end-date"
              type="date"
              value={controller.filters.end_date}
              onChange={(event) => controller.updateFilters({ end_date: event.target.value })}
              aria-label="End date"
              className="h-9 w-36"
            />
          </div>
        </fieldset>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => controller.loadLogs(controller.filters)}
            className="bg-[var(--accent-primary)] hover:brightness-110 text-[var(--text-on-accent,#fff)]"
          >
            Filter
          </Button>
          <Button variant="ghost" size="sm" onClick={controller.clearFilters}>
            Clear
          </Button>
        </div>
      </div>
    </div>
  );
}

function FilterTextInput({
  id,
  label,
  value,
  placeholder,
  ariaLabel,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  ariaLabel: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex-1 min-w-[200px]">
      <label htmlFor={id} className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">
        {label}
      </label>
      <Input
        id={id}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
        className="h-9"
      />
    </div>
  );
}

function AuditLogsTable({
  loading,
  logs,
}: {
  loading: boolean;
  logs: AuditLog[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="bg-[var(--bg-secondary)] text-[var(--text-muted)] font-medium border-b border-[var(--border-color)]">
          <tr>
            <th scope="col" className="px-4 py-3 w-10">Status</th>
            <th scope="col" className="px-4 py-3">Action</th>
            <th scope="col" className="px-4 py-3">User</th>
            <th scope="col" className="px-4 py-3">Resource</th>
            <th scope="col" className="px-4 py-3 text-right">Timestamp</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-color)]">
          {loading ? (
            <tr>
              <td colSpan={5} className="p-8 text-center">
                <Loader2 className="size-6 animate-spin text-[var(--accent-info)] mx-auto" />
                <p className="text-[var(--text-muted)] mt-2">Loading logs…</p>
              </td>
            </tr>
          ) : logs.length === 0 ? (
            <tr>
              <td colSpan={5} className="p-8 text-center text-[var(--text-muted)]">
                No audit logs found matching criteria.
              </td>
            </tr>
          ) : (
            logs.map((log) => <AuditLogRow key={`${log.timestamp}:${log.action}:${log.resource ?? ""}:${log.user ?? ""}`} log={log} />)
          )}
        </tbody>
      </table>
    </div>
  );
}

function AuditLogRow({ log }: { log: AuditLog }) {
  return (
    <tr className="hover:bg-[var(--bg-hover)] transition-colors duration-200">
      <td className="px-4 py-3">
        {log.success ? (
          <span className="inline-flex items-center">
            <CheckCircle2 className="size-4 text-[var(--accent-success)]" aria-hidden="true" />
            <span className="sr-only">Success</span>
          </span>
        ) : (
          <span className="inline-flex items-center">
            <AlertCircle className="size-4 text-[var(--accent-danger)]" aria-hidden="true" />
            <span className="sr-only">Failed</span>
          </span>
        )}
      </td>
      <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
        {log.action}
      </td>
      <td className="px-4 py-3 text-[var(--text-secondary)]">
        {log.user || "—"}
      </td>
      <td className="px-4 py-3 text-[var(--text-secondary)] max-w-[200px]">
        {log.resource ? (
          <code className="text-xs bg-[var(--bg-secondary)] px-1.5 py-0.5 rounded border border-[var(--border-color)] truncate block max-w-full" title={log.resource}>
            {log.resource}
          </code>
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 py-3 text-right text-[var(--text-muted)] font-mono text-xs">
        {new Date(log.timestamp).toLocaleString()}
      </td>
    </tr>
  );
}
