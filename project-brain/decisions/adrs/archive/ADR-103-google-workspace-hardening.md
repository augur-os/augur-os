---
status: Implemented
date: '2026-02-15'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- google
- workspace
- hardening
superseded_by: null
---

# ADR-103: Google Workspace Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 57/100 | 12% | significant-gaps | No GlassCard usage in /google-workspace/calendar |
| 2 | Page Coverage | 58/100 | 10% | significant-gaps | 3/5 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 100/100 | 10% | good | 4 actions use API-wrapped MCP pattern |
| 5 | Performance | 41/100 | 10% | critical | Score capped at 60/100 — runtime telemetry needed for ful... |
| 6 | User Value | 47/100 | 15% | critical | 1 real data files found in google-workspace/ data dir |
| 7 | Workflows | 70/100 | 8% | needs-work | 7/7 actions have working backends |
| 8 | Cross-Hub Connectivity | 60/100 | 5% | significant-gaps | Links to 4 other hubs: /career, /content, /eisenhower, /f... |
| 9 | Action Buttons | 85/100 | 8% | needs-work | 5/7 actions are fully-wired |
| 10 | Wow Effect | 40/100 | 10% | critical | Best candidate: Summarize Today |

**Composite Score**: 66/100 (significant-gaps)

> **Architecture Note (ADR-103 learnings)**: Our MCP pattern uses API-wrapped routing (`tool: /api/{hub}/...`) rather than direct `mcp://` references. This keeps web as one client of MCP alongside CLI and IDEs. The hardening audit now correctly recognizes this pattern via the `mcp_tool` field.

## Wow Effect: Triage Inbox

> Automated email triage — fetches unread Gmail messages, categorizes by urgency and topic, and drafts reply suggestions for high-priority threads

**Score**: 30/100

**Demo Flow**:
1. User clicks 'Summarize Today'
2. IDE chat opens with context
3. AI generates response
4. User reviews and applies

**Current state**: 8 candidate actions evaluated
**Gap to demo-ready**: Good static foundation — run /harden with dashboard running to verify live behavior

**Cross-hub leverage**: Pulls data from career, content, eisenhower, finance

**Other candidates**:
- Refresh Inbox (40/100, fast_action)
- Refresh Calendar (40/100, fast_action)
- Extract Career Emails (40/100, llm_action)
- Draft Reply (40/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Google Workspace** (http://localhost:3000/google-workspace) on 2026-02-15.
Composite score: **60/100**.

### Issues Identified

**UI Compliance** (57/100):
- No GlassCard usage in /google-workspace/calendar
- No GlassCard usage in /google-workspace/docs
- Missing proper layout structure in /google-workspace/docs

**Page Coverage** (58/100):
- 3/5 pages use mock/hardcoded data instead of real fetching
- Mixed real/mock data in 'Overview' — still has hardcoded content
- Mixed real/mock data in 'Calendar' — still has hardcoded content

**MCP Tool Wiring** (50/100):
- No explicit MCP tool references in actions/modals
- 5/5 pages have MCP tool calls
- MCP module registered with 20 tools

**Performance** (41/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (47/100):
- 1 real data files found in google-workspace/ data dir
- 15/15 API routes have real backend logic
- 2/5 pages fetch real data

**Cross-Hub Connectivity** (60/100):
- Links to 4 other hubs: /career, /content, /eisenhower, /finance
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 1 connections

**Wow Effect** (40/100):
- Best candidate: Summarize Today
- Description: AI synthesizes today's emails, calendar events, and Drive activity into a structured daily briefing with priorities and action items
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 40/100):
- Best candidate: Summarize Today
- Description: AI synthesizes today's emails, calendar events, and Drive activity into a structured daily briefing with priorities and action items
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

**Performance** (current: 41/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (current: 47/100):
- 1 real data files found in google-workspace/ data dir
- 15/15 API routes have real backend logic
- 2/5 pages fetch real data

### Phase 2: Completeness

**UI Compliance** (current: 57/100):
- No GlassCard usage in /google-workspace/calendar
- No GlassCard usage in /google-workspace/docs
- Missing proper layout structure in /google-workspace/docs

**Page Coverage** (current: 58/100):
- 3/5 pages use mock/hardcoded data instead of real fetching
- Mixed real/mock data in 'Overview' — still has hardcoded content
- Mixed real/mock data in 'Calendar' — still has hardcoded content

**MCP Tool Wiring** (current: 50/100):
- No explicit MCP tool references in actions/modals
- 5/5 pages have MCP tool calls
- MCP module registered with 20 tools

**Cross-Hub Connectivity** (current: 60/100):
- Links to 4 other hubs: /career, /content, /eisenhower, /finance
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 1 connections

### Phase 3: Polish & Performance

**Workflows** (current: 70/100):
- 7/7 actions have working backends
- No chain workflows found — no automated multi-step flows

**Action Buttons** (current: 85/100):
- 5/7 actions are fully-wired
- 2/7 actions are frontend-only

## Consequences

### Positive

- Google Workspace hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Triage Inbox

### Negative

- Requires implementation effort across 9 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `google-workspace` hub audit
- Audit timestamp: 2026-02-15T12:51:06.405925

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-103: Google Workspace Hardening**.

Read the full ADR: `docs/decisions/ADR-103-google-workspace-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-103-google-workspace-hardening", description="Implementing ADR-103: Google Workspace Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-103-google-workspace-hardening", name="{role}",
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

**Team name**: `adr-103-google-workspace-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (40/100): Best candidate: Summarize Today | `plugins/productivity/skills/google-workspace/augur.yaml`, `plugins/productivity/skills/google-workspace/augur/` |
| 1.2 | frontend | medium | Fix Performance (41/100): Score capped at 60/100 — runtime telemetry needed for ful... | `plugins/productivity/skills/google-workspace/augur//page.tsx` |
| 1.3 | architect | high | Fix User Value (47/100): 1 real data files found in google-workspace/ data dir | `plugins/productivity/skills/google-workspace/augur.yaml` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.4 | frontend | medium | Fix UI Compliance (57/100): No GlassCard usage in /google-workspace/calendar | `plugins/productivity/skills/google-workspace/augur/calendar/page.tsx`, `plugins/productivity/skills/google-workspace/augur/docs/page.tsx`, `plugins/productivity/skills/google-workspace/augur/docs/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.5 | developer | medium | Fix Page Coverage (58/100): 3/5 pages use mock/hardcoded data instead of real fetching | `plugins/productivity/skills/google-workspace/augur/` |
| 2.6 | devops | low | Fix MCP Tool Wiring (50/100): No explicit MCP tool references in actions/modals | `plugins/productivity/skills/google-workspace/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 2.7 | developer | medium | Fix Cross-Hub Connectivity (60/100): Links to 4 other hubs: /career, /content, /eisenhower, /f... | `plugins/productivity/skills/google-workspace/augur/` |

#### Phase 3: Polish & Performance
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.8 | developer | medium | Fix Workflows (70/100): 7/7 actions have working backends | `plugins/productivity/skills/google-workspace/augur.yaml` | Chains: `generate_delight` |
| 3.9 | frontend | medium | Fix Action Buttons (85/100): 5/7 actions are fully-wired | `plugins/productivity/skills/google-workspace/augur.yaml` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/google-workspace in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 40/100 to >= 90
- [ ] Performance improved from 41/100 to >= 90
- [ ] User Value improved from 47/100 to >= 90
- [ ] UI Compliance improved from 57/100 to >= 90
- [ ] Page Coverage improved from 58/100 to >= 90
- [ ] MCP Tool Wiring improved from 50/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 60/100 to >= 90
- [ ] Workflows improved from 70/100 to >= 90
- [ ] Action Buttons improved from 85/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] ADR-103 status updated to Accepted
