---
status: Implemented
date: '2026-02-12'
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

# ADR-118: Observability Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 10/100 | 12% | critical | No GlassCard usage in /observe |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 0/100 | 12% | critical | 1/1 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 0/100 | 10% | critical | No actions and no MCP integration — hub is entirely passive |
| 5 | Performance | 60/100 | 10% | significant-gaps | Good static performance patterns detected |
| 6 | User Value | 0/100 | 15% | critical | No data directory — hub produces no persisted data |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 50/100 | 5% | significant-gaps | Links to 1 other hubs: /ai_bridge |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 19/100 (major-rebuild)

## Wow Effect: Self-Heal Event Timeline

> Interactive timeline showing self-heal detections, classifications, and autonomous fixes with before/after diffs and success rates

**Score**: 0/100

**Demo Flow**:
1. Daemon scanner detects error in logs
2. LLM classifier categorizes severity and type (transient vs actionable)
3. Fix engine generates and applies patch
4. Timeline entry appears with detection→classification→fix→commit chain
5. User can expand entry to see diff, commit hash, and success/failure

**Current state**: Self-heal pipeline operational since 2026-02-11, but no UI visibility
**Gap to demo-ready**: Build timeline UI component, wire to self-heal history data, add real-time updates

**Cross-hub leverage**: Pulls data from /control (daemon service status), /ai_bridge (agent activity)

**Other candidates**:
- Live System Health Dashboard (75/100, )
- Agent Activity Monitor (70/100, )

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Observability** (http://localhost:3000/observe) on 2026-02-12.
Composite score: **19/100**.

### Issues Identified

**UI Compliance** (10/100):
- No GlassCard usage in /observe
- Missing proper layout structure in /observe
- No interactive elements in /observe — static display only

**API Completeness** (0/100):
- 1/1 API routes are stubs with no real backend logic
- STUB: /api/observe/sessions returns hardcoded/minimal response

**MCP Tool Wiring** (0/100):
- No actions and no MCP integration — hub is entirely passive

**Performance** (60/100):
- Good static performance patterns detected
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (0/100):
- No data directory — hub produces no persisted data
- All 1 API routes are stubs — no real processing
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (50/100):
- Links to 1 other hubs: /ai_bridge
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 6 connections

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity

**Wow Effect** (0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

**UI Compliance** (current: 10/100):
- No GlassCard usage in /observe
- Missing proper layout structure in /observe
- No interactive elements in /observe — static display only

**API Completeness** (current: 0/100):
- 1/1 API routes are stubs with no real backend logic
- STUB: /api/observe/sessions returns hardcoded/minimal response

**MCP Tool Wiring** (current: 0/100):
- No actions and no MCP integration — hub is entirely passive

**User Value** (current: 0/100):
- No data directory — hub produces no persisted data
- All 1 API routes are stubs — no real processing
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (current: 0/100):
- No actions defined — hub has no workflows

**Action Buttons** (current: 0/100):
- No action buttons defined — hub has no interactivity

### Phase 2: Completeness

**Performance** (current: 60/100):
- Good static performance patterns detected
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**Cross-Hub Connectivity** (current: 50/100):
- Links to 1 other hubs: /ai_bridge
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 6 connections

## Consequences

### Positive

- Observability hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Self-Heal Event Timeline

### Negative

- Requires implementation effort across 9 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## User Notes

- **Focus on self-heal visibility**: The self-heal pipeline is now operational (as of 2026-02-11). Prioritize surfacing heal events — detections, classifications, fixes, and success rates — as the primary data source for this hub.
- **Integrate daemon metrics**: The daemon service (LaunchAgent) runs background monitoring (log scanning, health checks). Surface its health status, scan results, and service uptime directly in the hub.
- **Make it the ops command center**: This should be the single pane of glass for all system operations and health. Consolidate scattered monitoring data from /control, /ai_bridge, and daemon services into this hub.

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `observe` hub audit
- Audit timestamp: 2026-02-12T00:20:50.006805

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-078: Observability Hardening**.

Read the full ADR: `docs/decisions/ADR-078-observe-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-078-observe-hardening", description="Implementing ADR-078: Observability Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-078-observe-hardening", name="{role}",
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

**Team name**: `adr-078-observe-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (0/100): Best candidate: No wow effect identified | `plugins/observability/skills/observe/augur.yaml`, `plugins/observability/skills/observe/augur/` |
| 1.2 | frontend | medium | Fix UI Compliance (10/100): No GlassCard usage in /observe | `plugins/observability/skills/observe/augur//page.tsx`, `plugins/observability/skills/observe/augur//page.tsx`, `plugins/observability/skills/observe/augur//page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.3 | developer | medium | Fix API Completeness (0/100): 1/1 API routes are stubs with no real backend logic | `src/dashboard/app/api/observe/`, `src/dashboard/lib/services/` |
| 1.4 | devops | low | Fix MCP Tool Wiring (0/100): No actions and no MCP integration — hub is entirely passive | `plugins/observability/skills/observe/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.5 | architect | high | Fix User Value (0/100): No data directory — hub produces no persisted data | `plugins/observability/skills/observe/augur.yaml` |
| 1.6 | developer | medium | Fix Workflows (0/100): No actions defined — hub has no workflows | `plugins/observability/skills/observe/augur.yaml` | Chains: `generate_delight` |
| 1.7 | frontend | medium | Fix Action Buttons (0/100): No action buttons defined — hub has no interactivity | `plugins/observability/skills/observe/augur.yaml` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.8 | frontend | medium | Fix Performance (60/100): Good static performance patterns detected | `plugins/observability/skills/observe/augur//page.tsx` |
| 2.9 | developer | medium | Fix Cross-Hub Connectivity (50/100): Links to 1 other hubs: /ai_bridge | `plugins/observability/skills/observe/augur/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/observe in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90
- [ ] UI Compliance improved from 10/100 to >= 90
- [ ] API Completeness improved from 0/100 to >= 90
- [ ] MCP Tool Wiring improved from 0/100 to >= 90
- [ ] User Value improved from 0/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] Performance improved from 60/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 50/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] ADR-078 status updated to Accepted
