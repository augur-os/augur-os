"use client";

import type { FormEvent } from "react";
import {
  FileCheck2,
  FolderPlus,
  Inbox,
  Loader2,
  Mail,
  MailPlus,
  Play,
  RefreshCw,
} from "lucide-react";
import {
  RoutingQueueRow,
  SourceLaneRow,
  UnifiedRunRow,
  VaultCandidateRow,
  VaultTargetRow,
} from "./components";
import { CountTile, FolderPresetButtons, asInboxAction } from "./inbox.helpers";
import { EmailSourceRow, FolderRow } from "./inbox.rows";
import type { BrainInboxState, FolderPreset } from "./inbox.types";
import type { EmailAction, EmailSource, InboxFolder } from "./types";

export function InboxPageHeader({
  onRefresh,
  runStatus,
}: {
  onRefresh: () => void;
  runStatus: BrainInboxState["runStatus"];
}) {
  return (
    <section className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Inbox className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Brain Inbox</h2>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-[var(--text-secondary)]">
          Control source lanes, vault discovery, routing, and intake runs from one inbox.
        </p>
        {runStatus?.message ? (
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            {runStatus.state ? `${runStatus.state}: ` : ""}
            {runStatus.message}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onRefresh}
        className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] sm:w-auto sm:min-w-[120px]"
      >
        <RefreshCw className="size-4" aria-hidden="true" />
        Refresh
      </button>
    </section>
  );
}

export function SourceLanesSection({
  sourceLanes,
}: {
  sourceLanes: BrainInboxState["sourceLanes"];
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Inbox className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Source lanes</h2>
      </div>
      {sourceLanes.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm text-[var(--text-muted)]">
          No source lanes are registered.
        </div>
      ) : (
        sourceLanes.map((lane) => <SourceLaneRow key={lane.id} lane={lane} />)
      )}
    </section>
  );
}

export function VaultTargetsSection({
  discoveredVaults,
  onDiscover,
  onRegister,
  vaultTargets,
}: {
  discoveredVaults: BrainInboxState["discoveredVaults"];
  onDiscover: BrainInboxState["discoverVaults"];
  onRegister: BrainInboxState["registerVault"];
  vaultTargets: BrainInboxState["vaultTargets"];
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <FileCheck2 className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Vault targets</h2>
        </div>
        <button
          type="button"
          onClick={() => onDiscover()}
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          Discover Vaults
        </button>
      </div>
      {vaultTargets.map((target) => <VaultTargetRow key={target.id} target={target} />)}
      {discoveredVaults.map((candidate) => (
        <VaultCandidateRow key={candidate.candidate_id} candidate={candidate} onRegister={onRegister} />
      ))}
    </section>
  );
}

export function RoutingQueueSection({
  onConsume,
  onRoute,
  routingQueue,
}: {
  onConsume: BrainInboxState["consumePacket"];
  onRoute: BrainInboxState["routePacket"];
  routingQueue: BrainInboxState["routingQueue"];
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Play className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Routing queue</h2>
      </div>
      {routingQueue.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm text-[var(--text-muted)]">
          No staged packets need routing.
        </div>
      ) : (
        routingQueue.map((packet) => (
          <RoutingQueueRow
            key={packet.packet_id}
            packet={packet}
            onRoute={onRoute}
            onConsume={onConsume}
          />
        ))
      )}
    </section>
  );
}

export function UnifiedRunsSection({ runs }: { runs: BrainInboxState["latestUnifiedRuns"] }) {
  if (runs.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <FileCheck2 className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Unified runs</h2>
      </div>
      {runs.map((run) => <UnifiedRunRow key={run.id} run={run} />)}
    </section>
  );
}

export function InboxTotalsOrStarter({
  hasInboxActivity,
  hasWatchedFolders,
  onSelectPreset,
  totals,
}: {
  hasInboxActivity: boolean;
  hasWatchedFolders: boolean;
  onSelectPreset: (preset: FolderPreset) => void;
  totals: BrainInboxState["totals"];
}) {
  if (hasWatchedFolders || hasInboxActivity) {
    return (
      <section aria-label="Inbox totals" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <CountTile label="New files to inspect" value={totals.newFiles} />
        <CountTile label="Document candidates" value={totals.documents} />
        <CountTile label="Trash candidates" value={totals.trash} />
        <CountTile label="Failed items" value={totals.failed} />
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Start with a folder you already use.
          </h3>
          <p className="mt-2 max-w-2xl text-sm text-[var(--text-secondary)]">
            Scan previews candidates before anything moves. Consume routes useful files into Augur, and Purge to Trash only moves safe disposable candidates.
          </p>
        </div>
        <FolderPresetButtons onSelect={onSelectPreset} />
      </div>
    </section>
  );
}

export function AddFolderSection({
  actionState,
  folderName,
  folderPath,
  onFolderNameChange,
  onFolderPathChange,
  onSubmit,
}: {
  actionState: BrainInboxState["actionState"];
  folderName: string;
  folderPath: string;
  onFolderNameChange: (value: string) => void;
  onFolderPathChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <form className="grid gap-3 lg:grid-cols-[minmax(140px,220px)_1fr_auto]" onSubmit={onSubmit}>
        <label className="block">
          <span className="text-xs font-medium uppercase text-[var(--text-muted)]">Folder name</span>
          <input
            value={folderName}
            onChange={(event) => onFolderNameChange(event.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
            placeholder="Downloads"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium uppercase text-[var(--text-muted)]">Folder path</span>
          <input
            value={folderPath}
            onChange={(event) => onFolderPathChange(event.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
            placeholder="/Users/me/Downloads"
          />
        </label>
        <button
          type="submit"
          disabled={!folderPath.trim() || actionState?.folderId === "new"}
          className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 self-end rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50 lg:min-w-[132px]"
        >
          {actionState?.folderId === "new" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <FolderPlus className="size-4" aria-hidden="true" />}
          Add Folder
        </button>
      </form>
    </section>
  );
}

export function AddMailDropSection({
  displayName,
  isAddingEmail,
  onDisplayNameChange,
  onPathChange,
  onSubmit,
  path,
}: {
  displayName: string;
  isAddingEmail: boolean;
  onDisplayNameChange: (value: string) => void;
  onPathChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  path: string;
}) {
  return (
    <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Mail className="size-4 text-[var(--text-secondary)]" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Add Mail Drop</h3>
        </div>
        <span className="text-xs text-[var(--text-muted)]">A local folder where saved or agent-exported email files land.</span>
      </div>
      <form
        className="grid gap-3 lg:grid-cols-[minmax(140px,220px)_1fr_auto]"
        onSubmit={onSubmit}
      >
        <label className="block">
          <span className="text-xs font-medium uppercase text-[var(--text-muted)]">Display name</span>
          <input
            value={displayName}
            onChange={(event) => onDisplayNameChange(event.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
            placeholder="Mail Drop"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium uppercase text-[var(--text-muted)]">Mail Drop path</span>
          <input
            value={path}
            onChange={(event) => onPathChange(event.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
            placeholder="~/Documents/Augur/inbox/email"
          />
        </label>
        <button
          type="submit"
          disabled={!displayName.trim() || !path.trim() || isAddingEmail}
          className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 self-end rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50 lg:min-w-[148px]"
        >
          {isAddingEmail ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <MailPlus className="size-4" aria-hidden="true" />}
          Add Mail Drop
        </button>
      </form>
    </section>
  );
}

export function InboxNotice({ notice }: { notice: BrainInboxState["notice"] }) {
  if (!notice) return null;

  return (
    <div
      role={notice.type === "error" ? "alert" : "status"}
      className={`rounded-lg border px-4 py-3 text-sm ${
        notice.type === "error"
          ? "border-[var(--accent-danger)] text-[var(--accent-danger)]"
          : notice.type === "warning"
            ? "border-amber-500/30 text-amber-300"
            : "border-[var(--border-color)] text-[var(--text-secondary)]"
      }`}
    >
      {notice.message}
    </div>
  );
}

export function MailDropSourcesSection({
  actionState,
  emailSources,
  onAction,
}: {
  actionState: BrainInboxState["actionState"];
  emailSources: EmailSource[];
  onAction: BrainInboxState["runEmailAction"];
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Mail className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Mail Drop sources</h2>
      </div>
      {emailSources.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm text-[var(--text-muted)]">
          No Mail Drop source yet. Add a folder above, then save or export email files there; attachments and article links route through the same Brain Inbox pipeline as folders.
        </div>
      ) : (
        emailSources.map((source) => (
          <EmailSourceRow
            key={source.id}
            source={source}
            activeAction={actionState?.folderId === `email:${source.id}` ? (actionState.action as EmailAction) : null}
            onAction={(action) => onAction(source.id, action)}
          />
        ))
      )}
    </section>
  );
}

export function WatchedFoldersSection({
  actionState,
  error,
  folders,
  isInitialLoading,
  onAction,
  onSelectPreset,
  show,
}: {
  actionState: BrainInboxState["actionState"];
  error: string | null;
  folders: InboxFolder[];
  isInitialLoading: boolean;
  onAction: BrainInboxState["runFolderAction"];
  onSelectPreset: (preset: FolderPreset) => void;
  show: boolean;
}) {
  if (!show) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <FileCheck2 className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Watched folders</h2>
      </div>
      {!isInitialLoading && !error && folders.length === 0 ? (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Start with a folder you already use.
              </h3>
              <p className="mt-2 max-w-2xl text-sm text-[var(--text-secondary)]">
                Scan previews candidates before anything moves. Consume routes useful files into Augur, and Purge to Trash only moves safe disposable candidates.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[360px]">
              <FolderPresetButtons onSelect={onSelectPreset} />
            </div>
          </div>
        </div>
      ) : (
        folders.map((folder) => (
          <FolderRow
            key={folder.id}
            folder={folder}
            activeAction={actionState?.folderId === folder.id ? asInboxAction(actionState.action) : null}
            onAction={(action) => onAction(folder.id, action)}
          />
        ))
      )}
    </section>
  );
}
