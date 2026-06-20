'use client';

import { ArrowDownToLine, ArrowUpRight, Layers, RefreshCw } from "lucide-react";
import type { BrainHarnessController } from "./harness.controller";
import type { ManagerRow } from "./harness.types";

export function ManagerSection({ controller }: { controller: BrainHarnessController }) {
  return (
    <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Harness manager</h2>
          </div>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            {controller.managerSnapshot
              ? `${controller.managerTotals.effective} effective rows, ${controller.managerTotals.shadowed} shadowed overrides`
              : "Tiered snapshot unavailable"}
          </p>
        </div>
        <ManagerTierFilter controller={controller} />
      </div>
      {controller.managerLoading && <p className="text-sm text-[var(--text-muted)]">Loading harness manager…</p>}
      {controller.managerError && <p role="alert" className="text-sm text-[var(--accent-danger)]">Harness manager snapshot could not be loaded.</p>}
      {controller.managerActionError && <p role="alert" className="mb-3 text-sm text-[var(--accent-danger)]">{controller.managerActionError}</p>}
      {controller.managerSnapshot && <ManagerGroups controller={controller} />}
    </section>
  );
}

function ManagerTierFilter({ controller }: { controller: BrainHarnessController }) {
  return (
    <fieldset className="m-0 flex min-w-0 flex-wrap gap-2 border-0 p-0">
      <legend className="sr-only">Harness manager tier filter</legend>
      {controller.managerTierOptions.map((tier) => (
        <button
          key={tier.key}
          type="button"
          onClick={() => controller.setManagerTier(tier.key)}
          aria-label={tier.key === "effective" ? "Show effective capabilities" : `Filter manager by ${tier.label} tier`}
          aria-pressed={controller.managerTier === tier.key}
          className={`min-h-[40px] rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
            controller.managerTier === tier.key
              ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/15 text-[var(--text-primary)]"
              : "border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          {tier.label}
        </button>
      ))}
    </fieldset>
  );
}

function ManagerGroups({ controller }: { controller: BrainHarnessController }) {
  if (controller.visibleManagerGroups.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-[var(--border-color)] p-4 text-sm text-[var(--text-secondary)]">
        No manager rows match the selected tier.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {controller.visibleManagerGroups.map(({ key, group, rows }) => (
        <div key={key} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)]">
          <div className="flex items-center justify-between border-b border-[var(--border-color)] px-3 py-2">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{group.label}</h3>
            <span className="text-xs text-[var(--text-muted)]">{rows.length} shown</span>
          </div>
          <ul className="divide-y divide-[var(--border-color)]">
            {rows.map((row) => (
              <ManagerRowItem key={row.id} row={row} controller={controller} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ManagerRowItem({
  row,
  controller,
}: {
  row: ManagerRow;
  controller: BrainHarnessController;
}) {
  return (
    <li className="grid gap-3 p-3 lg:grid-cols-[1fr_11rem_12rem] lg:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-[var(--text-primary)]">{row.name}</span>
          <span className="rounded border border-[var(--border-color)] px-2 py-0.5 text-[11px] text-[var(--text-muted)]">
            {row.owner_label}
          </span>
          <span className="rounded border border-[var(--border-color)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
            {row.winner_tier_label}
          </span>
          {row.shadowed_entries.map((shadow) => (
            <span key={`${row.id}-${shadow.tier}`} className="rounded border border-[var(--accent-warning)]/35 bg-[var(--accent-warning)]/10 px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
              Shadowed by {shadow.tier_label}
            </span>
          ))}
        </div>
        <p className="mt-1 break-words text-xs text-[var(--text-muted)]">{row.winner_path}</p>
      </div>
      <TierBadges row={row} />
      <ManagerRowActions row={row} controller={controller} />
    </li>
  );
}

function TierBadges({ row }: { row: ManagerRow }) {
  return (
    <div className="flex flex-wrap gap-1">
      {row.tiers.map((tier) => (
        <span
          key={`${row.id}-${tier.tier}-${tier.status}`}
          className={`rounded px-2 py-1 text-[11px] ${
            tier.status === "effective"
              ? "bg-[var(--accent-primary)]/15 text-[var(--text-primary)]"
              : "bg-[var(--bg-secondary)] text-[var(--text-muted)]"
          }`}
        >
          {tier.tier_label}
        </span>
      ))}
    </div>
  );
}

function ManagerRowActions({
  row,
  controller,
}: {
  row: ManagerRow;
  controller: BrainHarnessController;
}) {
  return (
    <div className="flex gap-2 lg:justify-end">
      <button
        type="button"
        onClick={() => controller.handleManagerAction(row, "promote")}
        disabled={!row.actions.promote.enabled || controller.managerBusyId === `promote:${row.id}`}
        aria-label={`Promote ${row.name}`}
        className="inline-flex min-h-[40px] items-center gap-2 rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ArrowUpRight className="size-4" aria-hidden="true" />
        Promote
      </button>
      <button
        type="button"
        onClick={() => controller.handleManagerAction(row, "demote")}
        disabled={!row.actions.demote.enabled || controller.managerBusyId === `demote:${row.id}`}
        aria-label={`Demote ${row.name} to Codex`}
        className="inline-flex min-h-[40px] items-center gap-2 rounded-md border border-[var(--border-color)] px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ArrowDownToLine className="size-4" aria-hidden="true" />
        Demote
      </button>
    </div>
  );
}

export function RefreshSnapshotButton({
  controller,
  label,
}: {
  controller: BrainHarnessController;
  label: string;
}) {
  return (
    <>
      <button
        type="button"
        onClick={controller.handleRefresh}
        disabled={controller.isRefreshing}
        className="mt-4 inline-flex min-h-[44px] items-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
      >
        <RefreshCw className="size-4" aria-hidden="true" />
        {label}
      </button>
      {controller.refreshError && <p role="alert" className="mt-3 text-sm text-[var(--accent-danger)]">{controller.refreshError}</p>}
    </>
  );
}
