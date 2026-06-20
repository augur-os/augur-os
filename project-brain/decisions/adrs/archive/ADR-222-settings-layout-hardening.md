---
status: Implemented
date: '2026-03-04'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- settings
- hardening
superseded_by: null
---

# ADR-222: Settings Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 50/100 | 12% | significant-gaps | No GlassCard usage in /settings/layout |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 15/100 | 12% | critical | API directory exists but contains no route.ts files |
| 4 | MCP Tool Wiring | 30/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 95/100 | 10% | good | Runtime probe: pages 1/1 (avg 33ms), apis 0/0 (avg 0ms) |
| 6 | User Value | 25/100 | 15% | critical | No API routes — hub cannot process data autonomously |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 2/100 | 8% | critical | No dashboard action manifest, but UI has 1 button element... |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 34/100 (major-rebuild)

## Wow Effect: No wow effect identified

> Hub has no complete actions that could serve as a demo

**Score**: 0/100

**Score breakdown**: static evidence 0/100 + runtime bonus 0 = 0/100

**Current state**: No interactive workflows
**Gap to demo-ready**: Add at least one action with real backend, real data, and visible output

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Settings** (http://localhost:3000/settings/layout) on 2026-03-04.
Composite score: **34/100**.

### Issues Identified

**UI Compliance** (50/100):
- No GlassCard usage in /settings/layout
- 1/1 pages lack strong typography hierarchy
- 1/1 pages miss design-system accent colors

**API Completeness** (15/100):
- API directory exists but contains no route.ts files

**MCP Tool Wiring** (30/100):
- No explicit MCP tool references in actions/modals
- 1/1 source files have MCP/API tool calls
- Core hub inline MCP wiring detected via action-runner references, API calls, and MCP endpoint usage

**User Value** (25/100):
- No API routes — hub cannot process data autonomously
- 1/1 pages fetch real data
- No actions defined — hub is read-only

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Action Buttons** (2/100):
- No dashboard action manifest, but UI has 1 button elements and 1 click handlers

**Wow Effect** (0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- UI evidence missing: candidate not confirmed in hub dashboard source

## Decision

Implement hardening in 2 phases, ordered by severity and user impact.

User-selected scope: **All Phases**.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- UI evidence missing: candidate not confirmed in hub dashboard source

**API Completeness** (current: 15/100):
- API directory exists but contains no route.ts files

**MCP Tool Wiring** (current: 30/100):
- No explicit MCP tool references in actions/modals
- 1/1 source files have MCP/API tool calls
- Core hub inline MCP wiring detected via action-runner references, API calls, and MCP endpoint usage

**User Value** (current: 25/100):
- No API routes — hub cannot process data autonomously
- 1/1 pages fetch real data
- No actions defined — hub is read-only

**Workflows** (current: 0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (current: 0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Action Buttons** (current: 2/100):
- No dashboard action manifest, but UI has 1 button elements and 1 click handlers

### Phase 2: Completeness

**UI Compliance** (current: 50/100):
- No GlassCard usage in /settings/layout
- 1/1 pages lack strong typography hierarchy
- 1/1 pages miss design-system accent colors

## Consequences

### Positive

- Settings hub upgraded with standardized hardening across 8 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: No wow effect identified

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
- Audit report: `settings_layout` extension audit (/settings/layout)
- Audit timestamp: 2026-03-04T22:33:30.660614

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-222: Settings Hardening**.

Read the full ADR: `docs/decisions/ADR-222-settings-layout-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-222-settings-layout-hardening", description="Implementing ADR-222: Settings Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-222-settings-layout-hardening", name="{role}",
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

**Team name**: `adr-222-settings-layout-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: MIXED (lock wow-effect acceptance criteria first, then parallelize remaining critical dimensions)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (0/100): Best candidate: No wow effect identified | `plugins/skills` |
| 1.2 | developer | medium | Fix API Completeness (15/100): API directory exists but contains no route.ts files | `plugins/skills` |
| 1.3 | devops | low | Fix MCP Tool Wiring (30/100): No explicit MCP tool references in actions/modals | `plugins/skills` |
| 1.4 | architect | high | Fix User Value (25/100): No API routes — hub cannot process data autonomously | `plugins/skills` |
| 1.5 | developer | medium | Fix Workflows (0/100): No actions defined — hub has no workflows | `plugins/skills` |
| 1.6 | developer | medium | Fix Cross-Hub Connectivity (0/100): No cross-hub navigation links — hub is isolated | `plugins/skills` |
| 1.7 | frontend | medium | Fix Action Buttons (2/100): No dashboard action manifest, but UI has 1 button element... | `plugins/skills` |

#### Phase 2: Completeness
**Strategy**: PIPELINE

Dependency: complete Phase 1 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Fix UI Compliance (50/100): No GlassCard usage in /settings/layout (Chains: `ui_quality_audit`, `redesign_page`) | `plugins/skills` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/settings/layout in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` and `augur/data/actions/*.yaml` against the current MCP tool registry/exposed server tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90
- [ ] API Completeness improved from 15/100 to >= 90
- [ ] MCP Tool Wiring improved from 30/100 to >= 90
- [ ] User Value improved from 25/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] Action Buttons improved from 2/100 to >= 90
- [ ] UI Compliance improved from 50/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in `augur.yaml` and `augur/data/actions/*.yaml` resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-222 status updated to Accepted
