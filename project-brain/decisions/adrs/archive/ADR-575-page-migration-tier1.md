---
status: Implemented
date: 2026-03-30
deciders:
  - Gur Sannikov
related:
  - ADR-491
  - ADR-274
hub: null
tags:
  - dashboard
  - pages
  - migration
  - mcp
  - tooling
superseded_by: null
---

# ADR-575: Page Migration Tier 1 — Tool-First TSX-to-YAML Migration

## Context

The dashboard had 47 custom TSX pages under `skills/dashboard/pages/`. They worked but were hand-coded, inconsistent, and hard to maintain. A previous batch attempt converted 30+ pages at once with fabricated MCP tool names and no browser verification, producing pages with empty data and 500 errors.

Most pages can be expressed as YAML configs rendered by `ConfigPage` plus the block system (ADR-491), or covered by smart auto-pages from `SKILL.md` `x-augur-mcp-tools` (ADR-274). The migration must keep every page working at every step and avoid the previous mode of failure.

## Decision

Adopt a tool-first, one-page-at-a-time migration runbook for Tier 1 (read-only, 1–2 tools, no custom components: ~15 pages). Tooling and verification gates make verification mandatory at every step.

### Phase 1 — Tool verification diagnostic

Add `scripts/verify-page-tools.py`. It scans every TSX page for `useMcpQuery`, `useMcpMutation`, and `useMcpPoll` tool names; calls each tool through the MCP server; records whether the tool exists, returns data, and the data shape; and writes `docs/generated/tool-verification.json`. Pages are then grouped by readiness: READY (all tools return data), NO DATA (tools exist but empty), BLOCKED (tools missing). Missing tools are fixed in the MCP server, never skipped.

### Phase 2 — Per-page migration loop

For each page, in simplest-first order:

1. Read the TSX, extract every MCP tool, and verify each one returns data.
2. Fix broken tools in the MCP server before writing YAML.
3. Author `skills/{skill}/augur/pages/{name}.yaml` referencing only verified tools. Choose block type by intent: `metrics-dashboard` for multi-source, `card-grid`/`data-table` for lists, `stat-grid` for stats, `quickAdd`/`row_actions` for mutations.
4. Run `pnpm run build:scripts && node scripts/dist/mount-plugins.mjs && npx next build`; require pass.
5. Browser-verify in Chrome: page renders, data loads (no "No data"), no 500s, layout correct, interactions work.
6. Delete the TSX only after browser confirmation.
7. Commit `feat(pages): migrate {hub}/{page} to YAML config` per page.

If browser verification fails: revert YAML, keep TSX, debug. Never advance with a broken page.

### Phase 3 — Block enhancement when needed

If a tier needs capabilities the block system lacks (charts, tabbed sections, inline editing), enhance the block system first with tests, verify with test data, then resume migration.

### Tier 1 page set

career/growth, command/updater/plugins, life/health, adaptive/auto-skill-quality/skill-scores, plus the larger ladder of read-only stat displays. life/apple/voice stays as TSX because its custom interactive components (recorder, importer, folders, search) cannot be expressed as blocks.

### Anti-patterns explicitly forbidden

- Batch converting multiple pages without per-page browser verification.
- Writing YAML with unverified tool names.
- Deleting TSX before confirming the YAML replacement renders correctly.
- Skipping pages instead of fixing blockers.
- Making up MCP tool names from naming intuition.

## Consequences

### Positive
- Every migrated page is verified end-to-end before TSX deletion.
- Broken tools are fixed in the MCP server, raising data quality across the dashboard.
- Tool verification produces a reusable diagnostic for later tiers.
- Per-page commits create a clean rollback story.

### Negative
- The runbook is slow by design — one page per commit, browser verification mandatory.
- Pages with custom interactive components (e.g., voice recorder) stay as TSX, leaving a hybrid dashboard.

### Neutral
- Some Tier 1 pages need no YAML at all: when a skill's `x-augur-mcp-tools` covers the page, `buildDefaultPageConfig()` via Browse handles it for free.

## Alternatives Considered

### Alternative 1: Re-attempt batch migration
Rejected. The previous batch failed precisely because verification was deferred; doing more of the same pattern reintroduces the same failure mode.

### Alternative 2: Auto-generate YAML from TSX via static analysis
Rejected as the primary path. Heuristics cannot pick the right block type for mixed pages, and the failure mode is silent (empty pages render). Could be a tool used by humans, not the migration policy.

## References
- Plan: docs/superpowers/plans/2026-03-30-page-migration-tier1.md
- Spec: docs/superpowers/specs/2026-03-30-page-migration-runbook.md
