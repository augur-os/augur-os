'use client';

import { useState } from "react";
import {
  Brain,
  Check,
  ClipboardCheck,
  Inbox,
  RefreshCw,
  X,
} from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

type Candidate = {
  id: string;
  source: string;
  client: string;
  kind: string;
  name: string;
  description: string;
  body: string;
  target_filename: string;
  origin: string;
  created: string;
  status: string;
};

type ReviewQueue = {
  success: boolean;
  generated_at: string;
  brain: { id: string; type: string; reason: string; mode: string };
  writable: boolean;
  entries_dir: string;
  counts: { pending: number; promoted: number; rejected: number };
  pending: Candidate[];
};

const KIND_STYLES: Record<string, string> = {
  feedback: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  preference: "border-pink-500/30 bg-pink-500/10 text-pink-300",
  project: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
  reference: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  insight: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  decision: "border-blue-500/30 bg-blue-500/10 text-blue-300",
};

function KindBadge({ kind }: { kind: string }) {
  const cls = KIND_STYLES[kind] ?? "border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-muted)]";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${cls}`}>
      {kind}
    </span>
  );
}

function CountPill({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${tone}`}>
      <span className="font-semibold">{value}</span> <span className="opacity-80">{label}</span>
    </div>
  );
}

function CandidateCard({
  candidate,
  busy,
  onApprove,
  onReject,
}: {
  candidate: Candidate;
  busy: boolean;
  onApprove: (c: Candidate) => void;
  onReject: (c: Candidate) => void;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <KindBadge kind={candidate.kind} />
        <span className="rounded-full border border-[var(--border-color)] bg-[var(--bg-card)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-muted)]">
          {candidate.client}
        </span>
      </div>
      <h4 className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{candidate.name}</h4>
      {candidate.description && (
        <p className="mt-1 text-xs text-[var(--text-secondary)]">{candidate.description}</p>
      )}
      {candidate.body && (
        <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-xs text-[var(--text-muted)]">
          {candidate.body}
        </p>
      )}
      <p className="mt-2 break-words font-mono text-[11px] text-[var(--text-muted)]">
        → {candidate.target_filename}
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => onApprove(candidate)}
          disabled={busy}
          className="inline-flex min-h-[40px] flex-1 items-center justify-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check className="size-4" aria-hidden="true" />
          Approve
        </button>
        <button
          type="button"
          onClick={() => onReject(candidate)}
          disabled={busy}
          className="inline-flex min-h-[40px] items-center justify-center gap-1.5 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--accent-danger)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <X className="size-4" aria-hidden="true" />
          Reject
        </button>
      </div>
    </div>
  );
}

export default function MemoryReviewPage() {
  const { data, loading, error, refetch } = useMcpQuery<ReviewQueue>(
    ["memory-review-queue"],
    "memory-review-queue",
    "user-data",
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const act = async (
    candidate: Candidate,
    tool: "memory-review-approve" | "memory-review-reject",
  ) => {
    setBusyId(candidate.id);
    setActionError(null);
    setNotice(null);
    try {
      const res = await mcpCall<{ success: boolean; path?: string; error?: string }>(tool, {
        candidate_id: candidate.id,
      });
      if (!res?.success) {
        throw new Error(res?.error || "Action failed");
      }
      setNotice(
        tool === "memory-review-approve"
          ? `Approved "${candidate.name}" → ${res.path ?? "brain memory"}`
          : `Rejected "${candidate.name}"`,
      );
      await refetch();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  };

  const header = (
    <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex items-start gap-3">
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-3">
          <ClipboardCheck className="size-5 text-emerald-400" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Memory Review</h2>
          <p className="mt-1 max-w-2xl text-sm text-[var(--text-muted)]">
            Client-native memory is input, not canonical state. Approve a candidate to write it as a
            reviewed memory entry in your brain; reject to dismiss it for good.
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => refetch()}
        disabled={loading || busyId !== null}
        className="inline-flex min-h-[44px] items-center gap-2 self-start rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
        Refresh
      </button>
    </header>
  );

  if (loading) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        {header}
        <p className="text-sm text-[var(--text-muted)]">Loading review queue…</p>
      </div>
    );
  }

  if (error || !data?.success) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        {header}
        <p role="alert" className="text-sm text-[var(--accent-danger)]">
          The memory review queue could not be loaded.
        </p>
      </div>
    );
  }

  const pending = data.pending ?? [];

  return (
    <div className="space-y-6 p-4 md:p-6">
      {header}

      {(actionError || notice) && (
        <div
          role={actionError ? "alert" : "status"}
          className={`rounded-lg border p-3 text-sm ${
            actionError
              ? "border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10 text-[var(--accent-danger)]"
              : "border-[var(--accent-success)]/30 bg-[var(--accent-success)]/10 text-[var(--accent-success)]"
          }`}
        >
          {actionError ?? notice}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)]">
          <Brain className="size-4 text-emerald-400" aria-hidden="true" />
          Target brain: <span className="font-semibold text-[var(--text-primary)]">{data.brain.id}</span>
        </span>
        <CountPill
          label="pending"
          value={data.counts.pending}
          tone="border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
        />
        <CountPill
          label="promoted"
          value={data.counts.promoted}
          tone="border-[var(--accent-success)]/30 bg-[var(--accent-success)]/10 text-[var(--accent-success)]"
        />
        <CountPill
          label="rejected"
          value={data.counts.rejected}
          tone="border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-muted)]"
        />
      </div>

      {!data.writable && (
        <p role="alert" className="rounded-lg border border-[var(--accent-warning)]/30 bg-[var(--accent-warning)]/10 p-3 text-sm text-[var(--accent-warning)]">
          This brain uses packet-based writes: memory review cannot write directly here.
        </p>
      )}

      {pending.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-10 text-center">
          <Inbox className="size-8 text-[var(--text-muted)]" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--text-primary)]">No candidates awaiting review</p>
          <p className="max-w-md text-xs text-[var(--text-muted)]">
            New client-native memory facts and agent-submitted observations appear here for approval.
            {data.counts.promoted > 0 && ` ${data.counts.promoted} entries are already in your brain.`}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {pending.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              busy={busyId !== null}
              onApprove={(c) => act(c, "memory-review-approve")}
              onReject={(c) => act(c, "memory-review-reject")}
            />
          ))}
        </div>
      )}

      <p className="text-xs text-[var(--text-muted)]">
        Approved entries are written to{" "}
        <span className="font-mono">{data.entries_dir}</span>. Snapshot{" "}
        {data.generated_at.slice(0, 19).replace("T", " ")} UTC.
      </p>
    </div>
  );
}
