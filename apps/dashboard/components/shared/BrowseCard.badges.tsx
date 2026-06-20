"use client";
// Icon resolution + badge collection/rendering for BrowseCard.
// Imports leaf helpers; never imports from BrowseCard.tsx (no cycle).

import React from "react";
import { Box, Layers } from "lucide-react";
import { resolveIcon as resolveIconFromMap } from "@/lib/icon-map";
import type { LucideIcon } from "lucide-react";
import type { BrowseItem } from "@/lib/browse/types";
import { overlayScope, overlayScopeLabel } from "@/lib/browse/overlay";
import {
  isWikiPageItem,
  itemPageTags,
  positiveCountLabel,
  wikiMaintenanceStateLabel,
  type BadgeEntry,
} from "./BrowseCard.helpers";

/* ------------------------------------------------------------------ */
/*  Icon helpers                                                       */
/* ------------------------------------------------------------------ */

export function resolveIcon(name: string | undefined): LucideIcon {
  return resolveIconFromMap(name, Box);
}

export function ResolvedIcon({ name, className }: { name?: string; className?: string }) {
  return React.createElement(resolveIcon(name), { className });
}

/* ------------------------------------------------------------------ */
/*  Master client badge constants                                      */
/* ------------------------------------------------------------------ */

const CLIENT_BADGE_COLORS: Record<string, string> = {
  "claude": "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border-[var(--accent-warning)]/25",
  "claude-code": "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border-[var(--accent-warning)]/25",
  "claude-plugin": "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border-[var(--accent-warning)]/25",
  "codex": "bg-[var(--accent-success)]/15 text-[var(--accent-success)] border-[var(--accent-success)]/25",
  "gemini": "bg-[var(--accent-info)]/15 text-[var(--accent-info)] border-[var(--accent-info)]/25",
  "cursor": "bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)] border-[var(--accent-secondary)]/25",
  "copilot": "bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)] border-[var(--accent-secondary)]/25",
  "opencode": "bg-[var(--text-muted)]/15 text-[var(--text-muted)] border-[var(--text-muted)]/25",
  "augur": "bg-[var(--text-muted)]/15 text-[var(--text-muted)] border-[var(--text-muted)]/25",
};

const CLIENT_DISPLAY_NAMES: Record<string, string> = {
  "claude": "Claude",
  "claude-code": "Claude",
  "claude-plugin": "Claude",
  "codex": "Codex",
  "gemini": "Gemini",
  "cursor": "Cursor",
  "copilot": "Copilot",
  "opencode": "OpenCode",
  "augur": "Augur",
};

/* ------------------------------------------------------------------ */
/*  BrowseBadges — capped with "+N more" overflow                      */
/* ------------------------------------------------------------------ */

const MAX_VISIBLE_BADGES = 3;

export function collectBadges(item: BrowseItem): BadgeEntry[] {
  const badges: BadgeEntry[] = [];
  const m = item.metadata;
  if (isWikiPageItem(item)) {
    const stateLabel = wikiMaintenanceStateLabel(m?.wikiMaintenanceState);
    if (stateLabel) {
      const stateClass = m?.wikiMaintenanceState === "no-apply"
        ? "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border-[var(--accent-warning)]/25"
        : m?.wikiMaintenanceState === "current"
          ? "bg-[var(--accent-success)]/15 text-[var(--accent-success)] border-[var(--accent-success)]/25"
          : "bg-[var(--accent-info)]/15 text-[var(--accent-info)] border-[var(--accent-info)]/25";
      badges.push({ key: "wiki-maintenance-state", node: (
        <span
          className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${stateClass}`}
          title={m?.wikiLastBatchReason || m?.wikiMaintenanceVerdict || "Wiki maintenance status"}
        >
          {stateLabel}
        </span>
      )});
    }
    const pendingLabel = positiveCountLabel(m?.wikiPendingSources, "pending");
    if (pendingLabel) {
      badges.push({ key: "wiki-pending", node: (
        <span
          className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]"
          title={m?.wikiLastBatchReason || "Sources pending wiki extraction"}
        >
          {pendingLabel}
        </span>
      )});
    }
    if (m?.wikiLastReindexedAt) {
      badges.push({ key: "wiki-reindexed", node: (
        <span
          className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-success)]/10 text-[var(--accent-success)] border border-[var(--accent-success)]/20"
          title={`Last reindexed: ${m.wikiLastReindexedAt}`}
        >
          reindexed
        </span>
      )});
    }
  }
  if (m?.archive_source) {
    badges.push({ key: "archive-source", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)] border border-[var(--accent-info)]/20">
        archive_source={m.archive_source}
      </span>
    )});
  }
  // ADR-748 Decision §3: prompt cards expose a `source` badge so user-authored
  // vault prompts are visually distinct from skill-shipped prompts. Gated on
  // m.prompt to scope this to prompt items (other kinds reuse `source` for
  // discovery tags like "private-vault" / "claude-local" — different vocabulary).
  if (m?.prompt && (m?.source === "vault" || m?.source === "skill")) {
    const isVault = m.source === "vault";
    const cls = isVault
      ? "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border-[var(--accent-warning)]/25"
      : "bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border-color)]";
    badges.push({ key: "prompt-source", node: (
      <span
        className={`px-2 py-0.5 rounded text-[11px] font-medium border ${cls}`}
        title={`Source: ${m.source}`}
      >
        {m.source}
      </span>
    )});
  }
  // ADR-772: federated records carry their owning brain. The badge rides the
  // existing card (rule 32) so cross-brain views are visibly attributed.
  if (m?.brain_id) {
    badges.push({ key: "brain", node: (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)] border border-[var(--accent-info)]/20"
        title={`Brain: ${m.brain_id}`}
      >
        <Layers className="size-3" aria-hidden="true" />
        {m.brain_id}
      </span>
    )});
  }
  const scope = overlayScope(m);
  if (scope) {
    const cls = scope === "packet"
      ? "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border-[var(--accent-warning)]/25"
      : scope === "private"
        ? "bg-[var(--accent-info)]/15 text-[var(--accent-info)] border-[var(--accent-info)]/25"
        : "bg-[var(--accent-success)]/15 text-[var(--accent-success)] border-[var(--accent-success)]/25";
    badges.push({ key: `overlay-${scope}`, node: (
      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${cls}`}>{overlayScopeLabel(scope)}</span>
    )});
  }
  if (m?.visibility) {
    badges.push({ key: "visibility", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-success)]/10 text-[var(--accent-success)] border border-[var(--accent-success)]/20">/{item.id}</span>
    )});
  } else if (m?.visibility === "") {
    badges.push({ key: "visibility", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-primary)] text-[var(--text-secondary)]/50 border border-[var(--border-color)]">internal</span>
    )});
  }
  if (m?.qualityTier) {
    const cls = m.qualityTier === "A" ? "bg-[var(--accent-success)]/15 text-[var(--accent-success)]"
      : m.qualityTier === "B" ? "bg-[var(--accent-info)]/15 text-[var(--accent-info)]"
      : m.qualityTier === "C" ? "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]"
      : (m.qualityTier === "D" || m.qualityTier === "F") ? "bg-[var(--accent-danger)]/15 text-[var(--accent-danger)]"
      : "bg-[var(--text-muted)]/15 text-[var(--text-muted)]";
    badges.push({ key: "quality", node: (
      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${cls}`}>{m.qualityTier} ({m.qualityScore})</span>
    )});
  }
  if (m?.pages && m.pages !== "0") {
    badges.push({ key: "pages", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">
        {m.customPages !== "0" ? `${m.customPages} custom` : `${m.pages} pages`}
      </span>
    )});
  }
  if (m?.relevanceScore) {
    badges.push({ key: "relevance", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-secondary)]/10 text-[var(--accent-secondary)] border border-[var(--accent-secondary)]/20">{m.relevanceScore}%</span>
    )});
  }
  // ADR-741 check-resolvable: a capability_exposure entry pointing at a
  // skill/tool that no longer exists. Joined on by enrichItemsWithCoverage();
  // the audit has no browse view of its own (see lib/browse/skillCoverage.ts).
  if (m?.coverageStale) {
    badges.push({ key: "coverage-stale", node: (
      <span
        className="px-2 py-0.5 rounded text-[11px] font-semibold bg-[var(--accent-danger)]/15 text-[var(--accent-danger)] border border-[var(--accent-danger)]/25"
        title={m.coverageStale}
      >
        stale entry
      </span>
    )});
  }
  if (m?.mcp_tool_count && m.mcp_tool_count !== "0") {
    badges.push({ key: "mcp-tools", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">{m.mcp_tool_count} tools</span>
    )});
  }
  if (m?.enabled) {
    const on = m.enabled === "true";
    badges.push({ key: "enabled", node: (
      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${on ? "bg-[var(--accent-success)]/15 text-[var(--accent-success)]" : "bg-[var(--text-muted)]/15 text-[var(--text-muted)]"}`}>{on ? "enabled" : "disabled"}</span>
    )});
  }
  if (m?.blockCount && m.blockCount !== "0") {
    badges.push({ key: "blocks", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">{m.blockCount} blocks</span>
    )});
  }
  if (m?.fileCount && m.fileCount !== "0") {
    badges.push({ key: "file-count", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">
        {m.fileCount} {m.fileCount === "1" ? "file" : "files"}
      </span>
    )});
  }
  if (m?.totalSize) {
    badges.push({ key: "total-size", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">
        {m.totalSize}
      </span>
    )});
  }
  if (m?.skill) {
    badges.push({ key: "skill", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)]">{m.skill}</span>
    )});
  }
  if (m?.pageType && !m?.pageTags) {
    badges.push({ key: "page-type", node: (
      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${m.pageType === "custom" ? "bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)]" : "bg-[var(--bg-secondary)] text-[var(--text-muted)]"}`}>{m.pageType}</span>
    )});
  }
  if (m?.fileType) {
    badges.push({ key: "file-type", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">{m.fileType}</span>
    )});
  }
  if (m?.date) {
    badges.push({ key: "date", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)]">{m.date}</span>
    )});
  }
  if (m?.modified && !m?.date) {
    const label = (() => {
      try {
        const d = new Date(m.modified);
        const diffDays = Math.floor((Date.now() - d.getTime()) / 86400000);
        if (diffDays === 0) return "today";
        if (diffDays === 1) return "yesterday";
        if (diffDays < 30) return `${diffDays}d ago`;
        if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
        return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
      } catch { return ""; }
    })();
    if (label) badges.push({ key: "modified", node: <span className="text-[11px] text-[var(--text-muted)]">{label}</span> });
  }
  if (m?.status) {
    const cls = (m.status === "Implemented" || m.status === "accepted") ? "bg-[var(--accent-success)]/15 text-[var(--accent-success)]"
      : (m.status === "superseded" || m.status === "deprecated") ? "bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]"
      : "bg-[var(--accent-info)]/15 text-[var(--accent-info)]";
    badges.push({ key: "status", node: (
      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${cls}`}>{m.status}</span>
    )});
  }
  if (m?.mode) {
    badges.push({ key: "mode", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)]">{m.mode}</span>
    )});
  }
  if (m?.tier) {
    badges.push({ key: "tier", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-muted)] border border-[var(--border-color)]">tier {m.tier}</span>
    )});
  }
  if (m?.dispatch) {
    const cls = m.dispatch === "fire" ? "bg-[var(--accent-success)]/15 text-[var(--accent-success)]"
      : m.dispatch === "ide" ? "bg-[var(--accent-info)]/15 text-[var(--accent-info)]"
      : "bg-[var(--accent-secondary)]/15 text-[var(--accent-secondary)]";
    badges.push({ key: "dispatch", node: (
      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${cls}`}>{m.dispatch}</span>
    )});
  }
  const skillClients = m?.skillClients
    ? m.skillClients.split(",").flatMap((client) => {
        const trimmed = client.trim();
        return trimmed ? [trimmed] : [];
      })
    : [];
  if (skillClients.length > 0) {
    for (const client of skillClients.slice(0, 3)) {
      badges.push({ key: `client-${client}`, node: (
        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${CLIENT_BADGE_COLORS[client] || CLIENT_BADGE_COLORS.augur}`}>
          {CLIENT_DISPLAY_NAMES[client] || client}
        </span>
      )});
    }
  } else if (m?.masterClient) {
    badges.push({ key: "master-client", node: (
      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${CLIENT_BADGE_COLORS[m.masterClient] || CLIENT_BADGE_COLORS.augur}`}>
        {CLIENT_DISPLAY_NAMES[m.masterClient] || m.masterClient}
      </span>
    )});
  }
  // External repo badge — shown only for external inventory, not adopted skills.
  const ownership = typeof m?.ownership === "string" ? m.ownership : "";
  if (
    ownership === "external" ||
    (!ownership && (m?.source === "external" || m?.installMethod === "script"))
  ) {
    badges.push({ key: "external", node: (
      <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border-[var(--accent-primary)]/20">
        Community
      </span>
    )});
  }
  if (m?.plugin) {
    badges.push({ key: "plugin", node: (
      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)] border border-[var(--accent-info)]/20">{m.plugin}</span>
    )});
  }
  if (m?.skillType) {
    const cls = m.skillType === "domain" ? "bg-violet-500/15 text-violet-500"
      : m.skillType === "command" ? "bg-emerald-500/15 text-emerald-500"
      : m.skillType === "library-reference" ? "bg-amber-500/15 text-amber-500"
      : m.skillType === "runbook" ? "bg-sky-500/15 text-sky-500"
      : m.skillType === "autoloop" ? "bg-pink-500/15 text-pink-500"
      : m.skillType === "template" ? "bg-cyan-500/15 text-cyan-500"
      : "bg-[var(--text-muted)]/15 text-[var(--text-muted)]";
    badges.push({ key: "skill-type", node: (
      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold tracking-wider ${cls}`}>{m.skillType}</span>
    )});
  }
  if (m?.skillTags) {
    for (const tag of m.skillTags.split(",").slice(0, 3)) {
      const trimmed = tag.trim();
      if (trimmed) {
        badges.push({ key: `skill-tag-${trimmed}`, node: (
          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)]">{trimmed}</span>
        )});
      }
    }
  }
  if (!isWikiPageItem(item)) {
    for (const tag of itemPageTags(item).slice(0, 3)) {
      badges.push({ key: `page-tag-${tag}`, node: (
        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)]">{tag}</span>
      )});
    }
  }
  return badges;
}

export function BrowseBadges({ item }: { item: BrowseItem }) {
  const allBadges = collectBadges(item);
  const visible = allBadges.slice(0, MAX_VISIBLE_BADGES);
  const overflowCount = allBadges.length - visible.length;

  if (allBadges.length === 0) {
    return null;
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-1.5">
      {visible.map((b) => (
        <React.Fragment key={b.key}>{b.node}</React.Fragment>
      ))}
      {overflowCount > 0 && (
        <span
          className="px-2 py-0.5 rounded-md text-[11px] font-medium text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-color)]"
          title={allBadges.slice(MAX_VISIBLE_BADGES).map((b) => b.key).join(", ")}
        >
          +{overflowCount} more
        </span>
      )}
    </div>
  );
}
