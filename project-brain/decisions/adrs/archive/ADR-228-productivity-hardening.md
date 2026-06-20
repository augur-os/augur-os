---
status: Implemented
date: '2026-03-02'
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

# ADR-228: Productivity Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 69/100 | 12% | significant-gaps | No GlassCard usage in /productivity/calendar |
| 2 | Page Coverage | 90/100 | 10% | good | 1/7 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 92/100 | 12% | good | 2/25 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 81/100 | 10% | needs-work | 22/57 source files have MCP/API tool calls |
| 5 | Performance | 68/100 | 10% | significant-gaps | No code splitting for large page: /productivity/calendar |
| 6 | User Value | 78/100 | 15% | needs-work | 10 real data files found across 5/5 skills |
| 7 | Workflows | 64/100 | 8% | significant-gaps | 11/15 actions have working backends |
| 8 | Cross-Hub Connectivity | 80/100 | 5% | needs-work | Links to 5 other hubs: /admin, /career, /finance, /health... |
| 9 | Action Buttons | 86/100 | 8% | needs-work | 11/15 actions are fully-wired |
| 10 | Wow Effect | 80/100 | 10% | needs-work | Best candidate: Edit in MarkText |

**Composite Score**: 78/100 (good-foundation)

**Scoring Confidence Note**: Action metrics use different semantics across dimensions (User Value: 7/15 autonomous, Workflows: 11/15 functional). Treat these as medium-confidence inputs until a shared action classification rubric is applied and scores are re-baselined before execution.

## Wow Effect: Edit in MarkText

> Open a note in your configured markdown editor

**Score**: 80/100

**Score breakdown**: static evidence 40/100 + runtime probe bonus 40 = 80/100

**Demo Flow**:
1. User clicks 'Edit in MarkText'
2. Action executes via the configured fast-action backend
3. UI confirms completion with updated data/view state

**Expected visible output**: Open a note in your configured markdown editor

**Current state**: 16 candidate actions/workflows evaluated; runtime probe confirms page/API responsiveness, not full end-to-end editor launch behavior
**Gap to demo-ready**: Require a full browser-validated E2E run of the MarkText action path with success/failure UX checks

**Cross-hub leverage**: Pulls data from admin, career, finance, health, lifestyle

**Other candidates**:
- List Notes (40/100, fast_action)
- Promote Inbox Item (40/100, llm_action)
- Search Notes (40/100, fast_action)
- Sync to Apple Notes (40/100, fast_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Productivity** (http://localhost:3000/productivity) on 2026-03-02.
Composite score: **78/100**.

### Issues Identified

**UI Compliance** (69/100):
- No GlassCard usage in /productivity/calendar
- Missing proper layout structure in /productivity/eisenhower
- No GlassCard usage in /productivity/email

**Performance** (68/100):
- No code splitting for large page: /productivity/calendar
- Large page (975 lines): /productivity
- No code splitting for large page: /productivity

**Workflows** (64/100):
- 11/15 actions have working backends
- 4/15 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

## Decision

Implement hardening in 4 phases (including baseline normalization), ordered by severity and user impact.

User-selected scope: **All Phases**.

### Pre-Phase: Score Normalization & Baseline Lock

- Normalize action semantics across User Value, Workflows, and Action Buttons (`autonomous`, `functional`, `frontend-only`, `IDE-assisted`)
- Recompute a single baseline action matrix (`count by class`, `total actions`, `source of truth files`)
- Record normalized baseline in the implementation notes before Phase 1 starts

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 80/100):
- Best candidate: Edit in MarkText
- Description: Open a note in your configured markdown editor
- Gap to demo-ready: Full browser-validated E2E run is required (editor launch success path plus actionable failure path)

### Phase 2: Completeness

**UI Compliance** (current: 69/100):
- No GlassCard usage in /productivity/calendar
- Missing proper layout structure in /productivity/eisenhower
- No GlassCard usage in /productivity/email

**Performance** (current: 68/100):
- No code splitting for large page: /productivity/calendar
- Large page (975 lines): /productivity
- No code splitting for large page: /productivity

**Workflows** (current: 64/100):
- 11/15 actions have working backends
- 4/15 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

### Phase 3: Polish, Integration & Cleanup

**MCP Tool Wiring** (current: 81/100):
- 22/57 source files have MCP/API tool calls
- MCP module registered with 48 tools

**User Value** (current: 78/100):
- 10 real data files found across 5/5 skills
- 5/25 API routes have real backend logic
- 17/23 pages fetch real data

**Cross-Hub Connectivity** (current: 80/100):
- Links to 5 other hubs: /admin, /career, /finance, /health, /lifestyle
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 15 connections

**Action Buttons** (current: 86/100):
- 11/15 actions are fully-wired
- 4/15 actions are frontend-only
- Action 'create-note' references missing modal ''

## Consequences

### Positive

- Productivity hub upgraded with standardized hardening across 8 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Edit in MarkText

### Negative

- Requires implementation effort across 8 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `productivity` hub audit
- Audit timestamp: 2026-03-02T20:58:26.991896

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-228: Productivity Hardening**.

Read the full ADR: `docs/decisions/ADR-228-productivity-hardening.md`

User-selected scope: **All Phases**.

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

1. **Create team**: `TeamCreate(team_name="adr-193-productivity-hardening", description="Implementing ADR-228: Productivity Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-193-productivity-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{{role}}' on the {team_name} team.
        Read your profile: .claude/agents/{{role}}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: Use task blocking for every file overlap, even inside PARALLEL phases. If two steps edit the same file, serialize them with `blocked_by`.
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-193-productivity-hardening`

#### Phase 0: Baseline Normalization
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 0.1 | architect | medium | Normalize action classification semantics and lock a single baseline matrix for User Value / Workflows / Action Buttons before implementation | `plugins/productivity/skills/*/augur/data/actions`, `plugins/dev/skills/frontend/augur/data/hardening-reports/productivity_20260302.yaml`, `docs/decisions/ADR-228-productivity-hardening.md` |

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (80/100): make 'Edit in MarkText' fully E2E with explicit success UX, actionable error UX, and completion telemetry | `plugins/productivity/skills/apple/augur/dashboard`, `plugins/productivity/skills/eisenhower/augur/dashboard`, `plugins/productivity/skills/google-workspace/augur/dashboard`, `plugins/productivity/skills/apple/augur/data/actions` |

#### Phase 2: Completeness
**Strategy**: MIXED (serialized where files overlap)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Fix UI Compliance (69/100): No GlassCard usage in /productivity/calendar (Chains: `ui_quality_audit`, `redesign_page`) | `plugins/productivity/skills/apple/augur/dashboard/calendar/page.tsx`, `plugins/productivity/skills/google-workspace/augur/dashboard/calendar/page.tsx`, `plugins/productivity/skills/eisenhower/augur/dashboard/page.tsx` |
| 2.2 | frontend | medium | Fix Performance (68/100): add code splitting only after UI structure changes settle on shared calendar files | `plugins/productivity/skills/apple/augur/dashboard/calendar/page.tsx`, `plugins/productivity/skills/google-workspace/augur/dashboard/calendar/page.tsx`, `plugins/productivity/skills/apple/augur/dashboard/page.tsx` |
| 2.3 | developer | medium | Fix Workflows (64/100): 11/15 actions have working backends (Chains: `generate_delight`) | `plugins/productivity/skills/apple/augur/data/actions`, `plugins/productivity/skills/eisenhower/augur/data/actions`, `plugins/productivity/skills/google-workspace/augur/data/actions` |

Dependency rules:
- `2.2` is `blocked_by: 2.1` (shared calendar files)
- `2.3` can run in parallel with `2.1` and `2.2` (different file set)

#### Phase 3: Polish, Integration & Cleanup
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | devops | low | Fix MCP Tool Wiring (81/100): 22/57 source files have MCP/API tool calls | `plugins/productivity/skills/apple/augur/mcp/__init__.py`, `plugins/productivity/skills/eisenhower/augur/mcp/__init__.py`, `plugins/productivity/skills/google-workspace/augur/mcp/__init__.py` |
| 3.2 | architect | high | Fix User Value (78/100): 10 real data files found across 5/5 skills | `plugins/productivity/skills/apple/augur/api`, `plugins/productivity/skills/google-workspace/augur/api`, `plugins/productivity/skills/organizer/augur/api` |
| 3.3 | developer | medium | Fix Cross-Hub Connectivity (80/100): Links to 5 other hubs: /admin, /career, /finance, /health... | `plugins/productivity/skills/apple/augur/dashboard`, `plugins/productivity/skills/eisenhower/augur/dashboard`, `plugins/productivity/skills/google-workspace/augur/dashboard` |
| 3.4 | frontend | medium | Fix Action Buttons (86/100): resolve frontend-only actions and missing modal references (`create-note`, `create-reminder`, `note-create`, `add-article`) | `plugins/productivity/skills/apple/augur.yaml`, `plugins/productivity/skills/eisenhower/augur.yaml`, `plugins/productivity/skills/google-workspace/augur.yaml`, `plugins/productivity/skills/apple/augur/data/actions`, `plugins/productivity/skills/eisenhower/augur/data/actions`, `plugins/productivity/skills/google-workspace/augur/data/actions`, `plugins/productivity/skills/*/augur/dashboard/modals` |
| 3.5 | developer | medium | Close known residual gaps in near-pass dimensions: remove hardcoded Docs content and replace health-route stubs with real checks | `plugins/productivity/skills/*/augur/dashboard`, `plugins/productivity/skills/*/augur/api` |

Dependency rules:
- `3.4` is `blocked_by: 2.3` (action wiring consistency)
- `3.5` can run in parallel with `3.1` to `3.3` if file overlap is avoided

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/productivity in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` and `augur/data/actions/*.yaml` against `augur/mcp/__init__.py` registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation and normalized action semantics remain consistent across dimensions |
| V.5 | validator | low | Re-run `dashboard_hardening_audit.py --url http://localhost:3000/productivity` and confirm score deltas and classification consistency |

### Completion Criteria

- [ ] Wow Effect improved from 80/100 to >= 90
- [ ] Wow-effect E2E acceptance passes: configured markdown editor launches from UI action, success state is visible, and failure path shows actionable guidance
- [ ] UI Compliance improved from 69/100 to >= 90
- [ ] Performance improved from 68/100 to >= 90
- [ ] Workflows improved from 64/100 to >= 90
- [ ] MCP Tool Wiring improved from 81/100 to >= 90
- [ ] User Value improved from 78/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 80/100 to >= 90
- [ ] Action Buttons improved from 86/100 to >= 90
- [ ] Known residuals closed: no hardcoded Docs mock content and no health route stubs in Productivity hub APIs
- [ ] Normalized action matrix published and used consistently across User Value, Workflows, and Action Buttons scoring
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in `augur.yaml` and `augur/data/actions/*.yaml` resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-228 status updated to Accepted
