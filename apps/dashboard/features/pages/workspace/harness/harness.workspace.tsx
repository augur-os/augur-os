'use client';

import { Activity, AlertTriangle, FileText, RefreshCw, Search, Wrench } from "lucide-react";
import type { BrainHarnessController } from "./harness.controller";
import { summarizeDiagnostics } from "./harness.helpers";
import type { Capability, Diagnostic, HarnessSnapshot } from "./harness.types";

export function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

export function ReadinessSection({
  controller,
  snapshot,
}: {
  controller: BrainHarnessController;
  snapshot: HarnessSnapshot;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <Activity className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Harness readiness</h2>
        <span className="rounded-full border border-[var(--border-color)] bg-[var(--bg-card)] px-2 py-1 text-xs font-medium text-[var(--text-muted)]">
          Developer diagnostic
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Capabilities" value={`${controller.mappedCount} mapped`} />
        <StatCard label="Diagnostics" value={`${snapshot.diagnostics.length}`} />
        <StatCard label="Skills" value={`${snapshot.provenance.source_counts?.skills ?? 0}`} />
        <StatCard label="Generated" value={snapshot.generated_at.slice(0, 10)} />
      </div>
    </section>
  );
}

export function HarnessWorkspace({
  controller,
  snapshot,
}: {
  controller: BrainHarnessController;
  snapshot: HarnessSnapshot;
}) {
  return (
    <section className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
      <div className="space-y-3">
        <HarnessActions controller={controller} />
        <BlockersCard controller={controller} snapshot={snapshot} />
        <DiagnosticsCard diagnostics={snapshot.diagnostics} />
      </div>
      <CapabilityMap controller={controller} snapshot={snapshot} />
    </section>
  );
}

function HarnessActions({ controller }: { controller: BrainHarnessController }) {
  return (
    <>
      <button
        type="button"
        onClick={controller.handleRefresh}
        disabled={controller.isRefreshing}
        className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw className="size-4" aria-hidden="true" />
        Refresh snapshot
      </button>
      <button
        type="button"
        onClick={controller.handleRepair}
        disabled={controller.isExecuting || controller.isRefreshing}
        className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Wrench className="size-4" aria-hidden="true" />
        Ask IDE agent to repair
      </button>
      {controller.refreshError && <p role="alert" className="mt-2 text-sm text-[var(--accent-danger)]">{controller.refreshError}</p>}
    </>
  );
}

function BlockersCard({
  controller,
  snapshot,
}: {
  controller: BrainHarnessController;
  snapshot: HarnessSnapshot;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle className="size-5 text-[var(--accent-warning)]" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Blockers</h2>
      </div>
      <p className="text-sm font-medium text-[var(--text-primary)]">
        {summarizeDiagnostics(snapshot.diagnostics)}
      </p>
      <div className="mt-3">
        <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">Affected capabilities</p>
        {controller.affectedCapabilities.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {controller.affectedCapabilities.map((label) => (
              <span key={label} className="rounded-full border border-[var(--border-color)] bg-[var(--bg-card)] px-2 py-1 text-xs text-[var(--text-secondary)]">
                {label}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-[var(--text-secondary)]">No affected capabilities reported.</p>
        )}
      </div>
    </div>
  );
}

function DiagnosticsCard({ diagnostics }: { diagnostics: Diagnostic[] }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle className="size-5 text-[var(--accent-warning)]" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Diagnostics</h2>
      </div>
      {diagnostics.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">No diagnostics reported.</p>
      ) : (
        <div className="space-y-2">
          {diagnostics.map((diagnostic) => (
            <div key={diagnostic.id} className="border-b border-[var(--border-color)] py-2 last:border-b-0">
              <p className="text-sm text-[var(--text-primary)]">{diagnostic.reason}</p>
              <p className="mt-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">Repair action</p>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">{diagnostic.recommended_action.label}</p>
              <p className="mt-1 break-words text-xs text-[var(--text-muted)]">{diagnostic.source_path}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CapabilityMap({
  controller,
  snapshot,
}: {
  controller: BrainHarnessController;
  snapshot: HarnessSnapshot;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Capability map</h2>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {controller.visibleCapabilities.length} of {snapshot.capabilities.length} capabilities shown
          </p>
        </div>
        <CapabilitySearch controller={controller} />
      </div>
      <CapabilityTypeFilter controller={controller} snapshot={snapshot} />
      <ul className="max-h-[36rem] space-y-2 overflow-y-auto pr-1">
        {controller.visibleCapabilities.map((item) => (
          <CapabilityItem key={item.id} item={item} />
        ))}
      </ul>
      {controller.hiddenCapabilityCount > 0 && (
        <p className="mt-3 rounded-lg border border-dashed border-[var(--border-color)] p-4 text-sm text-[var(--text-secondary)]">
          Use search or a type filter to inspect the remaining {controller.hiddenCapabilityCount} capabilities.
        </p>
      )}
      {controller.filteredCapabilities.length === 0 && (
        <p className="rounded-lg border border-dashed border-[var(--border-color)] p-4 text-sm text-[var(--text-secondary)]">
          No capabilities match the current filters.
        </p>
      )}
    </div>
  );
}

function CapabilitySearch({ controller }: { controller: BrainHarnessController }) {
  return (
    <div className="relative sm:w-72">
      <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden="true" />
      <input
        aria-label="Search capabilities"
        value={controller.capabilityQuery}
        onChange={(event) => controller.setCapabilityQuery(event.target.value)}
        placeholder="Search capabilities"
        className="min-h-[44px] w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] py-2 pl-9 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]"
      />
    </div>
  );
}

function CapabilityTypeFilter({
  controller,
  snapshot,
}: {
  controller: BrainHarnessController;
  snapshot: HarnessSnapshot;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => controller.setCapabilityType("all")}
        aria-label="Show all capability types"
        aria-pressed={controller.capabilityType === "all"}
        className={`min-h-[44px] rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
          controller.capabilityType === "all"
            ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/15 text-[var(--text-primary)]"
            : "border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        }`}
      >
        All <span aria-hidden="true">{snapshot.capabilities.length}</span>
      </button>
      {controller.capabilityTypes.map(({ type, count }) => (
        <button
          key={type}
          type="button"
          onClick={() => controller.setCapabilityType(type)}
          aria-label={`Filter capabilities by type ${type}`}
          aria-pressed={controller.capabilityType === type}
          className={`min-h-[44px] rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
            controller.capabilityType === type
              ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/15 text-[var(--text-primary)]"
              : "border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          {type} <span aria-hidden="true">{count}</span>
        </button>
      ))}
    </div>
  );
}

function CapabilityItem({ item }: { item: Capability }) {
  return (
    <li className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-[var(--border-color)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-muted)]">
          {item.type}
        </span>
        <span className="font-medium text-[var(--text-primary)]">{item.label}</span>
      </div>
      {item.summary && <p className="mt-2 text-sm text-[var(--text-secondary)]">{item.summary}</p>}
      <p className="mt-1 break-words text-xs text-[var(--text-muted)]">{item.source_path}</p>
    </li>
  );
}

export function ProvenanceDetails({ provenance }: { provenance: HarnessSnapshot["provenance"] }) {
  return (
    <details className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <FileText className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
        Provenance
      </summary>
      <pre className="mt-3 max-h-80 overflow-auto text-xs text-[var(--text-muted)]">
        {JSON.stringify(provenance, null, 2)}
      </pre>
    </details>
  );
}
