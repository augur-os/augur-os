---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- productivity
- hardening
superseded_by: null
---

# ADR-156: Productivity Hardening

## Audit Summary

| # | Dimension | Raw | Adj.* | Weight | Status | Key Finding |
|---|-----------|-----|-------|--------|--------|-------------|
| 1 | UI Compliance | 61 | 61 | 12% | significant-gaps | No GlassCard in /productivity/calendar or /productivity/email; eisenhower layout bug masks UI |
| 2 | Page Coverage | 88 | 88 | 10% | needs-work | 2/22 pages use mock/hardcoded data (Organize, Duplicates) |
| 3 | API Completeness | 88 | 75 | 12% | significant-gaps | 16/18 API routes have real logic, but all 18 belong to apple skill — eisenhower and google-workspace have zero API routes |
| 4 | MCP Tool Wiring | 8 | ~35 | 10% | critical | Apple has 17 MCP tools + `mcp_tools` blocks; google-workspace has 7 tools + `mcp_tool` refs in augur.yaml. But 7 action YAMLs lack `mcp_tool` keys; organizer has zero tools |
| 5 | Performance | 38 | 50 | 10% | significant-gaps | Overview page (960 lines) needs code splitting; calendar (204L) and reminders (240L) are borderline |
| 6 | User Value | 42 | 55 | 15% | significant-gaps | All 4 skills have augur/data/ dirs with real content; 16/18 API routes real; no unified export |
| 7 | Workflows | 0 | 30 | 8% | critical | 7 action YAMLs across 3 skills (apple: 3, eisenhower: 2, google-workspace: 2); organizer: 0; no chains |
| 8 | Cross-Hub Connectivity | 80 | 80 | 5% | needs-work | Links to 6 hubs; no src/lib service imports for programmatic cross-hub data |
| 9 | Action Buttons | 0 | 25 | 8% | critical | Apple overview + eisenhower inbox + google-workspace (3 files) have useActionRunner; organizer has none |
| 10 | Wow Effect | 0 | 0 | 10% | critical | Individual data sources work but no unified workflow; no orchestrated demo |

\* **Adjusted scores** account for audit under-detection. Original audit only discovered the apple sub-skill, missing eisenhower/google-workspace/organizer. Dimensions 3, 4, 6, 7, 9 were manually verified across all 4 sub-skills. API Completeness adjusted *down* because all routes belong to apple — eisenhower and google-workspace have none.

**Raw Composite**: 41/100 (major-rebuild) | **Adjusted Composite**: 48/100 (needs-work)

## Wow Effect: Smart Daily Briefing

> AI reads calendar events + overdue reminders + inbox emails, generates a prioritized Do First list in the Eisenhower matrix. Combines Apple + Google data into one morning workflow.

**Score**: 0/100 (current) -> 95/100 (target)

**Current state**: Individual data sources work (calendar, reminders, email) but no unified workflow. Apple skill has 17 MCP tools and 6 actions. Google-workspace has 7 MCP tools and 7 actions. Neither is orchestrated into a cross-skill flow.

**Gap to demo-ready** (4 items):
1. **Daily Briefing action YAML**: Create `daily-briefing.yaml` in eisenhower skill with `dispatch: ide` referencing apple + google MCP tools cross-skill
2. **Eisenhower API routes**: Create `/api/productivity/eisenhower/tasks` and `/api/productivity/eisenhower/route` for task creation and Eisenhower quadrant routing (currently zero eisenhower API routes exist)
3. **Briefing summary component**: Build GlassCard component showing triaged results with source attribution (calendar icon, email icon, reminder icon per item) before routing to matrix
4. **Graceful degradation**: If a data source is unavailable (e.g. no Google Workspace), the briefing proceeds with available sources and notes which were skipped

**Flow**:
1. User clicks "Daily Briefing" action button on Eisenhower overview (also available on Productivity overview)
2. IDE agent fetches today's calendar events (`apple-calendar-today`)
3. IDE agent fetches overdue/due reminders (`apple-list-reminders`)
4. IDE agent fetches urgent unread emails (`google-gmail-list`); Apple Mail via `apple-list-emails` if available
5. AI triages all items by urgency/importance into Eisenhower quadrants
6. Tasks created in Do First / Schedule / Delegate via Eisenhower API (`/api/productivity/eisenhower/tasks`)
7. Briefing summary component shows triage results with source attribution
8. User sees populated matrix with AI-suggested priorities

**Cross-hub leverage**: career (job emails via `google-gmail-search`), health (health reminders), finance (financial emails)

**Priority**: This is the first thing to implement in Phase 1, after bug fixes in step 1.0.

## User Notes

Fix Eisenhower config error first. The "Eisenhower hub configuration not found" error and the services fetch 404 (returning HTML instead of JSON) are the most visible bugs and should be prioritized in Phase 1 before feature work.

## Context

Automated hardening audit of **Productivity** (http://localhost:3000/productivity/eisenhower/do-first) on 2026-02-25.
Composite score: **41/100** (raw) / **48/100** (adjusted).

### Hub Architecture

| Skill | Role | MCP Tools | Actions (augur.yaml) | Action YAMLs | API Routes | Pages | Dashboard State |
|-------|------|-----------|---------------------|--------------|------------|-------|-----------------|
| **apple** | Hub owner | 17 | 6 (quick-capture, create-note, refresh-inbox, create-reminder, transcribe-memo, triage-inbox) | 3 (create-note, create-reminder, refresh-inbox) | 18 (all routes) | 8 (overview + 7 sub-pages) | Functional — real MCP calls, modals, action buttons |
| **eisenhower** | Sub-skill | 0 | 2 (add-task, prioritize) | 2 (prioritize, route-all-auto) | 0 | 7 (matrix + 5 quadrants + inbox) | Broken — layout calls getHubConfig('eisenhower'), tab hrefs wrong |
| **google-workspace** | Sub-skill | 7 | 7 (triage-inbox, refresh-gmail, refresh-calendar, extract-career-emails, draft-reply, schedule-follow-up, email-digest) | 2 (draft-reply, extract-career-emails) | 0 | 5 (overview + gmail + calendar + drive + docs) | Partial — augur.yaml well-defined, no API routes, tab hrefs wrong |
| **organizer** | Sub-skill | 0 | 0 | 0 | 1 (health stub) | 4 (overview + organize + duplicates + cleanup) | Mock — hardcoded data, no actions, no MCP tools, tab hrefs wrong |

**Total**: 24 MCP tools, 15 augur.yaml actions, 7 action YAMLs, 18 API routes (apple only), 22 pages, 0 dashboard.yaml manifests

### Issues Identified (corrected after manual verification)

**UI Compliance** (61/100):
- No GlassCard usage in /productivity/calendar (apple skill, 204 lines)
- No GlassCard usage in /productivity/email (apple skill)
- Eisenhower layout calls `getHubConfig('eisenhower')` which returns undefined — this is a **bug**, not a styling issue (sub-skill layouts must be passthrough or use parent hub config)

**Page Coverage** (88/100):
- 2/22 pages use mock/hardcoded data: Organize (hardcoded rules + setTimeout simulation), Duplicates (hardcoded file groups + setTimeout simulation)
- Drive page fetches real data via Google API — no fix needed

**API Completeness** (88/100 raw, adjusted 75/100):
- 16/18 API routes have real backend logic; 2 are health-check stubs
- **Critical gap**: All 18 API routes belong to the apple skill. Eisenhower and google-workspace have zero API routes
- Google-workspace actions reference endpoints like `/api/google-workspace/gmail` that don't exist
- Eisenhower wow effect needs `/api/productivity/eisenhower/tasks` which doesn't exist

**MCP Tool Wiring** (8/100 raw, adjusted ~35):
- Apple: 17 MCP tools registered, 4 `mcp_tools` blocks in action definitions
- Google-workspace: 7 MCP tools registered, `mcp_tool` refs on every augur.yaml action
- Eisenhower: 0 MCP tools registered (`mcp: tools: []`)
- Organizer: 0 MCP tools registered (`mcp: tools: []`)
- 7 action YAMLs across 3 skills lack individual `mcp_tool` keys
- 5/22 pages have `useActionRunner` calls with MCP dispatch

**Performance** (38/100 raw, adjusted 50):
- Overview page (960 lines) needs code splitting — the only genuinely oversized page
- Calendar (204 lines) and reminders (240 lines) are borderline but under 250
- No `dynamic()` imports anywhere in productivity hub

**User Value** (42/100 raw, adjusted 55):
- All 4 skills have `augur/data/` directories: apple (voice-memos, transcripts), eisenhower (tasks.yaml), google-workspace (briefings/), organizer (platform/)
- 16/18 API routes have real backend logic; 2 are health-check stubs
- Missing: unified data export, briefing history persistence

**Workflows** (0/100 raw, adjusted 30):
- 7 action YAMLs across 3 skills (apple: 3, eisenhower: 2, google-workspace: 2); organizer: 0
- Audit only searched apple skill — missed eisenhower and google-workspace
- No workflow chains connecting actions across skills

**Cross-Hub Connectivity** (80/100):
- Links to 6 other hubs: career, finance, health, lifestyle, creative, admin (12+ cross-hub hrefs)
- No src/lib service imports — hub uses href links but doesn't consume cross-hub data programmatically

**Action Buttons** (0/100 raw, adjusted 25):
- Apple overview has 6 Quick Action buttons via `useActionRunner`
- Eisenhower inbox has `useActionRunner` for task routing
- Google-workspace has 3 files with `useActionRunner` (EmailDetail, GmailToolbar, AiActions)
- Organizer has zero action buttons

**Wow Effect** (0/100):
- No unified workflow combining multiple data sources
- Individual actions exist but no orchestrated demo flow

### Bugs Not in Original Audit

**Tab href routing bug** (3 sub-skills):
- Eisenhower tabs use `/eisenhower/do-first` instead of `/productivity/eisenhower/do-first`
- Google-workspace tabs use `/google-workspace/gmail` instead of `/productivity/google-workspace/gmail`
- Organizer tabs use `/organizer/organize` instead of `/productivity/organizer/organize`
- Only apple (hub owner) has correct hrefs using `/productivity/notes` etc.
- These broken hrefs cause 404s when clicking sub-skill tabs

**Missing dashboard.yaml manifests** (all 4 skills):
- Zero dashboard.yaml files exist for any productivity skill
- mount-plugins.ts requires dashboard.yaml for plugin discovery — these skills mount via legacy/fallback path only

**Stale google-workspace API URLs**:
- Google-workspace action YAMLs reference `/api/google-workspace/gmail` but no such route exists
- All API routes are under `/api/productivity/` (apple skill only)

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Bug Fixes** (prerequisite — blocks all other work):
- Fix "Eisenhower hub configuration not found" error: layout.tsx calls `getHubConfig('eisenhower')` but eisenhower is a sub-skill, not a hub. Change to passthrough layout (`<>{children}</>`) per ADR-131 sub-skill layout pattern
- Fix tab href routing in 3 sub-skills: eisenhower (`/eisenhower/*` -> `/productivity/eisenhower/*`), google-workspace (`/google-workspace/*` -> `/productivity/google-workspace/*`), organizer (`/organizer/*` -> `/productivity/organizer/*`)
- Fix services fetch 404 (returning HTML instead of JSON) — likely stale API URL missing hub prefix
- Fix google-workspace stale API URLs: `/api/google-workspace/gmail` -> `/api/productivity/google-workspace/gmail` (or create routes at expected paths)

**Wow Effect — Smart Daily Briefing** (current: 0/100, target: 95/100):
- Create `daily-briefing.yaml` action in `eisenhower/augur/data/actions/` with IDE dispatch
- Wire MCP tools: `apple-calendar-today`, `apple-list-reminders`, `google-gmail-list`, `apple-list-emails`
- Create eisenhower API routes: `/api/productivity/eisenhower/tasks` (CRUD), `/api/productivity/eisenhower/route` (quadrant routing)
- Build briefing summary component showing triaged results with source attribution
- Add graceful degradation when data sources are unavailable
- Cross-hub leverage: career (job emails), health (health reminders), finance (financial emails)

**MCP Tool Wiring** (current: ~35, target: 90+):
- Add `mcp_tool` refs to all 7 existing action YAMLs across 3 sub-skills
- Create 3 organizer action YAMLs (scan, organize, clean) — organizer needs MCP tools registered in augur.yaml first
- Wire eisenhower add-task/prioritize actions to MCP tools (requires MCP tool registration in eisenhower augur.yaml)

**Performance** (current: 50, target: 90+):
- Code-split overview page (960 lines) — extract calendar view, voice recorder, screenshot gallery into lazy-loaded components via `dynamic()`
- Calendar (204L) and reminders (240L) are borderline — leave unless Phase 3 re-audit flags them

**User Value** (current: 55, target: 90+):
- All 4 skills already have `augur/data/` directories — no creation needed
- Add briefing history persistence to `eisenhower/augur/data/briefings/`
- Wire 2 health-check stubs to real MCP-backed logic
- Add data export capabilities (tasks JSON, briefing history)

**Workflows** (current: 30, target: 90+):
- 7 action YAMLs exist across 3 skills; organizer has 0 — add 3 organizer actions
- Add workflow chains: daily-briefing -> eisenhower-route -> calendar-schedule
- Existing eisenhower `prioritize.yaml` needs chain wiring to inbox

**Action Buttons** (current: 25, target: 90+):
- Apple overview + eisenhower inbox + google-workspace already have `useActionRunner`
- Add action buttons to eisenhower overview (Add Task, Daily Briefing, Prioritize)
- Add action buttons to organizer pages (Scan, Organize, Clean)

### Phase 2: Completeness & Sub-Skill Infrastructure

**Dashboard.yaml Manifests** (all 4 skills):
- Create dashboard.yaml for apple (hub owner — registers all hub-level tabs and cross-skill actions)
- Create dashboard.yaml for eisenhower, google-workspace, organizer (sub-skill manifests)
- Ensure mount-plugins.ts discovers all 4 skills properly via dashboard.yaml

**UI Compliance** (current: 61, target: 90+):
- Add GlassCard to `/productivity/calendar` (apple skill, 204 lines)
- Add GlassCard to `/productivity/email` (apple skill)
- Note: eisenhower layout bug is fixed in Phase 1 bug fixes — not a UI compliance issue

**Google-Workspace API Routes**:
- Create `/api/productivity/google-workspace/gmail` (calls `google-gmail-list` MCP tool)
- Create `/api/productivity/google-workspace/calendar` (calls `google-calendar-list` MCP tool)
- Update google-workspace augur.yaml action endpoints to use new routes

### Phase 3: Polish & Data Quality

**Page Coverage** (current: 88, target: 90+):
- 2 pages use mock/hardcoded data: Organize (hardcoded rules + setTimeout simulation), Duplicates (hardcoded file groups + setTimeout simulation)
- Replace with real API fetching — organizer needs new API routes

**API Completeness** (current: 75 adjusted, target: 90+):
- 2/18 API routes are stubs: `/api/productivity/health` (apple), `/api/productivity/organizer/health` (organizer)
- Wire to real MCP-backed health checks

**Cross-Hub Connectivity** (current: 80, target: 90+):
- Links to 6 hubs already exist (career, finance, health, lifestyle, creative, admin)
- Add src/lib service imports for cross-hub data: career (job email filtering), health (health reminder context), finance (financial email tagging)

## Consequences

### Positive

- Productivity hub upgraded from 48/100 (adjusted) to 90+ across all 10 dimensions
- Critical bugs fixed: eisenhower layout error, tab routing in 3 sub-skills, stale API URLs
- Killer demo: Smart Daily Briefing — one-click morning workflow combining calendar + reminders + email into prioritized Eisenhower matrix
- All 4 sub-skills get dashboard.yaml manifests for proper mount-plugins discovery
- Eisenhower and google-workspace gain API routes (currently have zero)

### Negative

- Requires creating API routes for eisenhower and google-workspace from scratch
- Organizer skill needs MCP tool registration before action buttons can be wired
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing apple skill functionality remains untouched
- Audit report stored for trend tracking
- Raw vs adjusted gap (41 vs 48) informs audit engine calibration — multi-skill discovery needs fix

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
Manual review improved: adjusted scores, hub architecture table, tab href bug discovery, API route gap analysis, dashboard.yaml manifest requirement.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- ADR-148: AI hub hardening (reference for adjusted scores, sub-skill integration, phase structure)
- ADR-131: AI hub platform hardening (sub-skill layout pattern: passthrough)
- Audit report: `plugins/dev/skills/frontend/augur/data/hardening-reports/productivity_20260225.yaml`
- Audit timestamp: 2026-02-25T12:10:52.008108

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065. Manually revised.

You are implementing **ADR-156: Productivity Hardening**.

Read the full ADR: `docs/decisions/ADR-156-productivity-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-156-productivity-hardening", description="Implementing ADR-156: Productivity Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-156-productivity-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{{role}}' on the {team_name} team.
        Read your profile: .claude/agents/{{role}}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-156-productivity-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE for 1.0 (blocker), then PARALLEL for 1.1-1.6

| Step | Agent | Tier | Blocks | Task | Files |
|------|-------|------|--------|------|-------|
| 1.0 | developer | high | 1.1-1.6 | Fix 4 blocking bugs: (a) Eisenhower layout — change `getHubConfig('eisenhower')` to passthrough `<>{children}</>`. (b) Tab href routing — fix all hrefs in eisenhower/google-workspace/organizer augur.yaml from `/skill/*` to `/productivity/skill/*`. (c) Services fetch 404 — find and fix stale API URL. (d) Google-workspace stale API URLs — action YAMLs reference `/api/google-workspace/` which doesn't exist. | `plugins/productivity/skills/eisenhower/augur/dashboard/layout.tsx`, `plugins/productivity/skills/eisenhower/augur.yaml`, `plugins/productivity/skills/google-workspace/augur.yaml`, `plugins/productivity/skills/organizer/augur.yaml` |
| 1.1 | developer | high | -- | Implement Smart Daily Briefing wow effect: Create `daily-briefing.yaml` action in eisenhower with IDE dispatch. Wire MCP tools (`apple-calendar-today`, `apple-list-reminders`, `google-gmail-list`, `apple-list-emails`). Create eisenhower API routes (`/api/productivity/eisenhower/tasks`, `/api/productivity/eisenhower/route`). Build briefing summary GlassCard component with source attribution and graceful degradation. | `plugins/productivity/skills/eisenhower/augur/data/actions/daily-briefing.yaml`, `plugins/productivity/skills/eisenhower/augur/dashboard/`, `plugins/productivity/skills/eisenhower/augur/api/` |
| 1.2 | devops | medium | -- | Wire MCP tool refs: Add `mcp_tool` key to all 7 existing action YAMLs. Register MCP tools in eisenhower augur.yaml (currently `tools: []`) — at minimum `eisenhower-add-task`, `eisenhower-prioritize`. Create 3 new organizer action YAMLs (scan, organize, clean) — requires registering MCP tools in organizer augur.yaml first. | `plugins/productivity/skills/*/augur/data/actions/*.yaml`, `plugins/productivity/skills/eisenhower/augur.yaml`, `plugins/productivity/skills/organizer/augur.yaml` |
| 1.3 | frontend | medium | -- | Code-split apple overview page (960 lines): Extract calendar section, voice recorder section, screenshot gallery, and quick actions grid into lazy-loaded components via `dynamic()`. Target: overview < 300 lines. Calendar (204L) and reminders (240L) — leave as-is. | `plugins/productivity/skills/apple/augur/dashboard/page.tsx` |
| 1.4 | developer | medium | -- | Add workflow chains: daily-briefing -> eisenhower-route -> calendar-schedule. Wire existing `prioritize.yaml` chain to inbox tasks. Add `route-all-auto.yaml` chain from inbox to all quadrants. | `plugins/productivity/skills/eisenhower/augur/data/actions/`, `plugins/productivity/skills/eisenhower/augur/data/chains/` |
| 1.5 | frontend | medium | -- | Add action buttons: Eisenhower overview (Add Task, Daily Briefing, Prioritize via `useActionRunner`). Organizer overview (Scan, Organize, Clean). Consistent GlassCard action areas with dispatch mode badges. | `plugins/productivity/skills/eisenhower/augur/dashboard/page.tsx`, `plugins/productivity/skills/organizer/augur/dashboard/page.tsx` |

#### Phase 2: Completeness & Sub-Skill Infrastructure
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | devops | medium | Create dashboard.yaml manifests for all 4 skills: apple (hub owner — registers hub-level tabs and cross-skill actions), eisenhower (sub-skill manifest), google-workspace (sub-skill manifest), organizer (sub-skill manifest). Verify mount-plugins.ts discovers all 4. | `plugins/productivity/skills/*/dashboard.yaml` |
| 2.2 | frontend | medium | Fix UI Compliance: Add GlassCard wrappers + `glass-panel p-6` root to `/productivity/calendar` and `/productivity/email` (apple skill). Verify eisenhower pages render correctly after layout fix. | `plugins/productivity/skills/apple/augur/dashboard/calendar/page.tsx`, `plugins/productivity/skills/apple/augur/dashboard/email/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.3 | developer | medium | Create google-workspace API routes (MCP-first): `/api/productivity/google-workspace/gmail` (calls `google-gmail-list`), `/api/productivity/google-workspace/calendar` (calls `google-calendar-list`). Update google-workspace augur.yaml action endpoints to reference new routes. | `plugins/productivity/skills/google-workspace/augur/api/`, `plugins/productivity/skills/google-workspace/augur.yaml` |

#### Phase 3: Polish & Data Quality
**Strategy**: PARALLEL (all independent)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Replace mock data in Organize page (hardcoded rules + setTimeout) and Duplicates page (hardcoded file groups + setTimeout) with real API fetching. Create organizer API routes if needed. | `plugins/productivity/skills/organizer/augur/dashboard/organize/page.tsx`, `plugins/productivity/skills/organizer/augur/dashboard/duplicates/page.tsx` |
| 3.2 | developer | low | Implement real MCP-backed logic in 2 health-check stubs: apple health (source: `apple/augur/api/health/route.ts`) and organizer health (source: `organizer/augur/api/health/route.ts`). | `plugins/productivity/skills/apple/augur/api/health/route.ts`, `plugins/productivity/skills/organizer/augur/api/health/route.ts` |
| 3.3 | developer | medium | Add src/lib service imports for cross-hub data consumption: career (job email filtering), health (health reminder context), finance (financial email tagging). Wire into Daily Briefing and overview pages. | `plugins/productivity/skills/eisenhower/augur/dashboard/`, `plugins/productivity/skills/apple/augur/dashboard/page.tsx` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions (`pytest tests/src/`, `npm run build`) |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/productivity in Chrome MCP. Screenshot each sub-skill area (apple overview, eisenhower matrix, google-workspace gmail, organizer). Verify: (a) eisenhower no longer shows "config not found", (b) tab navigation works in all 4 sub-skills, (c) zero console errors |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in action YAMLs against registered tools in `mcp/__init__.py`. Verify all 4 dashboard.yaml manifests are discovered by mount-plugins. |
| V.4 | architect | low | Verify ADR intent matches implementation: Daily Briefing is demo-ready, all 4 sub-skills have working navigation, organizer has real data |

### Completion Criteria

**Dimension targets** (all >= 90/100 on re-audit):
- [ ] Wow Effect: 0 -> 90+ (Smart Daily Briefing demo-ready with cross-skill data)
- [ ] MCP Tool Wiring: ~35 -> 90+ (all action YAMLs have `mcp_tool` refs; eisenhower + organizer have MCP tools registered)
- [ ] Performance: 50 -> 90+ (overview page code-split, no page > 300 lines)
- [ ] User Value: 55 -> 90+ (briefing history persisted, data export available)
- [ ] Workflows: 30 -> 90+ (10+ action YAMLs, 3 workflow chains wired)
- [ ] Action Buttons: 25 -> 90+ (buttons on all sub-skill overview pages)
- [ ] UI Compliance: 61 -> 90+ (GlassCard on calendar + email, eisenhower layout fixed)
- [ ] Page Coverage: 88 -> 90+ (Organize + Duplicates pages use real data)
- [ ] API Completeness: 75 -> 90+ (eisenhower + google-workspace have API routes, health stubs real)
- [ ] Cross-Hub Connectivity: 80 -> 90+ (src/lib service imports for career, health, finance)

**Bug fixes (blockers):**
- [ ] Eisenhower layout no longer shows "hub configuration not found" error
- [ ] Tab navigation works in all 4 sub-skills (hrefs prefixed with `/productivity/`)
- [ ] Google-workspace actions reference valid API routes
- [ ] Services fetch returns JSON (not HTML 404)

**Sub-skill infrastructure:**
- [ ] All 4 skills have dashboard.yaml manifests
- [ ] Eisenhower has API routes (`/api/productivity/eisenhower/tasks`, `/api/productivity/eisenhower/route`)
- [ ] Google-workspace has API routes (`/api/productivity/google-workspace/gmail`, `/api/productivity/google-workspace/calendar`)
- [ ] Eisenhower and organizer have MCP tools registered in augur.yaml
- [ ] Organizer has 3 action YAMLs (scan, organize, clean)

**Structural:**
- [ ] All phases executed (Phase 1 -> Phase 2 -> Phase 3 -> Verification)
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: all 4 sub-skill areas render with zero console errors
- [ ] MCP validation: all tool references in action YAMLs resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-156 status updated to Accepted
