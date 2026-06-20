"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Terminal,
  Unplug,
  AlertTriangle,
  ExternalLink,
  RefreshCcw,
} from "lucide-react";
import type { SessionConflictInfo } from "@/features/hooks/useCliChat";

export function FloatingChatMinimizedPill({
  onRestore,
  statusColor,
  isRunning,
  statusLabel,
  cliLabel,
}: {
  onRestore: () => void;
  statusColor: string;
  isRunning: boolean;
  statusLabel: string;
  cliLabel: string;
}) {
  return (
    <button type="button"
      onClick={onRestore}
      aria-label="Restore chat window"
      data-testid="minimized-chat-launcher"
      className="fixed bottom-8 right-6 z-50 flex items-center gap-1 rounded-full border border-[var(--border-color)]/70 bg-[var(--bg-primary)]/72 p-1 shadow-xl backdrop-blur-xl transition-all duration-200 hover:-translate-y-0.5 floating-action-bar"
      title={`Restore chat window${cliLabel ? ` (${cliLabel})` : ""}`}
    >
      <div className="flex items-center gap-2 rounded-full px-3 py-1.5">
        <span
          className={`h-2.5 w-2.5 rounded-full ${statusColor} ${isRunning ? "motion-safe:animate-pulse" : ""}`}
          aria-live="polite"
          aria-label={`CLI status: ${statusLabel}`}
        />
        <span className="max-w-[9rem] truncate text-sm font-medium text-[var(--text-primary)]">
          {cliLabel}
        </span>
        <Terminal className="size-3.5 text-[var(--text-muted)]" />
      </div>
    </button>
  );
}

/**
 * ADR-535 0F: Banner shown when detached sessions exist on the server.
 * Appears on dashboard load to let users reconnect.
 */
export function DetachedSessionsBanner({
  onReconnect,
}: {
  onReconnect: (cliId: string) => void;
}) {
  const { data: sessions = [] } = useQuery({
    queryKey: ["chat-detached-sessions"],
    queryFn: async () => {
      const res = await fetch("/api/cli?action=list");
      if (!res.ok) return [];
      const data = await res.json();
      return (data.sessions ?? []).filter(
        (session: { detached: boolean; status: string }) =>
          session.detached || session.status === "detached",
      ) as Array<{ cliId: string; pid: number; uptime: number; detached: boolean }>;
    },
    refetchInterval: 15_000,
  });

  if (sessions.length === 0) return null;

  return (
    <div
      className="flex items-center gap-2 px-3 py-2 bg-blue-500/10 border-b border-blue-500/30 text-xs text-blue-400"
      aria-live="polite"
    >
      <Unplug className="size-3 flex-shrink-0" />
      <span>
        {sessions.length === 1
          ? "1 detached session"
          : `${sessions.length} detached sessions`}{" "}
        running in background.
      </span>
      {sessions.map((s) => (
        <button type="button"
          key={s.cliId}
          onClick={() => onReconnect(s.cliId)}
          className="px-1.5 py-0.5 rounded bg-blue-500/20 hover:bg-blue-500/30 transition-colors font-medium"
        >
          Reconnect {s.cliId}
        </button>
      ))}
    </div>
  );
}

export function ConnectionBanner({
  isOnline,
  isCliStale,
  isRunning,
}: {
  isOnline: boolean;
  isCliStale: boolean;
  isRunning: boolean;
}) {
  if (!isOnline) {
    return (
      <div
        className="flex items-center gap-2 px-3 py-2 bg-orange-500/10 border-b border-orange-500/30 text-xs text-orange-400"
        role="alert"
      >
        <span className="size-2 rounded-full bg-orange-500" />
        <span>
          You are offline. Messages will be sent when connection is restored.
        </span>
      </div>
    );
  }

  if (isCliStale && isRunning) {
    return (
      <div
        className="flex items-center gap-2 px-3 py-2 bg-yellow-500/10 border-b border-yellow-500/30 text-xs text-yellow-400"
        aria-live="polite"
      >
        <span className="size-3 border-2 border-yellow-400 border-t-transparent rounded-full motion-safe:animate-spin" />
        <span>Reconnecting to CLI…</span>
      </div>
    );
  }

  return null;
}

export function SessionConflictBanner({
  conflict,
  onSwitchSessionOwner,
  onTakeOverSessionOwner,
}: {
  conflict: SessionConflictInfo | null | undefined;
  onSwitchSessionOwner?: () => void;
  onTakeOverSessionOwner?: () => void;
}) {
  if (!conflict) {
    return null;
  }

  const owner = conflict.owner ?? {};
  const surface =
    owner.surface === "native-terminal"
      ? "native terminal"
      : owner.surface === "dashboard-pty"
        ? "dashboard chat"
        : "another surface";
  const pid = typeof owner.pid === "number" ? `PID ${owner.pid}` : null;
  const host =
    typeof owner.host === "string" && owner.host.length > 0
      ? owner.host
      : null;
  const meta = [pid, host].filter(Boolean).join(" · ");

  return (
    <div
      className="flex items-center gap-2 border-t border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300"
      aria-live="polite"
      data-testid="session-conflict-banner"
    >
      <AlertTriangle className="size-3.5 shrink-0" />
      <span className="min-w-0 truncate">
        Session is already open in {surface}
        {meta ? ` (${meta})` : ""}.
      </span>
      <div className="ml-auto flex shrink-0 items-center gap-1.5">
        {onSwitchSessionOwner && (
          <button
            type="button"
            onClick={onSwitchSessionOwner}
            className="inline-flex h-7 items-center gap-1 rounded-md border border-amber-500/25 bg-amber-500/10 px-2 font-medium text-amber-800 transition hover:bg-amber-500/18 dark:text-amber-200"
            aria-label="Switch to owning surface"
            title="Switch to owning surface"
          >
            <ExternalLink className="size-3.5" />
            <span>Switch</span>
          </button>
        )}
        {onTakeOverSessionOwner && (
          <button
            type="button"
            onClick={onTakeOverSessionOwner}
            className="inline-flex h-7 items-center gap-1 rounded-md border border-amber-500/35 bg-amber-500/18 px-2 font-medium text-amber-900 transition hover:bg-amber-500/25 dark:text-amber-100"
            aria-label="Take over here"
            title="Take over here"
          >
            <RefreshCcw className="size-3.5" />
            <span>Take over here</span>
          </button>
        )}
      </div>
    </div>
  );
}
