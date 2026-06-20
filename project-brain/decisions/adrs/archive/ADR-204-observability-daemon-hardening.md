---
status: Implemented
date: '2026-03-03'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- observability
- hardening
superseded_by: null
---

# ADR-227: Observability Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 98/100 | 12% | good | - |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 88/100 | 10% | needs-work | 8 actions use API-wrapped MCP pattern |
| 5 | Performance | 40/100 | 10% | critical | Large page (332 lines): /observability/daemon/loops |
| 6 | User Value | 81/100 | 15% | needs-work | 9 real data files found across 1/1 skills |
| 7 | Workflows | 90/100 | 8% | good | 8/8 actions have working backends |
| 8 | Cross-Hub Connectivity | 50/100 | 5% | significant-gaps | Links to 1 other hubs: /health |
| 9 | Action Buttons | 100/100 | 8% | good | 8/8 actions are fully-wired |
| 10 | Wow Effect | 35/100 | 10% | critical | Best candidate: Observability AI Workflow Suite |

**Composite Score**: 79/100 (good-foundation)

**Scoring Confidence Note**: Action metrics use different semantics across dimensions (User Value: 1/8 autonomous, Workflows: 8/8 functional). Reconcile this classification during implementation.

## Wow Effect: Observability AI Workflow Suite

> Execute a visible end-to-end daemon workflow from Loops and Notifications tabs with confirmed UI state changes

**Score**: 35/100

**Score breakdown**: static evidence 35/100 + runtime bonus 0 = 35/100

**Demo Flow**:
1. Open /observability/daemon/loops and trigger "Run Loop Cycle"; confirm success toast and refreshed loop status timestamp
2. Open /observability/daemon/notifications and trigger "Test Notification"; confirm a new notification appears at top of list
3. Trigger "Dismiss Old Notifications"; confirm dismissed count is reported and list count decreases

**Expected visible output**: Loop run status updates in Loops tab and notification list changes are visible in Notifications tab after actions complete

**Current state**: 9 candidate actions/workflows evaluated
**Gap to demo-ready**: Static-only assessment — run /harden with dashboard running to verify live behavior

**Cross-hub leverage**: Pulls data from health

**Other candidates**:
- Dismiss Old Notifications (20/100, llm_action)
- Loop History (20/100, llm_action)
- Loop Status (20/100, llm_action)
- Promote Category (20/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Observability** (http://localhost:3000/observability/daemon/loops) on 2026-03-03.
Composite score: **79/100**.

### Issues Identified

**Performance** (40/100):
- Large page (332 lines): /observability/daemon/loops
- No code splitting for large page: /observability/daemon/loops
- Large page (578 lines): /observability/daemon/notifications

**Cross-Hub Connectivity** (50/100):
- Links to 1 other hubs: /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 3 connections

**Wow Effect** (35/100):
- Best candidate: Observability AI Workflow Suite
- Description: Execute a visible end-to-end daemon workflow from Loops and Notifications tabs with confirmed UI state changes
- UI evidence missing: candidate not confirmed in hub dashboard source

## Decision

Implement hardening in 3 phases, ordered by severity and user impact.

User-selected scope: **Critical + Completeness**.
Skipped dimensions: UI Compliance, Page Coverage, API Completeness, MCP Tool Wiring, User Value, Workflows, Action Buttons.

### Phase 1: Scoring Reconciliation

**Action scoring conflict (must resolve first):**
- Action metrics use different semantics across dimensions (User Value: 1/8 autonomous, Workflows: 8/8 functional). Reconcile this classification during implementation.
- Define one canonical action-state rubric shared by User Value, Workflows, and Action Buttons
- Recompute findings so action counts align before planning execution tasks

### Phase 2: Wow Effect & Critical Gaps

Provisional phase: re-run the audit and regenerate this ADR after Phase 1 reconciliation before execution.

**Wow Effect** (current: 35/100):
- Best candidate: Observability AI Workflow Suite
- Description: Execute a visible end-to-end daemon workflow from Loops and Notifications tabs with confirmed UI state changes
- UI evidence missing: candidate not confirmed in hub dashboard source

**Performance** (current: 40/100):
- Large page (332 lines): /observability/daemon/loops
- No code splitting for large page: /observability/daemon/loops
- Large page (578 lines): /observability/daemon/notifications

### Phase 3: Completeness

Provisional phase: re-run the audit and regenerate this ADR after Phase 1 reconciliation before execution.

**Cross-Hub Connectivity** (current: 50/100):
- Links to 1 other hubs: /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 3 connections

## User Notes

Prioritize measurable demo acceptance criteria and explicit file-level execution targets.

## Consequences

### Positive

- Observability hub upgraded with standardized hardening across 3 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Observability AI Workflow Suite

### Negative

- Requires implementation effort across 3 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `observability_daemon` extension audit (/observability/daemon)
- Audit timestamp: 2026-03-03T20:28:40.806867

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-227: Observability Hardening**.

Read the full ADR: `docs/decisions/ADR-227-observability-daemon-hardening.md`

User-selected scope: **Critical + Completeness**.
Skipped dimensions: UI Compliance, Page Coverage, API Completeness, MCP Tool Wiring, User Value, Workflows, Action Buttons.

Scoring confidence note: Action metrics use different semantics across dimensions (User Value: 1/8 autonomous, Workflows: 8/8 functional). Reconcile this classification during implementation.
Execution gate: complete reconciliation first, then re-run hardening audit + ADR generation before executing later phases.

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

1. **Create team**: `TeamCreate(team_name="adr-204-observability-daemon-hardening", description="Implementing ADR-227: Observability Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-204-observability-daemon-hardening", name="{role}",
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

**Team name**: `adr-204-observability-daemon-hardening`

#### Phase 1: Scoring Reconciliation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | medium | Reconcile action semantics across User Value, Workflows, and Action Buttons; regenerate aligned findings | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py`, `plugins/dev/skills/frontend/scripts/generate_hardening_adr.py`, `plugins/dev/skills/frontend/augur/data/hardening-reports` |

#### Phase 2: Wow Effect & Critical Gaps
**Strategy**: MIXED (lock wow-effect acceptance criteria first, then parallelize remaining critical dimensions) (provisional until post-reconciliation rerun)

Dependency: complete Phase 1 and merge results before starting.

Do not execute this phase until reconciliation is complete and the ADR is regenerated.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Fix Wow Effect (35/100): Best candidate: Observability AI Workflow Suite | `plugins/observability/skills/daemon/augur/dashboard`, `plugins/observability/skills/daemon/augur.yaml` |
| 2.2 | frontend | medium | Fix Performance (40/100): Large page (332 lines): /observability/daemon/loops | `plugins/observability/skills/daemon/augur/dashboard/loops/page.tsx`, `plugins/observability/skills/daemon/augur/dashboard/notifications/page.tsx`, `plugins/observability/skills/daemon/augur/dashboard/page.tsx` |

#### Phase 3: Completeness
**Strategy**: PIPELINE (provisional until post-reconciliation rerun)

Dependency: complete Phase 2 and merge results before starting.

Do not execute this phase until reconciliation is complete and the ADR is regenerated.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Fix Cross-Hub Connectivity (50/100): Links to 1 other hubs: /health | `plugins/observability/skills/daemon/augur/dashboard` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/observability/daemon/loops in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` and `augur/data/actions/*.yaml` against the current MCP tool registry/exposed server tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 35/100 to >= 90
- [ ] Demo flow check: "Run Loop Cycle" shows success feedback and loop status timestamp changes from pre-action value
- [ ] Demo flow check: "Test Notification" creates a visible new notification item in the Notifications tab
- [ ] Demo flow check: "Dismiss Old Notifications" reports dismissed count and decreases visible notification count when eligible items exist
- [ ] Performance improved from 40/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 50/100 to >= 90
- [ ] Action scoring semantics reconciled across User Value, Workflows, and Action Buttons
- [ ] Hardening audit re-run and ADR regenerated after reconciliation
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in `augur.yaml` and `augur/data/actions/*.yaml` resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-227 status updated to Accepted
