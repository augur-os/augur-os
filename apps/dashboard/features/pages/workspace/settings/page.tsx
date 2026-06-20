'use client';

import { useState } from "react";
import {
  AlertTriangle,
  Brain,
  Check,
  Circle,
  Database,
  FolderGit2,
  GitBranch,
  Plus,
  RefreshCw,
} from "lucide-react";
import { mcpCall } from "@/lib/mcp/client";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

type BrainGit = {
  arrangement: string;
  branch: string;
  remote: string | null;
  host_repo: string | null;
  tracked: boolean;
  dirty: boolean | null;
  uncommitted: number | null;
};

type BrainIndex = {
  exists: boolean;
  memory_entries: number;
  notes: number;
  sources: number;
  wiki_pages: number;
  total_records: number;
  populated: boolean;
};

type BrainEntry = {
  id: string;
  type: string;
  root: string;
  description: string | null;
  is_active: boolean;
  exists: boolean;
  write_policy: string;
  git: BrainGit;
  index: BrainIndex;
};

type DetectedBrain = {
  id: string;
  type: string;
  root: string;
  attached_project: string | null;
  description: string | null;
  registered: boolean;
};

type CurrentProject = {
  root: string;
  name: string;
  project_brain_root: string;
  has_project_brain: boolean;
  registered_brain_id: string | null;
  registered: boolean;
  can_init: boolean;
};

type ClientProjection = {
  status: string;
  synced_skills: string[];
  last_sync: string | null;
  issues: string[];
};

type DiscoverySnapshot = {
  success: boolean;
  generated_at: string;
  active: { brain_id: string; type: string; root: string; source: string; attached_project: string | null } | null;
  current_project: CurrentProject;
  brains: BrainEntry[];
  detected_project_brains: DetectedBrain[];
  projections: { project_root?: string; clients?: Record<string, ClientProjection> };
};

const TYPE_STYLES: Record<string, string> = {
  personal: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  team: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  project: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
};

function TypeBadge({ type }: { type: string }) {
  const cls = TYPE_STYLES[type] ?? "border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-muted)]";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${cls}`}>
      {type}
    </span>
  );
}

function projectionTone(status: string): string {
  if (status === "healthy") return "border-[var(--accent-success)]/30 bg-[var(--accent-success)]/10 text-[var(--accent-success)]";
  if (status === "issues") return "border-[var(--accent-warning)]/30 bg-[var(--accent-warning)]/10 text-[var(--accent-warning)]";
  if (status === "not_installed") return "border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-muted)]";
  return "border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)]";
}

function GitLine({ git }: { git: BrainGit }) {
  const dirtyLabel =
    git.dirty === null
      ? "status unknown"
      : git.dirty
        ? `${git.uncommitted ?? 0} uncommitted`
        : "clean";
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--text-muted)]">
      <span className="inline-flex items-center gap-1">
        <GitBranch className="size-3.5" aria-hidden="true" />
        {git.arrangement}
        {git.branch ? ` · ${git.branch}` : ""}
      </span>
      <span
        className={
          git.dirty
            ? "text-[var(--accent-warning)]"
            : git.dirty === false
              ? "text-[var(--accent-success)]"
              : "text-[var(--text-muted)]"
        }
      >
        {dirtyLabel}
      </span>
      {git.remote && <span className="truncate">{git.remote}</span>}
    </div>
  );
}

function IndexLine({ index }: { index: BrainIndex }) {
  if (!index.populated) {
    return <p className="text-xs text-[var(--text-muted)]">No indexed records yet.</p>;
  }
  const parts = [
    index.notes ? `${index.notes} notes` : null,
    index.memory_entries ? `${index.memory_entries} memory` : null,
    index.wiki_pages ? `${index.wiki_pages} wiki` : null,
    index.sources ? `${index.sources} sources` : null,
  ].filter(Boolean);
  return (
    <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
      <Database className="size-3.5 text-[var(--text-muted)]" aria-hidden="true" />
      <span>
        {index.total_records} records
        {parts.length ? ` · ${parts.join(" · ")}` : ""}
      </span>
    </div>
  );
}

function BrainCard({ brain }: { brain: BrainEntry }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-[var(--text-primary)]">{brain.id}</span>
        <TypeBadge type={brain.type} />
        {brain.is_active && (
          <span className="inline-flex items-center gap-1 rounded-full border border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/10 px-2 py-0.5 text-[11px] font-semibold text-[var(--accent-primary)]">
            <Circle className="size-2 fill-current" aria-hidden="true" />
            Active
          </span>
        )}
        {!brain.exists && (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--accent-danger)]">
            <AlertTriangle className="size-3" aria-hidden="true" />
            Root missing
          </span>
        )}
      </div>
      {brain.description && (
        <p className="mt-1 text-xs text-[var(--text-secondary)]">{brain.description}</p>
      )}
      <p className="mt-2 break-words font-mono text-xs text-[var(--text-muted)]">{brain.root}</p>
      <div className="mt-3 space-y-2">
        <GitLine git={brain.git} />
        <IndexLine index={brain.index} />
      </div>
    </div>
  );
}

export default function BrainSettingsPage() {
  const { data, loading, error, refetch } = useMcpQuery<DiscoverySnapshot>(
    ["brain-discovery"],
    "brain-discovery",
    "config",
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const runInit = async (projectRoot?: string) => {
    setBusy(true);
    setActionError(null);
    setNotice(null);
    try {
      const res = await mcpCall<{ success: boolean; brain_id?: string; error?: string }>(
        "brain-init",
        projectRoot ? { project_root: projectRoot } : {},
      );
      if (!res?.success) {
        throw new Error(res?.error || "Initialization failed");
      }
      setNotice(`Project brain "${res.brain_id}" initialized and registered.`);
      await refetch();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Initialization failed");
    } finally {
      setBusy(false);
    }
  };

  const header = (
    <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex items-start gap-3">
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-3">
          <Brain className="size-5 text-emerald-400" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Brains</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Registered and detected brains, their content, git state, and AI-client projections.
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => refetch()}
        disabled={loading || busy}
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
        <p className="text-sm text-[var(--text-muted)]">Loading brain discovery…</p>
      </div>
    );
  }

  if (error || !data?.success) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        {header}
        <p role="alert" className="text-sm text-[var(--accent-danger)]">
          Brain discovery could not be loaded.
        </p>
      </div>
    );
  }

  const project = data.current_project;
  const detected = data.detected_project_brains ?? [];
  const unregisteredDetected = detected.filter((d) => !d.registered);
  const clients = Object.entries(data.projections?.clients ?? {});

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

      {/* Current project */}
      <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
        <div className="flex items-start gap-3">
          <FolderGit2 className="mt-0.5 size-5 text-[var(--text-secondary)]" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold text-[var(--text-primary)]">Current project</h3>
            <p className="mt-0.5 break-words font-mono text-xs text-[var(--text-muted)]">{project.root}</p>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              {project.registered ? (
                <span className="inline-flex items-center gap-1.5 text-[var(--accent-success)]">
                  <Check className="size-4" aria-hidden="true" />
                  Registered as <span className="font-semibold">{project.registered_brain_id}</span>
                </span>
              ) : project.has_project_brain ? (
                "A project-brain exists here but is not registered in this machine's registry."
              ) : (
                "This project has no project brain yet."
              )}
            </p>
            {project.can_init && (
              <button
                type="button"
                onClick={() => runInit()}
                disabled={busy}
                className="mt-3 inline-flex min-h-[44px] items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="size-4" aria-hidden="true" />
                {busy ? "Running augur init…" : "Run augur init"}
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Registered brains */}
      <section>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          Registered brains ({data.brains.length})
        </h3>
        {data.brains.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No brains registered.</p>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {data.brains.map((brain) => (
              <BrainCard key={brain.id} brain={brain} />
            ))}
          </div>
        )}
      </section>

      {/* Detected, unregistered project brains */}
      {unregisteredDetected.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            Detected project brains (unregistered)
          </h3>
          <div className="space-y-3">
            {unregisteredDetected.map((d) => (
              <div
                key={d.root}
                className="flex flex-col gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[var(--text-primary)]">{d.id}</span>
                    <TypeBadge type={d.type} />
                  </div>
                  <p className="mt-1 break-words font-mono text-xs text-[var(--text-muted)]">{d.root}</p>
                </div>
                {d.attached_project && (
                  <button
                    type="button"
                    onClick={() => runInit(d.attached_project ?? undefined)}
                    disabled={busy}
                    className="inline-flex min-h-[44px] items-center gap-2 self-start rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-400 transition-colors hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Plus className="size-4" aria-hidden="true" />
                    Register
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Client projections */}
      <section>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          AI-client projections
        </h3>
        {clients.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Projection status is unavailable in this runtime.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {clients.map(([client, info]) => (
              <div key={client} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-[var(--text-primary)]">{client}</span>
                  <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${projectionTone(info.status)}`}>
                    {info.status.replace("_", " ")}
                  </span>
                </div>
                <p className="mt-2 text-xs text-[var(--text-muted)]">
                  {info.synced_skills.length} skill{info.synced_skills.length === 1 ? "" : "s"} synced
                </p>
                {info.last_sync && (
                  <p className="mt-1 text-xs text-[var(--text-muted)]">Last sync {info.last_sync.slice(0, 10)}</p>
                )}
                {info.issues.length > 0 && (
                  <p className="mt-1 text-xs text-[var(--accent-warning)]">{info.issues.length} issue(s)</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="text-xs text-[var(--text-muted)]">
        Snapshot generated {data.generated_at.slice(0, 19).replace("T", " ")} UTC
      </p>
    </div>
  );
}
