---
status: Implemented
date: '2026-03-06'
deciders:
- gsannikov
related: []
hub: null
tags:
- capability
- migration
- audit
- dashboard
superseded_by: null
---

# ADR-253: Capability Migration Audit Dashboard

**Related ADRs**: ADR-237 (hub hardening), ADR-246 (auto-loop consolidation), ADR-251 (command registry parity)

## Context

The `/ops-refactor` command audits Augur workflows against latest AI client capabilities (Claude Code, Cursor, Gemini CLI, etc.) and produces a migration report with cross-agent parity analysis. It runs as an interactive CLI command and has driven significant architectural simplification — most recently the removal of the orchestration and offload subsystems (commit `5f338ce10`, `3c312f636`).

Current problems:

1. **No persistent report storage** — the report is generated inline during the session and lost when the session ends. Users must re-run the full audit to review findings.
2. **No dashboard visibility** — there's no way to view the migration report outside of the CLI session that generated it.
3. **No staleness tracking** — reports go stale as clients release new features, but there's no mechanism to flag when a new audit is needed.
4. **No IDE follow-up** — acting on findings requires manually reading the report and starting a new session. There's no action button to send the report to an IDE for interactive implementation.
5. **Client-locked** — the audit should be runnable from any supported client, not just Claude Code.

The `/auto-refactor` auto-command exists as a loop wrapper but has no scanner — it reports "no autonomous scanner (findings fed externally)". The dashboard surface would close this gap by making the report visible and actionable.

## Decision

### 1. Report Data Model

Save structured YAML reports in `plugins/dev/skills/devops/augur/data/reports/`:

- `ops-refactor-YYYY-MM-DD.yaml` — timestamped report with summary, findings (classified as MIGRATE/ENHANCE/EXPLORE/SKIP), cross-agent parity data, and next steps.
- `ops-refactor-expiry.yaml` — separate expiry tracking file with 14-day default. Integrates with the existing `check-expirations` daemon for dashboard flagging and notification.

### 2. Dashboard Page (`/dev/devops/refactor`)

New sub-page under the devops skill dashboard:

- Header with staleness indicator (green/amber/red based on expiry)
- Summary cards: MIGRATE, ENHANCE, EXPLORE, SKIP counts + token/latency savings estimates
- Two action buttons: "Run Audit" (oneshot dispatch) and "Work on Report in IDE" (ide dispatch)
- Priority matrix with expandable findings showing migration path, files, and risk
- Cross-agent parity section with coverage bars per agent
- Next steps grouped by timeframe (immediate/this_week/backlog)

### 3. Action Wiring

Two action definitions:

- `ops-refactor-audit` — `dispatch: oneshot`, runs `/ops-refactor` in an agent bubble. The audit involves web search and codebase scanning, suitable for a visible bubble.
- `ops-refactor-followup` — `dispatch: ide`, sends the full report as context to the connected IDE/CLI for interactive implementation of findings. Works with any supported client.

### 4. API Route

`GET /api/dev/refactor-report` — reads the latest report YAML and expiry YAML, computes staleness, returns JSON for the dashboard page.

### 5. Workflow Update

Add Step 6 to `ops-refactor.md`: after generating the report, save it as structured YAML and update the expiry file. This makes every future `/ops-refactor` run automatically persist its results for dashboard consumption.

### 6. Tab Registration

Register the page in `plugins/dev/skills/devops/augur.yaml` as a page contribution with route `/dev/devops/refactor`.

## Consequences

### Positive

- Migration report becomes persistent and reviewable without re-running the audit
- Expiry integration ensures reports don't silently go stale — dashboard flags and daemon notifications prompt re-audit
- IDE follow-up button enables immediate action on findings from any supported client
- Oneshot dispatch makes the audit accessible from the dashboard without needing CLI access
- The existing `auto-refactor` auto-command loop can potentially feed findings into the stored report

### Negative

- Adds a new API route that reads files directly (no MCP tool backing yet) — may need MCP tool later for consistency
- Report schema must be maintained in sync between the workflow (which writes YAML) and the dashboard (which reads it)

### Neutral

- Seed data file provides a development scaffold but should be replaced by a real audit run after implementation

## Implementation Order

### Phase 1: Data Layer (no dependencies)
1. Create reports directory and seed sample YAML report
2. Create expiry file with 14-day default
3. Create API route to serve report + expiry as JSON

### Phase 2: Dashboard (depends on Phase 1)
4. Create dashboard page component with all sections
5. Create action YAML definitions (oneshot + ide)
6. Register page and actions in augur.yaml, mount to dashboard

### Phase 3: Workflow Integration (independent)
7. Update ops-refactor.md with Step 6 for YAML persistence

### Phase 4: Verification (depends on all above)
8. End-to-end verification: API, page rendering, action wiring, expiry display

## Alternatives Considered

### A: Embed in existing devops page

Add the report as a collapsible card on `/dev/devops`. Rejected because the devops page is already dense with 9 action buttons and cross-hub links. The report content (priority matrix, detailed findings, parity analysis) deserves its own page.

### B: Extend advisor analytics

Add as a tab on `/dev/advisor/analytics`. Rejected because advisor is about telemetry/backlog metrics, not capability migration — wrong conceptual home. Also violates plugin decentralization (advisor skill ≠ devops skill).

### C: Markdown report instead of YAML

Store as markdown like the current output format. Rejected because the dashboard needs structured data (counts, classifications, priority scores). Parsing markdown is fragile. YAML supports both structure and rich content via multiline fields.

## References

- Design doc: `docs/plans/2026-03-06-ops-refactor-dashboard-design.md`
- Implementation plan: `docs/plans/2026-03-06-ops-refactor-dashboard-design.md` (Tasks section)
- Workflow: `plugins/dev/skills/devops/commands/ops-refactor.md`
- Auto-command: `plugins/dev/skills/devops/commands/auto-refactor/SKILL.md`
- Pattern reference: `plugins/dev/skills/advisor/augur/dashboard/analytics/page.tsx` (report page with action buttons)

## Implementation Prompt

Implementation plan with 7 tasks is in `docs/plans/2026-03-06-ops-refactor-dashboard-design.md`. Execute with `superpowers:executing-plans`.

**Team name**: `adr-253-capability-audit-dashboard`

| Phase | Step | Agent | Model | Isolation | Depends On |
|-------|------|-------|-------|-----------|------------|
| 1 | Seed report YAML + expiry | developer | medium | none | — |
| 1 | API route | developer | medium | none | — |
| 2 | Action YAML definitions | developer | low | none | — |
| 2 | Dashboard page | frontend | high | none | Phase 1 |
| 2 | Register in augur.yaml + mount | developer | medium | none | Phase 2 page |
| 3 | Update ops-refactor workflow | developer | medium | none | — |
| 4 | E2E verification | validator | high | none | All above |

Phases 1 and 3 are independent and can execute in parallel. Phase 2 depends on Phase 1 (API route must exist for the page to fetch data). Phase 4 is the final gate.
