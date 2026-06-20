"use client";

/**
 * Visual tags for the 8 drift dimensions emitted by the backend drift engine
 * (`src/lib/capabilities/drift.py`, ADR-734 C2):
 *
 *   D1 direct_mcp_exposure       — generated MCP surface without policy export_to: mcp
 *   D2 unclassified_export       — unclassified capability exported to a client target
 *   D3 blocked_present           — blocked capability still in a generated surface
 *   D4 unexpected_client         — exposed to client not in export_to
 *   D5 duplicate_external_skill  — same skill across multiple external clients (warn)
 *   D6 draft_leakage             — staged draft surfaced as active client skill
 *   D7 agents_md_drift           — AGENTS.md disagrees with policy
 *   D8 client_budget_blowout     — tool/skill count exceeds client budget
 *
 * Also handles the four record-level drift markers that
 * `_record_drift()` in `exposure_policy.py` emits today:
 * `duplicate`, `unclassified_export`, `unexpected_client`,
 * `missing_expected_export`.
 *
 * Failure-class drift (Augur regressions) is amber; warning-class
 * drift (external duplication, missing expected export) is slate.
 */

const FAIL_DIMENSIONS = new Set([
  "direct_mcp_exposure",
  "unclassified_export",
  "blocked_present",
  "unexpected_client",
  "draft_leakage",
  "agents_md_drift",
  "client_budget_blowout",
  "duplicate",
]);

const DRIFT_LABEL: Record<string, string> = {
  direct_mcp_exposure: "direct MCP exposure",
  unclassified_export: "unclassified export",
  blocked_present: "blocked present",
  unexpected_client: "unexpected client",
  duplicate_external_skill: "duplicate external",
  draft_leakage: "draft leakage",
  agents_md_drift: "AGENTS.md drift",
  client_budget_blowout: "client budget blowout",
  duplicate: "duplicate",
  missing_expected_export: "missing export",
};

interface CapabilityDriftBadgeProps {
  drift: readonly string[];
  className?: string;
}

export function CapabilityDriftBadge({ drift, className }: CapabilityDriftBadgeProps) {
  if (!drift || drift.length === 0) {
    return null;
  }
  return (
    <span
      data-testid="capability-drift-badge"
      className={`inline-flex flex-wrap gap-1 ${className ?? ""}`.trim()}
    >
      {drift.map((kind) => {
        const isFailure = FAIL_DIMENSIONS.has(kind);
        const label = DRIFT_LABEL[kind] ?? kind;
        const palette = isFailure
          ? "border-amber-500/40 bg-amber-500/10 text-amber-700"
          : "border-slate-400/40 bg-slate-400/10 text-slate-700";
        return (
          <span
            key={kind}
            className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${palette}`}
            title={isFailure ? "Augur regression" : "Advisory drift"}
          >
            {label}
          </span>
        );
      })}
    </span>
  );
}
