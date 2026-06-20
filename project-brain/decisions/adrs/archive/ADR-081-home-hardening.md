---
status: Implemented
date: '2026-02-12'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- smart
- home
- hardening
superseded_by: null
---

# ADR-081: Smart Home Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 60/100 | 12% | significant-gaps | No GlassCard usage in /home/climate |
| 2 | Page Coverage | 80/100 | 10% | needs-work | 2/7 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 20/100 | 12% | critical | No actions defined — no API needed but hub is passive |
| 4 | MCP Tool Wiring | 20/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 30/100 | 10% | critical | Score capped at 60/100 — runtime telemetry needed for ful... |
| 6 | User Value | 0/100 | 15% | critical | No data directory — hub produces no persisted data |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 22/100 (major-rebuild)

## Wow Effect: Live Light Control

> Toggle Hue lights on/off, adjust brightness and color from the Lighting page in real-time using home-hue-set-light and home-hue-list-lights MCP tools

**Score**: 0/100

**Demo Flow**:
1. User opens /home/lighting page
2. API route calls home-hue-list-lights MCP tool to populate light list with real state
3. Each light card shows toggle, brightness slider, and color picker
4. User toggles a light — API route calls home-hue-set-light with on/off
5. User adjusts brightness — debounced API call updates light in real-time
6. User picks a color — API call changes light color, card reflects new state
7. Light state auto-refreshes every 5 seconds via React Query polling

**Current state**: Lighting page shows empty state with hardcoded zeros
**Gap to demo-ready**: Need API routes, React Query bindings, and interactive light card components

**Cross-hub leverage**: Pulls data from Eisenhower hub — could trigger "Focus Mode" scene from task view, Lifestyle hub — could link routines to daily schedule

**Other candidates**:
- One-Click Scene (0/100, )
- Sonos Now Playing (0/100, )
- Device Dashboard (0/100, )

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Smart Home** (http://localhost:3000/home) on 2026-02-12.
Composite score: **22/100**.

### Issues Identified

**UI Compliance** (60/100):
- No GlassCard usage in /home/climate
- No interactive elements in /home/climate — static display only
- No loading states or error handling in /home/climate

**API Completeness** (20/100):
- No actions defined — no API needed but hub is passive

**MCP Tool Wiring** (20/100):
- No explicit MCP tool references in actions/modals
- MCP module registered with 8 tools

**Performance** (30/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (0/100):
- No data directory — hub produces no persisted data
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity

**Wow Effect** (0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

## User Notes

Focus on Hue integration — Sonos is secondary. Prioritize Philips Hue device control throughout all phases.

## Decision

Implement hardening in three phases, ordered by severity and user impact. Hue integration is the primary focus; Sonos is secondary.

### Phase 1: Wow Effect & Critical Gaps (8 dimensions, target: >= 90 each)

**1A. API Routes + MCP Wiring** (API: 20 -> 90, MCP: 20 -> 90, Action Buttons: 0 -> 90)

Create API routes that proxy to the 8 existing MCP tools:

| Route | Method | MCP Tool | Purpose |
|-------|--------|----------|---------|
| `/api/home/lights` | GET | `home-hue-list-lights` | List all Hue lights with state |
| `/api/home/lights/[id]` | PUT | `home-hue-set-light` | Toggle, brightness, color |
| `/api/home/scenes` | GET | `home-hue-list-scenes` | List available Hue scenes |
| `/api/home/scenes/[id]` | POST | `home-hue-activate-scene` | Activate a scene |
| `/api/home/speakers` | GET | `home-sonos-list` | List Sonos speakers |
| `/api/home/speakers/[id]/playback` | POST | `home-sonos-play` | Play/pause/next/prev |
| `/api/home/speakers/[id]/volume` | PUT | `home-sonos-volume` | Set volume |
| `/api/home/speakers/[id]/status` | GET | `home-sonos-status` | Get playback status |

Add action buttons in `dashboard.yaml`:

| Action | Flow | Description |
|--------|------|-------------|
| `all-lights-off` | `fast` | Turn off all Hue lights |
| `activate-scene` | `fast` | Activate a Hue scene by ID |
| `toggle-light` | `fast` | Toggle a specific light on/off |

Wire MCP tool references in `dashboard.yaml` `mcp_tools:` section.

**1B. Wow Effect: Live Light Control** (Wow: 0 -> 90)

Replace the static Lighting page (`plugins/home/skills/home-automation/dashboard/lighting/page.tsx`) with:
- React Query hook fetching `/api/home/lights` with 5s polling interval
- Light card component with: toggle switch, brightness slider (0-254), color picker
- Each interaction calls `/api/home/lights/[id]` PUT with debounced updates (300ms for brightness/color)
- Loading skeletons while fetching, error toast on API failure
- Scene quick-buttons at top that call `/api/home/scenes/[id]` POST

**1C. User Value & Data Layer** (User Value: 0 -> 90)

- Create `plugins/consulting/home/` directory for persisted state (favorites, custom scenes, room assignments)
- Overview page fetches real data: light count from `/api/home/lights`, speaker count from `/api/home/speakers`
- Add "last seen" state caching so pages show stale data while refreshing

**1D. Workflows** (Workflows: 0 -> 90)

Define action flows in `dashboard.yaml`:
- `set-scene-and-music`: Activate a Hue scene + set Sonos to matching playlist
- `all-off-goodnight`: Turn off all lights + pause all speakers
- `focus-mode`: Set lights to "Concentrate" scene + lower volume

**1E. Cross-Hub Connectivity** (Cross-Hub: 0 -> 90)

- Link from Eisenhower "Do First" tasks to "Focus Mode" scene
- Link from Lifestyle daily routines to home automation routines
- Add "Smart Home" widget to the main dashboard overview
- Import health/lifestyle schedule data to auto-suggest routines

### Phase 2: UI Compliance (target: >= 90)

**UI Compliance** (60 -> 90):

Across all 7 pages:
- Replace plain `div` cards with `GlassCard` from `@/components/ui/glass-card`
- Add loading skeletons (React Suspense or `isLoading` states from React Query)
- Add error boundary with retry button on API failures
- Add interactive elements to climate, devices, and lighting pages (currently static display only)
- Follow design standards from `plugins/dev/skills/frontend/references/design-standards.md`

### Phase 3: Page Coverage Polish (target: >= 90)

**Page Coverage** (80 -> 90):

- Overview page: Replace hardcoded stats with real API calls to `/api/home/lights` and `/api/home/speakers`
- Scenes page: Replace hardcoded preset list with real scenes from `/api/home/scenes`

## Consequences

### Positive

- Smart Home hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Live Light Control

### Negative

- Requires implementation effort across 10 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `home` hub audit
- Audit timestamp: 2026-02-12T09:33:54.421059

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-081: Smart Home Hardening**.

Read the full ADR: `docs/decisions/ADR-081-home-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-081-home-hardening", description="Implementing ADR-081: Smart Home Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-081-home-hardening", name="{role}",
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

**Team name**: `adr-081-home-hardening`

#### Phase 1: API + MCP + Wow Effect (PARALLEL where possible)
**Strategy**: Steps 1.1-1.3 PARALLEL, then 1.4-1.6 PARALLEL (depend on API routes), then 1.7 (depends on pages)

| Step | Agent | Tier | Task | Files | Depends |
|------|-------|------|------|-------|---------|
| 1.1 | developer | medium | Create 8 API routes proxying to MCP tools (lights CRUD, scenes, speakers) | `plugins/home/skills/home-automation/api/lights/route.ts`, `plugins/home/skills/home-automation/api/lights/[id]/route.ts`, `plugins/home/skills/home-automation/api/scenes/route.ts`, `plugins/home/skills/home-automation/api/scenes/[id]/route.ts`, `plugins/home/skills/home-automation/api/speakers/route.ts`, `plugins/home/skills/home-automation/api/speakers/[id]/playback/route.ts`, `plugins/home/skills/home-automation/api/speakers/[id]/volume/route.ts`, `plugins/home/skills/home-automation/api/speakers/[id]/status/route.ts` | — |
| 1.2 | developer | low | Add action buttons + MCP tool refs + workflows to dashboard.yaml | `plugins/home/skills/home-automation/dashboard.yaml` | — |
| 1.3 | developer | low | Create `plugins/consulting/home/` data dir with README + initial config | `plugins/consulting/home/README.md`, `plugins/consulting/home/config.yaml` | — |
| 1.4 | frontend | high | Build Live Light Control — interactive Lighting page with React Query, light cards (toggle/brightness/color), scene quick-buttons, 5s polling | `plugins/home/skills/home-automation/dashboard/lighting/page.tsx` | 1.1 |
| 1.5 | frontend | medium | Rewrite Overview page with real API data (light count, speaker count, room status from actual devices) + quick control buttons wired to API | `plugins/home/skills/home-automation/dashboard/page.tsx` | 1.1 |
| 1.6 | frontend | medium | Rewrite Scenes page — fetch real scenes from API, add activate buttons, remove hardcoded presets | `plugins/home/skills/home-automation/dashboard/scenes/page.tsx` | 1.1 |
| 1.7 | frontend | medium | Add cross-hub links: Eisenhower "Focus Mode" link, Lifestyle routines link, Smart Home widget reference | `plugins/home/skills/home-automation/dashboard/page.tsx`, `plugins/home/skills/home-automation/dashboard/routines/page.tsx` | 1.5 |

#### Phase 2: UI Compliance (PARALLEL — independent pages)
**Strategy**: PARALLEL (each page is independent)

| Step | Agent | Tier | Task | Files | Depends |
|------|-------|------|------|-------|---------|
| 2.1 | frontend | medium | Migrate climate page to GlassCard + add loading/error states + interactive thermostat controls | `plugins/home/skills/home-automation/dashboard/climate/page.tsx` | Phase 1 |
| 2.2 | frontend | medium | Migrate devices page to GlassCard + add loading/error states + device category cards | `plugins/home/skills/home-automation/dashboard/devices/page.tsx` | Phase 1 |
| 2.3 | frontend | medium | Migrate security page to GlassCard + add loading/error states | `plugins/home/skills/home-automation/dashboard/security/page.tsx` | Phase 1 |
| 2.4 | frontend | medium | Migrate routines page to GlassCard + add loading/error states | `plugins/home/skills/home-automation/dashboard/routines/page.tsx` | Phase 1 |

#### Phase 3: Performance + Coverage Polish
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files | Depends |
|------|-------|------|------|-------|---------|
| 3.1 | developer | medium | Add React Query cache configuration, stale-while-revalidate, error boundaries, Suspense boundaries for all pages | `plugins/home/skills/home-automation/dashboard/layout.tsx`, all page files | Phase 2 |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/home in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

**Dimension targets** (all must reach >= 90/100):
- [ ] Wow Effect: 0 -> 90 (Live Light Control functional with real Hue devices)
- [ ] API Completeness: 20 -> 90 (8 API routes proxying to MCP tools)
- [ ] MCP Tool Wiring: 20 -> 90 (all 8 tools referenced in dashboard.yaml)
- [ ] Action Buttons: 0 -> 90 (all-lights-off, activate-scene, toggle-light wired)
- [ ] User Value: 0 -> 90 (data dir exists, pages fetch real data, state persisted)
- [ ] Workflows: 0 -> 90 (3+ action flows defined and functional)
- [ ] Cross-Hub Connectivity: 0 -> 90 (links to Eisenhower + Lifestyle hubs)
- [ ] Performance: 30 -> 90 (React Query caching, Suspense, error boundaries)
- [ ] UI Compliance: 60 -> 90 (GlassCard on all pages, loading/error states)
- [ ] Page Coverage: 80 -> 90 (zero hardcoded mock data remaining)

**Verification**:
- [ ] All phases executed (12 steps + 4 verification)
- [ ] `npm run build` in `src/dashboard/` passes clean
- [ ] `pytest tests/src/` passes
- [ ] Browser: each tab renders in Chrome MCP with zero console errors
- [ ] MCP: all tool refs in dashboard.yaml resolve to registered tools in `mcp/__init__.py`
- [ ] Re-run audit: `python3 plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py --url http://localhost:3000/home` -> composite >= 85
- [ ] ADR-081 status updated to Accepted
