---
status: Implemented
date: '2026-02-11'
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

# ADR-073: Google Workspace Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 55/100 | 12% | significant-gaps | No GlassCard usage in /google-workspace/calendar |
| 2 | Page Coverage | 44/100 | 10% | critical | 4/5 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 44/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 34/100 | 10% | critical | Large page (329 lines): /google-workspace/calendar |
| 6 | User Value | 30/100 | 15% | critical | No data directory — hub produces no persisted data |
| 7 | Workflows | 60/100 | 8% | significant-gaps | 5/5 actions have working backends |
| 8 | Cross-Hub Connectivity | 20/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 50/100 | 8% | significant-gaps | 5/5 actions are frontend-only |
| 10 | Wow Effect | 30/100 | 10% | critical | Best candidate: Extract Career Emails |

**Composite Score**: 48/100 (major-rebuild)

## Wow Effect: Summarize Today

> AI summarizes today's emails, calendar events, and doc activity into a single briefing — the killer daily-driver feature for Google Workspace hub

**Score**: 30/100

**Demo Flow**:
1. User clicks 'Summarize Today' on Overview or Gmail tab
2. Backend fetches today's Gmail threads, Calendar events, and recent Drive activity
3. AI synthesizes a structured daily briefing with priorities and action items
4. Briefing displayed inline with expandable sections per service

**Current state**: 6 candidate actions evaluated
**Gap to demo-ready**: Backend exists — needs live browser verification and end-to-end testing

**Other candidates**:
- Summarize Today (30/100, llm_action)
- Draft Reply (30/100, llm_action)
- Schedule Follow-up (30/100, llm_action)
- Weekly Email Digest (30/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Google Workspace** (http://localhost:3000/google-workspace) on 2026-02-11.
Composite score: **48/100**.

### Issues Identified

**UI Compliance** (55/100):
- No GlassCard usage in /google-workspace/calendar
- No GlassCard usage in /google-workspace/docs
- No GlassCard usage in /google-workspace/drive

**Page Coverage** (44/100):
- 4/5 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching
- Mixed real/mock data in 'Gmail' — still has hardcoded content

**MCP Tool Wiring** (44/100):
- No explicit MCP tool references in actions/modals
- 4/5 pages have MCP tool calls
- MCP module registered with 20 tools

**Performance** (34/100):
- Large page (329 lines): /google-workspace/calendar
- No code splitting for large page: /google-workspace/calendar
- Large page (313 lines): /google-workspace/docs

**User Value** (30/100):
- No data directory — hub produces no persisted data
- 14/14 API routes have real backend logic
- 1/5 pages fetch real data

**Workflows** (60/100):
- 5/5 actions have working backends
- No chain workflows found — no automated multi-step flows

**Cross-Hub Connectivity** (20/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 1 connections

**Action Buttons** (50/100):
- 5/5 actions are frontend-only

**Wow Effect** (30/100):
- Best candidate: Extract Career Emails
- Description: Find and summarize recent emails relevant to job search, interviews, and career opportunities
- Gap to demo-ready: Backend exists — needs live browser verification and end-to-end testing

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 30/100):
- Best candidate: Extract Career Emails
- Description: Find and summarize recent emails relevant to job search, interviews, and career opportunities
- Gap to demo-ready: Backend exists — needs live browser verification and end-to-end testing

**Page Coverage** (current: 44/100):
- 4/5 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching
- Mixed real/mock data in 'Gmail' — still has hardcoded content

**MCP Tool Wiring** (current: 44/100):
- No explicit MCP tool references in actions/modals
- 4/5 pages have MCP tool calls
- MCP module registered with 20 tools

**Performance** (current: 34/100):
- Large page (329 lines): /google-workspace/calendar
- No code splitting for large page: /google-workspace/calendar
- Large page (313 lines): /google-workspace/docs

**User Value** (current: 30/100):
- No data directory — hub produces no persisted data
- 14/14 API routes have real backend logic
- 1/5 pages fetch real data

**Cross-Hub Connectivity** (current: 20/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 1 connections

### Phase 2: Completeness

**UI Compliance** (current: 55/100):
- No GlassCard usage in /google-workspace/calendar
- No GlassCard usage in /google-workspace/docs
- No GlassCard usage in /google-workspace/drive

**Workflows** (current: 60/100):
- 5/5 actions have working backends
- No chain workflows found — no automated multi-step flows

**Action Buttons** (current: 50/100):
- 5/5 actions are frontend-only

## Consequences

### Positive

- Google Workspace hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Summarize Today

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
- Audit timestamp: 2026-02-11T16:24:55.435859

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-073: Google Workspace Hardening**.

Read the full ADR: `docs/decisions/ADR-073-google-workspace-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-073-google-workspace-hardening", description="Implementing ADR-073: Google Workspace Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-073-google-workspace-hardening", name="{role}",
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

**Team name**: `adr-073-google-workspace-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (30/100): Best candidate: Extract Career Emails | `plugins/productivity/skills/google-workspace/augur.yaml`, `plugins/productivity/skills/google-workspace/augur/` |
| 1.2 | developer | medium | Fix Page Coverage (44/100): 4/5 pages use mock/hardcoded data instead of real fetching | `plugins/productivity/skills/google-workspace/augur/` |
| 1.3 | devops | low | Fix MCP Tool Wiring (44/100): No explicit MCP tool references in actions/modals | `plugins/productivity/skills/google-workspace/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.4 | frontend | medium | Fix Performance (34/100): Large page (329 lines): /google-workspace/calendar | `plugins/productivity/skills/google-workspace/augur/calendar/page.tsx`, `plugins/productivity/skills/google-workspace/augur/calendar/page.tsx`, `plugins/productivity/skills/google-workspace/augur/docs/page.tsx` |
| 1.5 | architect | high | Fix User Value (30/100): No data directory — hub produces no persisted data | `plugins/productivity/skills/google-workspace/augur.yaml` |
| 1.6 | developer | medium | Fix Cross-Hub Connectivity (20/100): No cross-hub navigation links — hub is isolated | `plugins/productivity/skills/google-workspace/augur/` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.7 | frontend | medium | Fix UI Compliance (55/100): No GlassCard usage in /google-workspace/calendar | `plugins/productivity/skills/google-workspace/augur/calendar/page.tsx`, `plugins/productivity/skills/google-workspace/augur/docs/page.tsx`, `plugins/productivity/skills/google-workspace/augur/drive/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.8 | developer | medium | Fix Workflows (60/100): 5/5 actions have working backends | `plugins/productivity/skills/google-workspace/augur.yaml` | Chains: `generate_delight` |
| 2.9 | frontend | medium | Fix Action Buttons (50/100): 5/5 actions are frontend-only | `plugins/productivity/skills/google-workspace/augur.yaml` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 30/100 to >= 90
- [ ] Page Coverage improved from 44/100 to >= 90
- [ ] MCP Tool Wiring improved from 44/100 to >= 90
- [ ] Performance improved from 34/100 to >= 90
- [ ] User Value improved from 30/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 20/100 to >= 90
- [ ] UI Compliance improved from 55/100 to >= 90
- [ ] Workflows improved from 60/100 to >= 90
- [ ] Action Buttons improved from 50/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] ADR-073 status updated to Accepted

## User Notes

Focus on Gmail integration — Gmail is the highest-value subpage and should be prioritized in the hardening plan. The "Summarize Today" wow effect was chosen specifically because it centers on Gmail as the primary data source, with Calendar and Drive as supporting inputs.
