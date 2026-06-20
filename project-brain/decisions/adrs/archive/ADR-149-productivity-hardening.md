---
status: Superseded
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
- ADR-156 (supersedes this)
hub: null
tags:
- productivity
- hardening
superseded_by: null
---

# ADR-149: Productivity Hardening

## Audit Summary

| # | Dimension | Raw | Adj.¹ | Weight | Status | Key Finding |
|---|-----------|-----|-------|--------|--------|-------------|
| 1 | UI Compliance | 61 | 61 | 12% | significant-gaps | No GlassCard in /productivity/calendar, /email; 6 google-workspace findings |
| 2 | Page Coverage | 88 | 88 | 10% | needs-work | 3/19 pages use mock/hardcoded data (Organize, Duplicates, Drive) |
| 3 | API Completeness | 88 | 88 | 12% | needs-work | 2/18 API routes are stubs (health endpoints) |
| 4 | MCP Tool Wiring | 8 | ~35 | 10% | critical | 17 MCP tools declared in augur.yaml; actions reference them; scanner found 6/22 pages with calls |
| 5 | Performance | 38 | 38 | 10% | critical | Main page is 960 lines with no code splitting |
| 6 | User Value | 42 | ~55 | 15% | needs-work | Data dir exists (augur/data/) but scanner missed it; 16/22 pages fetch real data |
| 7 | Workflows | 0 | ~45 | 8% | critical | 6 actions in augur.yaml + 3 action YAMLs exist; scanner found 0 (checks dashboard.yaml not augur.yaml) |
| 8 | Cross-Hub Connectivity | 80 | 80 | 5% | needs-work | Links to 5 hubs; 13 cross-hub connections; no shared service imports |
| 9 | Action Buttons | 0 | ~50 | 8% | critical | QuickActionsCard renders 6 buttons + 2 modals; scanner found 0 (checks dashboard.yaml) |
| 10 | Wow Effect | 0 | ~55 | 10% | critical | Triage Inbox chains 4 MCP tools — scanner missed because actions aren't in dashboard.yaml |

¹ **Adjusted scores** account for static-scan under-detection of existing functionality. Raw scores reflect what the audit engine found; adjusted scores reflect manual verification of actual hub state. The audit engine scans `dashboard.yaml` for actions but this hub uses `augur.yaml` (v3.0 format) where all actions and MCP tools are properly declared.

**Raw Composite**: 41/100 (major-rebuild) | **Adjusted Composite**: ~56/100 (needs-work)

## Wow Effect: Triage Inbox

> Click "Triage Inbox" — AI refreshes the Apple Notes inbox and Desktop, reads all items, classifies each as a task or reference, creates Reminders for tasks and Notes for references, then reports what was routed where with confidence scores.

**Score**: 55/100 (current) → 95/100 (target)

**Demo Flow**:
1. User clicks "Triage Inbox" button in QuickActionsCard on /productivity
2. IDE agent dispatches with `useActionRunner` (dispatch: ide)
3. Agent calls `apple-refresh-inbox` to scan Notes inbox + Desktop for new items
4. Agent calls `apple-read-notes` to retrieve all inbox items
5. For each item, AI classifies as task (→ `apple-create-reminder`) or reference (→ `apple-create-note`)
6. Agent reports routing summary: "3 tasks → Reminders, 2 references → Notes, 1 archived"
7. Page auto-refreshes showing updated inbox counts, new reminders, new notes

**Current state**: Action defined in augur.yaml with 4 MCP tools (apple-refresh-inbox, apple-read-notes, apple-create-reminder, apple-create-note). Button rendered in page.tsx via QuickActionsCard. Handler dispatches via `useActionRunner`.

**Gap to demo-ready** (3 items):
1. **Progress indicators**: Add per-item triage progress (scanning → classifying → routing) with animated transitions in a collapsible results panel below the inbox card
2. **Results panel**: Collapsible GlassCard showing triage results as a structured table (item, source, classification, destination, confidence) — not just a toast notification
3. **Inbox diff view**: Before/after comparison showing inbox items that moved, with color-coded badges (task=orange, reference=blue, archived=gray)

**Cross-hub leverage**: Pulls from /health for wellbeing-related task routing, /career for work-related item classification

**Other candidates**:
- Quick Capture (50/100, ide) — voice→transcribe→extract→create reminders/notes
- Transcribe Memo (40/100, ide) — voice memo→transcript→key points
- Refresh Inbox (35/100, fire) — simple scan, no AI classification

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Productivity** (http://localhost:3000/productivity) on 2026-02-25.
Composite score: **41/100** (raw), **~56/100** (adjusted).

### Hub Topology

The productivity hub contains **4 sub-skills** that all contribute pages:

| Sub-Skill | Plugin Path | MCP Tools | Actions | Pages | State |
|-----------|------------|-----------|---------|-------|-------|
| **apple** | `plugins/productivity/skills/apple/` | 17 | 6 (augur.yaml) + 3 (YAMLs) | 6 + overview | Real — live Apple integrations |
| **eisenhower** | `plugins/productivity/skills/eisenhower/` | 0 | 2 (augur.yaml) | 1 | Minimal — stub page.tsx (8 lines) |
| **google-workspace** | `plugins/productivity/skills/google-workspace/` | 7 | 7 (augur.yaml) | 4 | Mixed — some pages have real data, some mock |
| **organizer** | `plugins/productivity/skills/organizer/` | 0 | 0 | 3 | Stub — hardcoded data |

### Issues Identified

**UI Compliance** (61/100):
- No GlassCard usage in /productivity/calendar
- Missing proper layout structure in /productivity/eisenhower
- No GlassCard usage in /productivity/email
- No GlassCard usage in /productivity/google-workspace/calendar
- Missing proper layout structure in /productivity/google-workspace/calendar, /docs, /drive
- No interactive elements in /productivity/google-workspace/calendar — static display only
- No loading states or error handling in /productivity/google-workspace/calendar

**MCP Tool Wiring** (8/100, adjusted ~35):
- 17 MCP tools declared in apple augur.yaml + 7 in google-workspace augur.yaml
- Actions reference MCP tools but scanner checked dashboard.yaml (doesn't exist)
- 6/22 pages have MCP tool calls — remaining pages need wiring

**Performance** (38/100):
- Main page (960 lines): /productivity — needs code splitting
- No code splitting for /productivity/calendar (204 lines but uses no lazy loading)
- No code splitting for /productivity/reminders

**User Value** (42/100, adjusted ~55):
- Data directory exists at `plugins/productivity/skills/apple/augur/data/` (config, voice-memos, actions) — scanner missed it
- 16/22 pages fetch real data (good baseline)
- 3/18 API routes have real backend logic via MCP — most routes use createAPIRoute()

**Workflows** (0/100, adjusted ~45):
- 6 actions defined in apple augur.yaml (quick-capture, create-note, refresh-inbox, create-reminder, transcribe-memo, triage-inbox)
- 3 action YAML files in augur/data/actions/ (create-note.yaml, create-reminder.yaml, refresh-inbox.yaml)
- Scanner found 0 because it checks dashboard.yaml, not augur.yaml

**Action Buttons** (0/100, adjusted ~50):
- QuickActionsCard in page.tsx renders 6 action buttons with handlers
- Modal dialogs for create-note and create-reminder
- QuickCaptureModal for voice recording
- Scanner found 0 because it checks dashboard.yaml actions section

**Wow Effect** (0/100, adjusted ~55):
- Triage Inbox chains 4 MCP tools with AI classification
- Quick Capture chains 4 MCP tools (voice→transcribe→extract→create)
- Both fully defined in augur.yaml with dispatch and context fields

## Decision

Implement hardening in four phases (Phase 0 blocking, then 1→2→3), ordered by severity and user impact.

### Phase 0: Browser Validation (Blocker)

Phase 0 is mandatory first — verify all sub-skill pages load cleanly before adding features.

- Open http://localhost:3000/productivity in Chrome MCP
- Navigate to each of the 19 tabs (overview, notes, reminders, calendar, email, voice, screenshots, eisenhower, google-workspace/*, organizer/*)
- Check console for runtime errors on each page
- Fix any broken tabs, missing imports, hydration errors, or 404s before proceeding

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect — Triage Inbox** (current: ~55/100, target: 95/100):
- Add per-item triage progress panel (scanning → classifying → routing) with animated transitions
- Add collapsible GlassCard results panel below inbox card showing structured triage table (item, source, classification, destination, confidence)
- Add inbox diff view with before/after comparison and color-coded badges
- Wire "Triage Inbox" button to show real-time progress during IDE dispatch

**MCP Tool Wiring + Workflows + Action Buttons** (consolidated — same work):
- Root cause: All actions are in augur.yaml but the audit engine checks dashboard.yaml
- Ensure all 6 apple actions, 2 eisenhower actions, and 7 google-workspace actions are properly registered in their respective augur.yaml files
- Add `mcp_tool:` refs to action YAML files that invoke MCP tools
- Wire action buttons to eisenhower and google-workspace overview pages (currently stub pages with no buttons)
- Add workflow chains: triage-inbox → create-note/reminder → refresh-inbox, quick-capture → transcribe-memo → create-note

**Performance** (current: 38/100):
- Code-split apple/page.tsx (960 lines): Extract AppleStatsGrid, QuickActionsCard, InboxItemsCard, EventsCard, RemindersCard, RecentNotesCard, CrossHubLinks, ICloudStatusCard into lazy-loaded components
- Target: no page.tsx > 200 lines after split

### Phase 2: Sub-Skill Hardening & UI Compliance

**UI Compliance** (current: 61/100):
- Apple sub-pages: Add GlassCard wrappers to /productivity/calendar and /productivity/email
- Eisenhower: Replace stub page.tsx (8 lines) with proper GlassCard layout, loading states, error handling
- Google-workspace: Fix 6 findings across calendar, docs, drive pages — add GlassCard, layout structure, loading states, interactive elements
- Organizer: Add GlassCard wrappers and loading states to organize, duplicates, cleanup pages

**Sub-Skill Page Implementation**:
- Eisenhower page.tsx is 8 lines — needs real implementation (matrix view, task categorization, priority display)
- Google-workspace pages partially implemented — fix calendar, drive pages that mix real/mock data
- Organizer pages use hardcoded arrays — wire to API routes or MCP tools

### Phase 3: Polish & Cross-Hub

**Page Coverage** (current: 88/100):
- Replace mock data in Organize (hardcoded arrays), Duplicates (hardcoded arrays), Drive (mixed real/mock)
- Wire to existing API routes or create new routes backed by MCP tools

**API Completeness** (current: 88/100):
- 2 stub health endpoints: `/api/productivity/health`, `/api/productivity/organizer/health`
- Wire to actual MCP tool calls or service checks (not hardcoded {status: 'ok'})

**Cross-Hub Connectivity** (current: 80/100):
- Add shared service imports for cross-hub data consumption
- Wire cross-links: Eisenhower priority tasks → /health for wellbeing context, calendar events → /career for work scheduling
- Overview → aggregate stats from all 4 sub-skills via their APIs

## Consequences

### Positive

- Productivity hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo: Triage Inbox (AI reads inbox → classifies → routes to reminders/notes → reports)
- 4 sub-skills (apple, eisenhower, google-workspace, organizer) all brought to consistent quality
- Adjusted scoring methodology exposes static-scan under-detection for future audit improvements

### Negative

- Requires implementation effort across 4 phases with 11 execution steps
- Eisenhower and organizer sub-skills need significant page implementation work (currently stub/hardcoded)
- Google-workspace pages need mixed real/mock data resolved

### Neutral

- Existing working features (apple overview with 6 action buttons, voice recording, notes/reminders) remain untouched
- Audit report stored for trend tracking
- Adjusted composite (~56) vs raw (41) gap informs audit engine calibration

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065), then manually reviewed and corrected for audit under-detection of existing functionality.

## User Notes

The audit engine significantly underscores this hub. The apple skill has 6 working action buttons (QuickActionsCard), 2 modal dialogs (create-note, create-reminder), a Quick Capture modal with voice recording, 17 MCP tools, and 6 actions — all properly defined in augur.yaml. The scanner reports 0 for Workflows, Action Buttons, and Wow Effect because it checks dashboard.yaml (which doesn't exist) instead of augur.yaml (v3.0 format). Real scores are likely 15-25 points higher than reported for Workflows, Action Buttons, MCP Tool Wiring, and Wow Effect.

The hub has 4 sub-skills but the audit treats it as monolithic. Eisenhower and organizer are genuinely underdeveloped (8-line stub pages), but apple is functional with real Apple integrations.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `plugins/dev/skills/frontend/augur/data/hardening-reports/productivity_20260225.yaml`
- Audit timestamp: 2026-02-25T00:34:44.688901

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065, then manually corrected.

You are implementing **ADR-149: Productivity Hardening**.

Read the full ADR: `docs/decisions/ADR-149-productivity-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-149-productivity-hardening", description="Implementing ADR-149: Productivity Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-149-productivity-hardening", name="{role}",
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

**Team name**: `adr-149-productivity-hardening`

#### Phase 0: Browser Validation (Blocker)
**Strategy**: SINGLE — must complete before all other phases

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 0.1 | frontend | low | Open http://localhost:3000/productivity in Chrome MCP. Navigate to all 19 tabs (overview, notes, reminders, calendar, email, voice, screenshots, eisenhower, google-workspace/calendar, google-workspace/docs, google-workspace/drive, google-workspace overview, organizer/organize, organizer/duplicates, organizer/cleanup, organizer overview). Screenshot each page, check console for runtime errors. Report all broken tabs, missing imports, hydration errors, or 404s. |

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PARALLEL-then-PIPELINE

**Group A** (parallel — no file overlap):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Implement Wow Effect — Triage Inbox: Add per-item triage progress panel (scanning→classifying→routing) with animated transitions below inbox card. Add collapsible GlassCard results panel showing structured triage table (item, source, classification, destination, confidence). Add inbox diff view with before/after comparison and color-coded badges (task=orange, reference=blue, archived=gray). Wire "Triage Inbox" button to show real-time progress during IDE dispatch | `plugins/productivity/skills/apple/augur/dashboard/page.tsx`, `plugins/productivity/skills/apple/augur/dashboard/QuickCaptureModal.tsx` |
| 1.2 | devops | medium | Fix MCP Tool Wiring + Workflows + Action Buttons (consolidated): Verify all 6 apple actions, 2 eisenhower actions, and 7 google-workspace actions are registered in augur.yaml. Add `mcp_tool:` refs to action YAML files in `augur/data/actions/`. Add action buttons to eisenhower and google-workspace overview pages (currently stub pages with no buttons). Add workflow chains: triage-inbox→create-note/reminder→refresh-inbox, quick-capture→transcribe-memo→create-note | `plugins/productivity/skills/apple/augur.yaml`, `plugins/productivity/skills/apple/augur/data/actions/`, `plugins/productivity/skills/eisenhower/augur.yaml`, `plugins/productivity/skills/eisenhower/augur/dashboard/page.tsx`, `plugins/productivity/skills/google-workspace/augur.yaml`, `plugins/productivity/skills/google-workspace/augur/dashboard/page.tsx` |

**Group B** (after Group A — depends on action button changes):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.3 | frontend | medium | Fix Performance (38→90): Code-split apple/page.tsx (960 lines). Extract AppleStatsGrid, QuickActionsCard, InboxItemsCard, EventsCard, RemindersCard, RecentNotesCard, CrossHubLinks, ICloudStatusCard into separate files with dynamic imports. Target: no page.tsx > 200 lines after split | `plugins/productivity/skills/apple/augur/dashboard/page.tsx` |
| 1.4 | developer | medium | Fix User Value: Wire overview page to aggregate stats from all 4 sub-skill APIs. Ensure data directory at `plugins/productivity/skills/apple/augur/data/` is recognized by the audit scanner. Add persisted output from triage-inbox action (routing log) | `plugins/productivity/skills/apple/augur/dashboard/page.tsx`, `plugins/productivity/skills/apple/augur/data/` |

#### Phase 2: Sub-Skill Hardening & UI Compliance
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Fix UI Compliance for apple sub-pages: Add GlassCard wrappers to /productivity/calendar and /productivity/email. Ensure loading states and error handling follow design-standards.md | `plugins/productivity/skills/apple/augur/dashboard/calendar/page.tsx`, `plugins/productivity/skills/apple/augur/dashboard/email/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.2 | developer | medium | Eisenhower sub-skill hardening: Replace stub page.tsx (8 lines) with real implementation — Eisenhower matrix view (urgent/important 2x2 grid), task categorization, priority display, GlassCard layout, loading states. Wire to any existing augur.yaml actions | `plugins/productivity/skills/eisenhower/augur/dashboard/page.tsx`, `plugins/productivity/skills/eisenhower/augur.yaml` |
| 2.3 | developer | medium | Google-workspace sub-skill hardening: Fix 6 UI findings across calendar, docs, drive pages. Add GlassCard wrappers, layout structure, loading states, interactive elements. Fix mixed real/mock data in Drive page | `plugins/productivity/skills/google-workspace/augur/dashboard/calendar/page.tsx`, `plugins/productivity/skills/google-workspace/augur/dashboard/docs/page.tsx`, `plugins/productivity/skills/google-workspace/augur/dashboard/drive/page.tsx`, `plugins/productivity/skills/google-workspace/augur/dashboard/page.tsx` |
| 2.4 | developer | medium | Organizer sub-skill hardening: Replace hardcoded arrays in Organize and Duplicates pages with real data fetching. Add GlassCard wrappers, loading states. Wire to API routes or MCP tools | `plugins/productivity/skills/organizer/augur/dashboard/organize/page.tsx`, `plugins/productivity/skills/organizer/augur/dashboard/duplicates/page.tsx`, `plugins/productivity/skills/organizer/augur/dashboard/cleanup/page.tsx` |

#### Phase 3: Polish & Cross-Hub
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Fix Page Coverage (88→90): Verify all 19 pages fetch real data after Phase 2 sub-skill hardening. Replace any remaining mock/hardcoded data | `plugins/productivity/skills/*/augur/dashboard/` |
| 3.2 | developer | low | Fix API Completeness (88→90): Wire 2 stub health endpoints (`/api/productivity/health`, `/api/productivity/organizer/health`) to real MCP tool calls or service checks instead of hardcoded {status: 'ok'} | `plugins/productivity/skills/apple/augur/api/health/route.ts`, `plugins/productivity/skills/organizer/augur/api/health/route.ts` |
| 3.3 | developer | medium | Fix Cross-Hub Connectivity (80→90): Add shared service imports for cross-hub data. Wire cross-links: Eisenhower→/health for wellbeing context, calendar→/career for work scheduling. Overview→aggregate stats from all 4 sub-skill APIs | `plugins/productivity/skills/apple/augur/dashboard/page.tsx`, `plugins/productivity/skills/eisenhower/augur/dashboard/page.tsx` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/productivity in Chrome MCP, screenshot each tab, check console for runtime errors, verify Triage Inbox demo flow works end-to-end |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in augur.yaml files against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

**Dimension targets** (all >= 90/100 on re-audit):
- [ ] Wow Effect: ~55 → 90+ (Triage Inbox demo-ready with progress panel, results table, diff view)
- [ ] MCP Tool Wiring: ~35 → 90+ (all action YAMLs registered with `mcp_tool:` refs across 4 sub-skills)
- [ ] Performance: 38 → 90+ (no page.tsx > 200 lines, all large pages code-split)
- [ ] User Value: ~55 → 90+ (data directory recognized, overview aggregates from sub-skills, triage routing log)
- [ ] Workflows: ~45 → 90+ (all actions registered, 2 workflow chains wired)
- [ ] Action Buttons: ~50 → 90+ (buttons on all 4 sub-skill overview pages)
- [ ] UI Compliance: 61 → 90+ (GlassCard, loading states, error boundaries across all sub-skills)
- [ ] Page Coverage: 88 → 90+ (no mock data, all sub-skill pages implemented)
- [ ] API Completeness: 88 → 95+ (2 stub health endpoints wired to real backends)
- [ ] Cross-Hub Connectivity: 80 → 90+ (shared service imports, cross-links wired)

**Sub-skill integration:**
- [ ] Apple skill: code-split page.tsx, triage inbox wow effect, all actions wired
- [ ] Eisenhower: real page implementation (matrix view, task categorization)
- [ ] Google-workspace: all 4 pages have GlassCard, loading states, real data
- [ ] Organizer: hardcoded arrays replaced with real data fetching

**Structural:**
- [ ] Phase 0 browser validation passes with zero console errors
- [ ] All phases executed (Phase 0 → Phase 1 → Phase 2 → Phase 3 → Verification)
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: Triage Inbox demo flow works end-to-end in Chrome MCP
- [ ] MCP validation: all tool references in augur.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-149 status updated to Accepted
