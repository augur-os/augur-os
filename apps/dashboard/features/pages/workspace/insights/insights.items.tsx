"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Copy,
  Inbox,
  Search,
  Sparkles,
} from "lucide-react";
import {
  compactText,
  formatNumber,
  formatWhen,
  impactLabel,
  sourceLabel,
} from "./insights.helpers";
import type { AskCluster, AskOutcome, BrainInsight, BrainInsightsRun } from "./types";

const HEALTHY_WIKI_ACTIONS = [
  {
    href: "/browse?category=wiki",
    label: "Open Wiki Browse",
    detail: "Read the compiled concept pages.",
    icon: Sparkles,
  },
  {
    href: "/workspace/inbox",
    label: "Scan Brain Inbox",
    detail: "Bring in new files when you are ready.",
    icon: Inbox,
  },
  {
    href: "/browse?view=profile",
    label: "Search memory in Browse",
    detail: "Browse indexed memory entries.",
    icon: Search,
  },
];

export function EmptyState({ children }: { children: string }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm text-[var(--text-secondary)]">
      {children}
    </div>
  );
}

export function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
      <div className="text-xs font-medium uppercase text-[var(--text-muted)]">{label}</div>
      <div className="mt-2 text-xl font-semibold text-[var(--text-primary)]">{value}</div>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">{detail}</p>
    </div>
  );
}

export function InsightItem({
  insight,
  run,
  isNew,
  impact,
}: {
  insight: BrainInsight;
  run: BrainInsightsRun;
  isNew: boolean;
  impact: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [clipboardAvailable, setClipboardAvailable] = useState(false);
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setClipboardAvailable(Boolean(navigator.clipboard));
    }, 0);

    return () => window.clearTimeout(timeout);
  }, []);
  const sources = insight.sources ?? [];
  const summary = insight.summary || "";
  const isLong = summary.length > 360;
  const visibleSummary = expanded || !isLong ? summary : compactText(summary, 340);

  const copySummary = async () => {
    if (!summary || typeof navigator === "undefined" || !navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(summary);
    setCopied(true);
  };

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <h3 className="text-base font-semibold text-[var(--text-primary)]">{insight.title}</h3>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          {isNew && (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">
              New since last visit
            </span>
          )}
          <span className="rounded-full border border-[var(--border-color)] px-2 py-1 text-xs text-[var(--text-muted)]">
            {impactLabel(impact)}
          </span>
          <span className="rounded-full border border-[var(--border-color)] px-2 py-1 text-xs text-[var(--text-muted)]">
            {run.status || "run"} - {formatWhen(run.started_at || run.created_at)}
          </span>
        </div>
      </div>
      {summary && <p className="mt-2 text-sm text-[var(--text-secondary)]">{visibleSummary}</p>}
      {summary && (
        <div className="mt-3 flex flex-wrap gap-2">
          {isLong && (
            <button
              type="button"
              onClick={() => setExpanded((current) => !current)}
              className="inline-flex min-h-[44px] items-center rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {expanded ? "Hide full insight" : "Show full insight"}
            </button>
          )}
          {clipboardAvailable && (
            <button
              type="button"
              onClick={() => void copySummary()}
              className="inline-flex min-h-[44px] items-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              <Copy className="size-4" aria-hidden="true" />
              {copied ? "Copied insight summary" : "Copy insight summary"}
            </button>
          )}
        </div>
      )}
      {sources.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-medium uppercase text-[var(--text-muted)]">Sources</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {sources.slice(0, 6).map((source) => (
              <span
                key={sourceLabel(source)}
                className="max-w-full truncate rounded-full border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1 text-xs text-[var(--text-secondary)]"
                title={sourceLabel(source)}
              >
                {sourceLabel(source)}
              </span>
            ))}
          </div>
        </div>
      )}
      {insight.next_actions && insight.next_actions.length > 0 && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium uppercase text-[var(--text-muted)]">
            <CheckCircle2 className="size-4" aria-hidden="true" />
            Next actions
          </div>
          <ul className="space-y-2">
            {insight.next_actions.map((action) => (
              <li key={action} className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text-primary)]">
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

export function RunSummary({ run }: { run: BrainInsightsRun }) {
  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--text-primary)]">{run.id}</h3>
          <p className="mt-1 text-xs text-[var(--text-muted)]">{formatWhen(run.started_at || run.created_at)}</p>
        </div>
        <span className="rounded-full border border-[var(--border-color)] px-2 py-1 text-xs text-[var(--text-secondary)]">
          {run.status || "unknown"}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-[var(--text-secondary)] sm:grid-cols-2">
        <span>{formatNumber(run.files_seen)} seen</span>
        <span>{formatNumber(run.files_moved)} moved</span>
        <span>{formatNumber(run.files_indexed)} indexed</span>
        <span>{formatNumber(run.files_failed)} failed</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
        {run.airplane_mode && <span>Airplane mode</span>}
        <span>Cloud calls: {run.cloud_calls ?? 0}</span>
        <span>Local agent calls: {run.local_agent_calls ?? 0}</span>
        <span>Needs review: {run.files_needing_review ?? 0}</span>
      </div>
    </article>
  );
}

export function AskOutcomeItem({ outcome }: { outcome: AskOutcome }) {
  const [expanded, setExpanded] = useState(false);
  const summary = outcome.summary || "No summary was returned for this retained outcome.";
  const isLong = summary.length > 320;
  const visibleSummary = expanded || !isLong ? summary : compactText(summary);

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{outcome.question || "Retained ask outcome"}</h3>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">{visibleSummary}</p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="mt-3 inline-flex min-h-[44px] items-center rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
        >
          {expanded ? "Hide full outcome" : "Show full outcome"}
        </button>
      )}
    </article>
  );
}

export function AskClusterItem({ cluster }: { cluster: AskCluster }) {
  const [expanded, setExpanded] = useState(false);
  const summary = cluster.summary || "No cluster summary was returned.";
  const isLong = summary.length > 260;
  const visibleSummary = expanded || !isLong ? summary : compactText(summary, 240);

  return (
    <article className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{cluster.label || cluster.id || "Ask cluster"}</h3>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">{visibleSummary}</p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="mt-3 inline-flex min-h-[44px] items-center rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
        >
          {expanded ? "Hide full cluster" : "Show full cluster"}
        </button>
      )}
    </article>
  );
}

export function HealthyWikiActions() {
  return (
    <div className="mt-4 space-y-3">
      <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] p-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <CheckCircle2 className="size-4 text-[var(--accent-success)]" aria-hidden="true" />
          Wiki is current
        </div>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Compiler sources are current. Use the wiki, scan a watched folder, or search before starting another maintenance run.
        </p>
      </div>
      <div className="grid gap-2">
        {HEALTHY_WIKI_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <Link
              key={action.href}
              href={action.href}
              className="group flex min-h-[56px] items-center justify-between gap-3 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              <span className="flex min-w-0 items-center gap-3">
                <Icon className="size-4 shrink-0 text-[var(--text-secondary)]" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block font-medium text-[var(--text-primary)]">{action.label}</span>
                  <span className="mt-0.5 block text-xs text-[var(--text-muted)]">{action.detail}</span>
                </span>
              </span>
              <ArrowRight className="size-4 shrink-0 text-[var(--text-muted)] transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}
