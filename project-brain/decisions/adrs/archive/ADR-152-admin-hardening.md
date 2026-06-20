---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- admin
- hardening
superseded_by: null
---

# ADR-152: Admin Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 60/100 | 12% | significant-gaps | /admin/migrations, /admin/plugins, /admin/renderer lack GlassCard; overview + system-cleanup already use glass-panel |
| 2 | Page Coverage | 75/100 | 10% | needs-work | Missing page.tsx for tab 'Releases' (/admin/releases) declared in augur.yaml |
| 3 | API Completeness | 84/100 | 12% | needs-work | 2/13 API routes are stubs (health endpoints return hardcoded `{status:'ok'}`) |
| 4 | MCP Tool Wiring | 6/100 | 10% | critical | augur.yaml declares 6 `tool: mcp://` refs but dashboard pages use raw `fetch()` instead of `useActionRunner` — tools exist but are not rendered |
| 5 | Performance | 36/100 | 10% | critical | Zero `dynamic()` imports; system-cleanup is 512 lines with no code splitting |
| 6 | User Value | 45/100 | 15% | significant-gaps | System-cleanup has full scan→execute→terminal flow; updater has data/config.yaml+history.yaml but no persisted update log in runtime/ |
| 7 | Workflows | 0/100 | 8% | critical | system-cleanup has 3 action YAMLs, updater declares 6 actions in augur.yaml — but none surface as dispatchable workflow chains in dashboard |
| 8 | Cross-Hub Connectivity | 40/100 | 5% | critical | No cross-hub navigation links — hub is isolated; 12 API-level connections detected but not exposed in UI |
| 9 | Action Buttons | 0/100 | 8% | critical | No `useActionRunner` in any dashboard page — all interactivity uses raw `fetch()` |
| 10 | Wow Effect | 0/100 | 10% | critical | No streaming update terminal; updater tools + actions declared but not wired to UI |

**Composite Score**: 37/100 (major-rebuild)

**Audit corrections** (vs auto-generated scores):
- MCP Tool Wiring scored 6 but augur.yaml already has 6 `tool: mcp://` refs — real gap is dashboard rendering, not declaration. Effective score ~30.
- Workflows scored 0 but system-cleanup has 3 action YAMLs and updater declares 6 actions — real gap is chain wiring, not absence. Effective score ~35.
- User Value scored 45 but updater has `data_dir: services/updater` with config.yaml+history.yaml — "no data directory" is incorrect. Effective score ~55.
- UI Compliance scored 60 but overview page already uses `glass-panel` CSS class — only 3 of 5 pages are non-compliant, not all 5. Effective score ~70.

## Wow Effect: One-Click Update with Live Logs

> Full update cycle — check, backup, apply, migrate — streamed live in a terminal panel with automatic rollback on failure. Transforms the updater from a black box into a visible, trustworthy process.

**Score**: 0/100

**Demo Flow**:
1. User clicks "Update Augur" action button (rendered via `useActionRunner`, dispatch: `fire`)
2. Pre-flight: `updater-check` MCP tool runs → version comparison, conflict detection displayed in UpdateTerminal
3. Backup: `updater-backup` MCP tool runs → progress indicator shows backup creation
4. Apply: `updater-apply` MCP tool runs → API route streams SSE output (git fetch, merge, rebuild) line-by-line to UpdateTerminal
5. Migrate: `updater-migrate` MCP tool runs → step-by-step migration progress displayed
6. On failure at any step: `updater-rollback` MCP tool triggers automatically → toast notification with failure reason
7. On success: version badge updates inline, `updater-releases` MCP tool fetches changelog for display

**MCP tool mapping**:
| Demo Step | MCP Tool | augur.yaml Action |
|-----------|----------|-------------------|
| Pre-flight | `updater-check` | `check-updates` (dispatch: fire) |
| Backup | `updater-backup` | `create-backup` (dispatch: fire) |
| Apply | `updater-apply` | `apply-update` (type: modal → confirm-update) |
| Migrate | `updater-migrate` | `run-migrations` (dispatch: fire) |
| Rollback | `updater-rollback` | `rollback` (type: modal) |
| Changelog | `updater-releases` | (new: add to contributions.actions) |

**Component design**: `UpdateTerminal` reuses `CleanupTerminal` pattern (system-cleanup already has this). API route `/api/admin/update` returns SSE stream (`text/event-stream`). Terminal component subscribes via `EventSource` and renders lines with timestamps, color-coded by type (command/info/success/error). Rollback detection: if any step's response contains `success: false` or HTTP >= 400, abort chain and call rollback.

**Current state**: Updater has 10 MCP tools and 6 actions declared in augur.yaml but dashboard uses raw `fetch()` calls — none wired via `useActionRunner`

**Gap to demo-ready**:
1. Create `UpdateTerminal` component (reuse CleanupTerminal interface)
2. Add SSE streaming to `/api/admin/update/route.ts`
3. Replace raw `fetch()` buttons with `useActionRunner` action buttons
4. Wire the check→backup→apply→migrate chain as sequential dispatch
5. Add rollback-on-failure guard with error boundary

**Cross-hub leverage**: Pulls data from observe (audit trail of update events), ai (agent config regeneration post-update)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Admin** (http://localhost:3000/admin) on 2026-02-25.
Composite score: **37/100**.

### Existing Assets (preserve, don't recreate)

Before implementing, note what already exists:
- **updater/augur.yaml**: 6 actions with `tool: mcp://` refs, 2 modals with `submitTool`, tab groups, contributions.pages
- **updater components**: `UpdateStatusCard`, `MigrationTimeline`, `BackupManager`, `PluginCard`, `ChangelogViewer` (all exist in `augur/dashboard/components/`)
- **system-cleanup components**: `SystemStatsPanel`, `CleanupCategoryCard`, `CleanupConfirmModal`, `CleanupTerminal` (all fully implemented)
- **system-cleanup action YAMLs**: `system-review.yaml`, `open-data-folder.yaml`, `system-review-batch.yaml` in `augur/data/actions/`
- **updater data**: `config.yaml`, `history.yaml` in `augur/data/`
- **channels skill**: Hidden skill with 7 MCP tools (iMessage + WhatsApp) — no dashboard UI, intentionally headless

### Issues Identified

**UI Compliance** (60/100):
- No GlassCard/glass-panel usage in /admin/migrations (uses DashboardWidget)
- No GlassCard/glass-panel usage in /admin/plugins (uses DashboardWidget)
- No GlassCard/glass-panel usage in /admin/renderer (uses plain `bg-[var(--bg-card)]` divs)
- /admin overview and /admin/system-cleanup already use glass-panel CSS class

**MCP Tool Wiring** (6/100):
- augur.yaml declares 6 `tool: mcp://augur/...` action refs — these are correct
- Dashboard pages use raw `fetch('/api/...')` instead of `useActionRunner` dispatch
- 0/5 pages invoke MCP tools via the standard action dispatch pattern

**Performance** (36/100):
- No `dynamic()` imports across any admin dashboard page
- No code splitting for large page: /admin/system-cleanup (512 lines)
- All component imports are static in all pages

**User Value** (45/100):
- Updater has `data_dir: services/updater` and data/config.yaml+history.yaml — but no runtime/ update log
- 10/13 API routes have real backend logic (system-cleanup's scan/execute/stats are fully functional)
- 4/5 pages fetch real data
- System-cleanup has a complete scan→confirm→execute→terminal workflow already

**Workflows** (0/100):
- system-cleanup has 3 action YAMLs in augur/data/actions/ (system-review, open-data-folder, system-review-batch)
- updater declares 6 actions in augur.yaml contributions.actions
- Neither skill surfaces these as dispatchable chains — no `useActionRunner` usage, no sequential dispatch
- Missing: "Update Augur" chain (check→backup→update→migrate) as a workflow

**Cross-Hub Connectivity** (40/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 12 connections (API-level, not surfaced in UI)

**Action Buttons** (0/100):
- No `useActionRunner` in any dashboard page
- All interactivity uses raw `onClick` → `fetch()` pattern
- augur.yaml actions are declared but never rendered as UI buttons

**Wow Effect** (0/100):
- No streaming terminal for update operations
- CleanupTerminal exists in system-cleanup but no equivalent UpdateTerminal
- All update operations are fire-and-forget with no live feedback

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 0/100) — **One-Click Update with Live Logs**:
- Create `UpdateTerminal` component reusing `CleanupTerminal` interface from system-cleanup
- Add SSE streaming to `/api/admin/update/route.ts` for live output
- Wire the check→backup→apply→migrate chain as sequential MCP dispatch
- Implement rollback-on-failure: if any step returns `success: false` or HTTP >= 400, call updater-rollback
- Demo flow: click "Update Augur" → pre-flight check → auto backup → live streaming build → migration steps → success/rollback

**MCP Tool Wiring** (current: 6/100):
- augur.yaml already declares 6 `tool: mcp://` refs — do NOT recreate
- Real gap: replace raw `fetch()` in dashboard pages with `useActionRunner` dispatch
- Wire system-cleanup action YAMLs to dashboard buttons (3 already exist in data/actions/)
- Verify all 10 updater + 2 system-cleanup MCP tools are callable end-to-end

**Action Buttons** (current: 0/100):
- Replace all raw `fetch()` button handlers with `useActionRunner` + `dispatch: 'ide'`
- Updater: Check Updates, Update, Migrate, Backup, Rollback, Diagnose (6 buttons, matching augur.yaml actions)
- System-cleanup: already has functional buttons — add `useActionRunner` wrapper, keep existing UX

**Workflows** (current: 0/100):
- Define "Update Augur" chain: check-updates → create-backup → apply-update → run-migrations (sequential dispatch)
- System-cleanup already has scan→confirm→execute flow — add chain declaration to augur.yaml
- Surface chains as one-click workflows on overview pages

**Cross-Hub Connectivity** (current: 40/100):
- Add navigation links to /observe (audit trail), /ai (agent config regen), /dev (build status)
- Import observe hub metrics service for update event logging
- Add "Related" section to overview page with cross-hub cards

**Performance** (current: 36/100):
- Add `dynamic()` imports for UpdateTerminal, MigrationTimeline, BackupManager, ChangelogViewer
- System-cleanup: wrap CleanupTerminal, CleanupConfirmModal in dynamic imports (already extracted as components — don't re-extract)
- Add loading skeletons for dynamically imported components

**User Value** (current: 45/100):
- Persist update history to `runtime/admin/update-history.json` after each update operation
- Surface update timeline on overview page
- updater already has data/config.yaml+history.yaml — supplement, don't replace

### Phase 2: Completeness

**UI Compliance** (current: 60/100):
- /admin/migrations: replace DashboardWidget with GlassCard containers
- /admin/plugins: replace DashboardWidget with GlassCard containers
- /admin/renderer: replace plain `bg-[var(--bg-card)]` divs with GlassCard, add loading states and interactive elements
- /admin overview and /admin/system-cleanup already use glass-panel — verify consistency only

### Phase 3: Polish & Performance

**Page Coverage** (current: 75/100):
- Create /admin/releases page (declared in augur.yaml contributions.pages but no page.tsx exists)
- ChangelogViewer component already exists in updater/components/ — wire it to updater-releases MCP tool

**API Completeness** (current: 84/100):
- /api/admin/health: replace stub with aggregated health from all admin skill MCP tools
- /api/admin/system-cleanup/health: replace stub with macOS disk/memory stats via system calls

## Consequences

### Positive

- Admin hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: One-Click Update with Live Logs
- Existing functional code (system-cleanup terminal, updater components) preserved and extended

### Negative

- Requires implementation effort across 10 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)
- SSE streaming in update API adds complexity vs simple JSON response

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking
- channels skill remains headless (intentional — no dashboard needed)

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
Manual review applied corrections to 4 audit scores and restructured execution plan dependencies.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `admin` hub audit
- Audit timestamp: 2026-02-25T01:02:24.359387
- Pattern reference: `plugins/admin/skills/system-cleanup/augur/dashboard/components/CleanupTerminal.tsx` (reuse for UpdateTerminal)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065. Manually reviewed and corrected.

You are implementing **ADR-152: Admin Hardening**.

Read the full ADR: `docs/decisions/ADR-152-admin-hardening.md`

### Important: Existing Assets

Before writing any code, verify these already exist (do NOT recreate):
- `plugins/admin/skills/updater/augur.yaml` — already has 6 actions with `tool: mcp://` refs, 2 modals, tab_groups
- `plugins/admin/skills/updater/augur/dashboard/components/` — UpdateStatusCard, MigrationTimeline, BackupManager, PluginCard, ChangelogViewer
- `plugins/admin/skills/system-cleanup/augur/dashboard/components/` — SystemStatsPanel, CleanupCategoryCard, CleanupConfirmModal, CleanupTerminal
- `plugins/admin/skills/system-cleanup/augur/data/actions/` — 3 action YAMLs (system-review, open-data-folder, system-review-batch)
- `plugins/admin/skills/updater/augur/data/` — config.yaml, history.yaml

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` -> look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output
4. Record the verdict (accept / fix / escalate)
5. If `offload.enabled: false` OR tier is `medium`/`high` -> do the step yourself

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-152-admin-hardening", description="Implementing ADR-152: Admin Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for dependencies shown in the dependency column.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-152-admin-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{{role}}' on the {team_name} team.
        Read your profile: .claude/agents/{{role}}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: See `Depends On` column — spawn independent steps in parallel, gate dependent steps with task blocking
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-152-admin-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: MIXED (see dependency column — parallel where independent, pipeline where dependent)

| Step | Agent | Tier | Depends On | Task | Files |
|------|-------|------|------------|------|-------|
| 1.1 | developer | high | — | Wow Effect: Create `UpdateTerminal` component (reuse CleanupTerminal interface), add SSE streaming to `/api/admin/update/route.ts`, wire check→backup→apply→migrate chain with rollback-on-failure guard | `plugins/admin/skills/updater/augur/dashboard/components/UpdateTerminal.tsx`, `plugins/admin/skills/updater/augur/api/update/route.ts`, `plugins/admin/skills/updater/augur/dashboard/page.tsx` |
| 1.2 | devops | low | — | MCP Tool Wiring: augur.yaml already has 6 `tool: mcp://` refs — verify they resolve. Add `mcp_tool` refs to system-cleanup augur.yaml for scan/execute/stats. Verify all 10+2 MCP tools are callable end-to-end via `callMcpTool` | `plugins/admin/skills/system-cleanup/augur.yaml`, `plugins/admin/skills/updater/augur.yaml` |
| 1.3 | frontend | medium | — | Performance: Add `dynamic()` imports in all admin pages. Updater overview: dynamic-import UpdateTerminal, MigrationTimeline, BackupManager. Plugins page: dynamic-import PluginCard. System-cleanup: wrap CleanupTerminal + CleanupConfirmModal in dynamic imports (components already extracted — do NOT re-extract). Add loading skeletons. | `plugins/admin/skills/updater/augur/dashboard/page.tsx`, `plugins/admin/skills/updater/augur/dashboard/plugins/page.tsx`, `plugins/admin/skills/system-cleanup/augur/dashboard/page.tsx` |
| 1.4 | developer | medium | 1.1 | Action Buttons: Replace all raw `fetch()` button handlers with `useActionRunner` + `dispatch:'ide'`. Updater: 6 buttons (Check Updates, Update, Migrate, Backup, Rollback, Diagnose) matching augur.yaml actions. System-cleanup: wrap existing functional buttons with `useActionRunner`. | `plugins/admin/skills/updater/augur/dashboard/page.tsx`, `plugins/admin/skills/system-cleanup/augur/dashboard/page.tsx` |
| 1.5 | architect | medium | 1.4 | Workflows: Define "Update Augur" chain (check-updates→create-backup→apply-update→run-migrations) in augur.yaml. Add "System Cleanup" chain declaration (scan→confirm→execute). Surface chains as one-click workflow buttons on overview pages. | `plugins/admin/skills/updater/augur.yaml`, `plugins/admin/skills/system-cleanup/augur.yaml` |
| 1.6 | developer | medium | — | Cross-Hub: Add navigation cards to /observe (audit trail), /ai (agent config regen), /dev (build status) on updater overview. Add "Related Hubs" section. Import observe metrics service for update event logging. | `plugins/admin/skills/updater/augur/dashboard/page.tsx`, `plugins/admin/skills/updater/augur/dashboard/components/CrossHubLinks.tsx` |
| 1.7 | developer | medium | — | User Value: Persist update history to `runtime/admin/update-history.json` after each update. Surface update timeline on overview. Add `updater-releases` action to augur.yaml contributions.actions. | `plugins/admin/skills/updater/augur/api/update/route.ts`, `plugins/admin/skills/updater/augur.yaml` |

**Parallelism**: Steps 1.1, 1.2, 1.3, 1.6, 1.7 can all start immediately. Step 1.4 waits for 1.1 (needs UpdateTerminal). Step 1.5 waits for 1.4 (needs action buttons before chaining).

#### Phase 2: Completeness
**Strategy**: SINGLE STEP (can start once Phase 1 is complete)

| Step | Agent | Tier | Depends On | Task | Files |
|------|-------|------|------------|------|-------|
| 2.1 | frontend | medium | Phase 1 | UI Compliance: Migrate /admin/migrations, /admin/plugins to GlassCard (currently use DashboardWidget). Fix /admin/renderer (currently uses plain divs — add GlassCard, loading states, interactive elements). Verify /admin overview + /admin/system-cleanup glass-panel usage is consistent. | `plugins/admin/skills/updater/augur/dashboard/migrations/page.tsx`, `plugins/admin/skills/updater/augur/dashboard/plugins/page.tsx`, `plugins/admin/skills/renderer/augur/dashboard/page.tsx` |

#### Phase 3: Polish & Performance
**Strategy**: PARALLEL (both steps independent)

| Step | Agent | Tier | Depends On | Task | Files |
|------|-------|------|------------|------|-------|
| 3.1 | developer | medium | Phase 2 | Page Coverage: Create /admin/releases/page.tsx — ChangelogViewer component already exists in updater/components/, wire it to `updater-releases` MCP tool, show version tags, dates, formatted changelogs | `plugins/admin/skills/updater/augur/dashboard/releases/page.tsx` |
| 3.2 | developer | medium | Phase 2 | API Completeness: Replace health stubs — /api/admin/health: aggregate health from all admin skill MCP tools. /api/admin/system-cleanup/health: check macOS disk/memory via `os` module calls. Both must call MCP tools per MCP-first API rule. | `plugins/admin/skills/updater/augur/api/health/route.ts`, `plugins/admin/skills/system-cleanup/augur/api/health/route.ts` |

#### Final Phase: Verification

| Step | Agent | Tier | Depends On | Task |
|------|-------|------|------------|------|
| V.1 | validator | low | Phase 3 | Run all tests (`pytest tests/src/`, `npm run build`), verify no regressions |
| V.2 | frontend | low | V.1 | Browser validation: open http://localhost:3000/admin in Chrome MCP, screenshot each tab, check console for runtime errors, verify action buttons render and respond |
| V.3 | devops | low | V.1 | MCP validation: cross-check all `tool: mcp://` refs in augur.yaml against `mcp/__init__.py` registered tools for updater, system-cleanup, channels |
| V.4 | architect | low | V.2, V.3 | Verify ADR intent matches implementation — wow effect demo flow works end-to-end, all 10 dimensions improved |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90 (UpdateTerminal with SSE streaming, full chain demo)
- [ ] MCP Tool Wiring improved from 6/100 to >= 90 (all tools callable via useActionRunner)
- [ ] Performance improved from 36/100 to >= 90 (dynamic imports on all pages)
- [ ] User Value improved from 45/100 to >= 90 (persisted update history, timeline display)
- [ ] Workflows improved from 0/100 to >= 90 (update chain + cleanup chain defined and surfaced)
- [ ] Cross-Hub Connectivity improved from 40/100 to >= 90 (navigation cards to observe/ai/dev)
- [ ] Action Buttons improved from 0/100 to >= 90 (useActionRunner on all action buttons)
- [ ] UI Compliance improved from 60/100 to >= 90 (GlassCard on all 5 pages)
- [ ] Page Coverage improved from 75/100 to >= 90 (releases page created)
- [ ] API Completeness improved from 84/100 to >= 90 (health stubs replaced with real logic)
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in augur.yaml resolve to registered MCP tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-152 status updated to Accepted
