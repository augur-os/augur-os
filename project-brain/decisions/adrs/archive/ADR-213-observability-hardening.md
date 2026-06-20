---
status: Superseded
date: '2026-03-03'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
- ADR-212 (supersedes this)
hub: null
tags:
- observability
- hardening
superseded_by: null
---

# ADR-213: Observability Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 98/100 | 12% | good | - |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 89/100 | 10% | needs-work | 8 actions use API-wrapped MCP pattern |
| 5 | Performance | 63/100 | 10% | significant-gaps | Large page (332 lines): /observability/daemon/loops |
| 6 | User Value | 81/100 | 15% | needs-work | 10 real data files found across 2/3 skills |
| 7 | Workflows | 90/100 | 8% | good | 8/8 actions have working backends |
| 8 | Cross-Hub Connectivity | 80/100 | 5% | needs-work | Links to 4 other hubs: /admin, /ai, /health, /professional |
| 9 | Action Buttons | 100/100 | 8% | good | 8/8 actions are fully-wired |
| 10 | Wow Effect | 35/100 | 10% | critical | Best candidate: Observability AI Workflow Suite |

**Composite Score**: 83/100 (good-foundation)

**Scoring Confidence Note**: Scores are point-in-time for this audit run. Non-action dimensions are evidence-backed by direct findings in the report. Action-derived interpretation is provisional because action semantics differ across dimensions (User Value: 1/8 autonomous, Workflows: 8/8 functional). Reconcile semantics in Phase 1, then re-run the audit before downstream implementation.

## Wow Effect: Observability AI Workflow Suite

> Suite of 8 actions (7 AI-powered) — needs live verification

**Score**: 35/100

**Score breakdown**: static evidence 35/100 + runtime bonus 0 = 35/100

**Evidence status**: The current audit still reports "UI evidence missing" and records no concrete `flow_steps`. The outputs and flow below are implementation acceptance targets, not already-verified baseline behavior.

**Expected visible output**:
1. Notification count visibly drops in the notifications view after `Dismiss Old Notifications`.
2. A loop status badge/state visibly changes after running `Loop Status`.
3. Loop history shows a newly appended row/event after running `Loop History`.

**Demo flow (must pass end-to-end)**:
1. Open `/observability` and navigate to notifications; record current notification count.
2. Trigger `Dismiss Old Notifications`; verify the count decreases and UI confirms completion.
3. Navigate to loops; trigger `Loop Status`; verify at least one status indicator changes.
4. Trigger `Loop History`; verify a new history item appears with a current timestamp.
5. Capture before/after screenshots for each step and store with verification artifacts.

**Current state**: 9 candidate actions/workflows were ranked; end-to-end browser evidence for the selected flow is not yet captured.
**Gap to demo-ready**: Runtime partially verified — tighten UX flow and reduce action friction for a demo-ready experience

**Cross-hub leverage**: Pulls data from health

**Other candidates**:
- Dismiss Old Notifications (20/100, llm_action)
- Loop History (20/100, llm_action)
- Loop Status (20/100, llm_action)
- Promote Category (20/100, llm_action)

**Priority**: This is the first implementation target after the Phase 1 reconciliation gate (executed in Phase 2).

## Context

Automated hardening audit of **Observability** (http://localhost:3000/observability?tab=logs) on 2026-03-03.
Composite score: **83/100**.

### Issues Identified

**Performance** (63/100):
- Large page (332 lines): /observability/daemon/loops
- No code splitting for large page: /observability/daemon/loops
- Large page (578 lines): /observability/daemon/notifications

**Wow Effect** (35/100):
- Best candidate: Observability AI Workflow Suite
- Description: Suite of 8 actions (7 AI-powered) — needs live verification
- UI evidence missing: candidate not confirmed in hub dashboard source

**MCP Tool Wiring** (89/100):
- 8 actions use API-wrapped MCP pattern
- 20/31 source files have MCP/API tool calls
- MCP module registered with 14 tools

**User Value** (81/100):
- 10 real data files found across 2/3 skills
- 6/8 API routes have real backend logic
- 15/15 pages fetch real data
- 1/8 actions have autonomous backends

**Cross-Hub Connectivity** (80/100):
- Links to 4 other hubs: /admin, /ai, /health, /professional
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 9 connections

## Decision

Implement hardening in 4 phases, ordered by severity and user impact.

User-selected scope: **All Phases**.
Execution focus for this revision: close all failing dimensions (<90) while preserving non-failing dimensions.

### Phase 1: Scoring Reconciliation

**Action scoring conflict (must resolve first):**
- Action metrics use different semantics across dimensions (User Value: 1/8 autonomous, Workflows: 8/8 functional). Reconcile this classification during implementation.
- Define one canonical action-state rubric shared by User Value, Workflows, and Action Buttons
- Recompute findings so action counts align before planning execution tasks

### Phase 2: Wow Effect & Critical Gaps

Provisional phase: re-run the audit and regenerate this ADR after Phase 1 reconciliation before execution.

**Wow Effect** (current: 35/100):
- Best candidate: Observability AI Workflow Suite
- Description: Suite of 8 actions (7 AI-powered) — needs live verification
- UI evidence missing: candidate not confirmed in hub dashboard source

### Phase 3: Completeness

Can start after Phase 1 reconciliation and post-gate ADR regeneration. It is independent from Phase 2 except where files overlap; if ownership conflicts occur, sequence after Phase 2.

**Performance** (current: 63/100):
- Large page (332 lines): /observability/daemon/loops
- No code splitting for large page: /observability/daemon/loops
- Large page (578 lines): /observability/daemon/notifications

### Phase 4: Failing-Dimension Closure

Can run in parallel with Phases 2 and 3 after the Phase 1 gate re-audit/regeneration. Coordinate file ownership to avoid merge conflicts.

**MCP Tool Wiring** (current: 89/100):
- Confirm every `mcp_tool` reference resolves to a registered tool and remove stale refs.
- Raise wiring quality from 89 to >= 90 with evidence in verification output.

**User Value** (current: 81/100):
- Increase direct visible outcomes from actions (not only IDE-assisted execution).
- Add at least one autonomous, user-verifiable dashboard outcome path.

**Cross-Hub Connectivity** (current: 80/100):
- Validate all existing cross-hub links/routes at runtime.
- Add at least one concrete cross-hub data integration path or remove unsupported connectivity claims.

## User Notes

Audit note captured during harden run: "The main issue is that I have a lot of logs in the runtime folder but nothing seems connected."

## Consequences

### Positive

- Observability hub upgraded with standardized hardening across 5 dimensions
- Phase 1 preserves and validates the wow-effect demo flow
- Killer demo use case identified: Observability AI Workflow Suite

### Negative

- Requires implementation effort across 5 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `observability` hub audit
- Audit timestamp: 2026-03-03T20:25:23.528008

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-213: Observability Hardening**.

Read the full ADR: `docs/decisions/ADR-213-observability-hardening.md`

User-selected scope: **All Phases**.
Execution focus: include all failing dimensions (<90) for full gap closure in this ADR revision.

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

1. **Create team**: `TeamCreate(team_name="adr-213-observability-hardening", description="Implementing ADR-213: Observability Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-213-observability-hardening", name="{role}",
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

**Team name**: `adr-213-observability-hardening`

#### Phase 1: Scoring Reconciliation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | architect | medium | Reconcile action semantics across User Value, Workflows, and Action Buttons; regenerate aligned findings | `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py`, `plugins/dev/skills/frontend/scripts/generate_hardening_adr.py`, `plugins/dev/skills/frontend/augur/data/hardening-reports` |

#### Phase 2: Wow Effect & Critical Gaps
**Strategy**: PIPELINE (provisional until post-reconciliation rerun)

Dependency: complete Phase 1 and merge results before starting.

Do not execute this phase until reconciliation is complete and the ADR is regenerated.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | high | Fix Wow Effect (35/100): Best candidate: Observability AI Workflow Suite | `plugins/observability/skills/daemon/augur/dashboard`, `plugins/observability/skills/observe/augur/dashboard`, `plugins/observability/skills/daemon/augur.yaml` |

#### Phase 3: Completeness
**Strategy**: PIPELINE (after Phase 1 gate; independent from Phase 2 unless files overlap)

Dependency: complete Phase 1 reconciliation and regenerate ADR before starting.

Do not execute this phase until reconciliation is complete and the ADR is regenerated.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Fix Performance (63/100): Large page (332 lines): /observability/daemon/loops | `plugins/observability/skills/daemon/augur/dashboard/loops/page.tsx`, `plugins/observability/skills/daemon/augur/dashboard/notifications/page.tsx`, `plugins/observability/skills/daemon/augur/dashboard/page.tsx` |

#### Phase 4: Failing-Dimension Closure
**Strategy**: PARALLEL (after Phase 1 gate; can run alongside Phases 2 and 3)

Dependency: complete Phase 1 reconciliation and regenerate ADR before starting.

Do not execute this phase until reconciliation is complete and the ADR is regenerated.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | devops | medium | Raise MCP Tool Wiring from 89 to >= 90 by validating and fixing `mcp_tool` references and API-wrapped MCP paths | `plugins/observability/skills/*/augur.yaml`, `plugins/observability/skills/*/augur/data/actions/*.yaml`, `plugins/observability/skills/*/augur/mcp/*.py` |
| 4.2 | architect | high | Raise User Value from 81 to >= 90 by defining and implementing at least one autonomous, visible action outcome path in dashboard UX | `plugins/observability/skills/observe/augur/dashboard`, `plugins/observability/skills/daemon/augur/dashboard`, `plugins/observability/skills/metrics/augur/dashboard` |
| 4.3 | developer | medium | Raise Cross-Hub Connectivity from 80 to >= 90 by validating links and implementing one concrete cross-hub data integration or removing unsupported claims | `plugins/observability/skills/*/augur/dashboard/**/*.tsx`, `src/dashboard/lib/tabs/**/*.ts`, `src/lib/services/**/*.ts` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/observability?tab=logs in Chrome MCP, screenshot each tab (including health), check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` and `augur/data/actions/*.yaml` against the current MCP tool registry/exposed server tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 35/100 to >= 90
- [ ] Wow demo flow has 3 reproducible visible outcomes (notification count drop, status change, history append)
- [ ] Performance improved from 63/100 to >= 90
- [ ] MCP Tool Wiring improved from 89/100 to >= 90
- [ ] User Value improved from 81/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 80/100 to >= 90
- [ ] Action scoring semantics reconciled across User Value, Workflows, and Action Buttons
- [ ] Hardening audit re-run and ADR regenerated after reconciliation
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in `augur.yaml` and `augur/data/actions/*.yaml` resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-213 status updated to Accepted
