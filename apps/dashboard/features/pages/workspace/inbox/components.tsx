"use client";

import { Archive, CheckCircle2, Database, GitBranch, Inbox, Route, Server, XCircle } from "lucide-react";
import type {
  InboxRoutingQueueItem,
  InboxSourceLane,
  InboxVaultCandidate,
  InboxVaultTarget,
  UnifiedInboxRun,
} from "./types";

function StatusTag({ value }: { value?: string | null }) {
  if (!value) {
    return null;
  }
  return (
    <span className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
      {value}
    </span>
  );
}

function PathText({ value }: { value: string }) {
  return (
    <p className="mt-1 truncate text-sm text-[var(--text-muted)]" title={value}>
      {value}
    </p>
  );
}

export function InboxHealthStrip({
  sourceCount,
  targetCount,
  candidateCount,
  queuedCount,
}: {
  sourceCount: number;
  targetCount: number;
  candidateCount: number;
  queuedCount: number;
}) {
  const items = [
    { label: "Source lanes", value: sourceCount, icon: Inbox },
    { label: "Vault targets", value: targetCount, icon: Database },
    { label: "Discovered vaults", value: candidateCount, icon: GitBranch },
    { label: "Routing queue", value: queuedCount, icon: Route },
  ];
  return (
    <section aria-label="Unified inbox health" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.label} className="min-h-[76px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-3">
            <div className="flex items-center gap-2 text-xs font-medium uppercase text-[var(--text-muted)]">
              <Icon className="size-4" aria-hidden="true" />
              {item.label}
            </div>
            <div className="mt-1 text-2xl font-semibold text-[var(--text-primary)]">{item.value}</div>
          </div>
        );
      })}
    </section>
  );
}

export function SourceLaneRow({ lane }: { lane: InboxSourceLane }) {
  const healthy = !lane.health_state || lane.health_state === "ready";
  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {healthy ? <CheckCircle2 className="size-4 text-emerald-400" aria-hidden="true" /> : <XCircle className="size-4 text-[var(--accent-danger)]" aria-hidden="true" />}
            <h3 className="text-base font-semibold text-[var(--text-primary)]">{lane.name}</h3>
            <StatusTag value={lane.type} />
            <StatusTag value={lane.health_state} />
          </div>
          <PathText value={lane.drop_root} />
          {lane.health_error && <p className="mt-2 text-xs text-[var(--accent-danger)]">{lane.health_error}</p>}
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-[var(--text-secondary)] lg:justify-end">
          {lane.write_modes.map((mode) => (
            <StatusTag key={mode} value={mode} />
          ))}
        </div>
      </div>
    </article>
  );
}

export function VaultTargetRow({ target }: { target: InboxVaultTarget }) {
  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Server className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
            <h3 className="text-base font-semibold text-[var(--text-primary)]">{target.name}</h3>
            <StatusTag value={target.kind} />
            {target.default && <StatusTag value="default" />}
            <StatusTag value={target.writable ? "writable" : "read-only"} />
          </div>
          <PathText value={target.docs_root} />
          <PathText value={target.vault_root} />
        </div>
      </div>
    </article>
  );
}

export function VaultCandidateRow({
  candidate,
  onRegister,
}: {
  candidate: InboxVaultCandidate;
  onRegister: (candidateId: string) => void;
}) {
  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <GitBranch className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
            <h3 className="text-base font-semibold text-[var(--text-primary)]">{candidate.name}</h3>
            <StatusTag value={candidate.kind} />
            <StatusTag value={candidate.status} />
          </div>
          <PathText value={candidate.docs_root} />
          <p className="mt-1 text-xs text-[var(--text-muted)]">{candidate.reason}</p>
        </div>
        <button
          type="button"
          onClick={() => onRegister(candidate.candidate_id)}
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
        >
          Register {candidate.name}
        </button>
      </div>
    </article>
  );
}

export function RoutingQueueRow({
  packet,
  onRoute,
  onConsume,
}: {
  packet: InboxRoutingQueueItem;
  onRoute: (packetId: string) => void;
  onConsume: (packetId: string) => void;
}) {
  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Route className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
            <h3 className="text-base font-semibold text-[var(--text-primary)]">{packet.title}</h3>
            <StatusTag value={packet.status} />
            <StatusTag value={packet.failure_state} />
          </div>
          <PathText value={packet.packet_dir} />
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[240px]">
          <button
            type="button"
            onClick={() => onRoute(packet.packet_id)}
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            Route {packet.packet_id}
          </button>
          <button
            type="button"
            onClick={() => onConsume(packet.packet_id)}
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            Consume
          </button>
        </div>
      </div>
    </article>
  );
}

export function UnifiedRunRow({ run }: { run: UnifiedInboxRun }) {
  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Archive className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
            <h3 className="truncate text-base font-semibold text-[var(--text-primary)]">{run.id}</h3>
            <StatusTag value={run.status} />
          </div>
          <p className="mt-1 text-sm text-[var(--text-muted)]">{run.source_id}</p>
        </div>
        <div className="flex flex-wrap gap-3 text-sm text-[var(--text-secondary)]">
          <span>{run.moved} moved</span>
          <span>{run.archived} archived</span>
          <span>{run.questions} questions</span>
        </div>
      </div>
    </article>
  );
}
