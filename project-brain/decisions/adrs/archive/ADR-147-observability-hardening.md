---
status: Implemented
date: '2026-02-25'
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

# ADR-147: Observability Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 25/100 | 12% | critical | No GlassCard usage in /observability/daemon/health |
| 2 | Page Coverage | 30/100 | 10% | critical | Missing page.tsx for tab 'Health' (/observability/health) |
| 3 | API Completeness | 66/100 | 12% | significant-gaps | 1/3 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 15/100 | 10% | critical | Actions defined but none use MCP tools — limited autonomy |
| 5 | Performance | 34/100 | 10% | critical | Score capped at 60/100 — runtime telemetry needed for ful... |
| 6 | User Value | 37/100 | 15% | critical | Data directory has no substantial data files — empty or t... |
| 7 | Workflows | 70/100 | 8% | needs-work | 7/7 actions have working backends |
| 8 | Cross-Hub Connectivity | 50/100 | 5% | significant-gaps | Links to 1 other hubs: /health |
| 9 | Action Buttons | 92/100 | 8% | good | 6/7 actions are fully-wired |
| 10 | Wow Effect | 35/100 | 10% | critical | Best candidate: Observability AI Workflow Suite |

**Composite Score**: 43/100 (major-rebuild)

## Wow Effect: Observability AI Workflow Suite

> Suite of 7 actions (1 AI-powered) — needs live verification

**Score**: 35/100

**Current state**: 8 candidate actions evaluated
**Gap to demo-ready**: Good static foundation — run /harden with dashboard running to verify live behavior

**Cross-hub leverage**: Pulls data from health

**Other candidates**:
- Check Health (30/100, fast_action)
- MCP Diagnostics (30/100, fast_action)
- Test MCP Connection (30/100, fast_action)
- Performance Metrics (30/100, fast_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Observability** (http://localhost:3000/observability) on 2026-02-25.
Composite score: **43/100**.

### Issues Identified

**UI Compliance** (25/100):
- No GlassCard usage in /observability/daemon/health
- Missing proper layout structure in /observability/daemon/health
- No interactive elements in /observability/daemon/health — static display only

**Page Coverage** (30/100):
- Missing page.tsx for tab 'Health' (/observability/health)
- Missing page.tsx for tab 'Logs' (/observability/logs)
- Missing page.tsx for tab 'MCP' (/observability/mcp)

**API Completeness** (66/100):
- 1/3 API routes are stubs with no real backend logic
- STUB: /api/observability/daemon/self-heal/event returns hardcoded/minimal response

**MCP Tool Wiring** (15/100):
- Actions defined but none use MCP tools — limited autonomy

**Performance** (34/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (37/100):
- Data directory has no substantial data files — empty or template-only
- 2/3 API routes have real backend logic
- No pages fetch real data — all use hardcoded/mock content

**Cross-Hub Connectivity** (50/100):
- Links to 1 other hubs: /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 2 connections

**Wow Effect** (35/100):
- Best candidate: Observability AI Workflow Suite
- Description: Suite of 7 actions (1 AI-powered) — needs live verification
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 35/100):
- Best candidate: Observability AI Workflow Suite
- Description: Suite of 7 actions (1 AI-powered) — needs live verification
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

**UI Compliance** (current: 25/100):
- No GlassCard usage in /observability/daemon/health
- Missing proper layout structure in /observability/daemon/health
- No interactive elements in /observability/daemon/health — static display only

**Page Coverage** (current: 30/100):
- Missing page.tsx for tab 'Health' (/observability/health)
- Missing page.tsx for tab 'Logs' (/observability/logs)
- Missing page.tsx for tab 'MCP' (/observability/mcp)

**MCP Tool Wiring** (current: 15/100):
- Actions defined but none use MCP tools — limited autonomy

**Performance** (current: 34/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (current: 37/100):
- Data directory has no substantial data files — empty or template-only
- 2/3 API routes have real backend logic
- No pages fetch real data — all use hardcoded/mock content

### Phase 2: Completeness

**API Completeness** (current: 66/100):
- 1/3 API routes are stubs with no real backend logic
- STUB: /api/observability/daemon/self-heal/event returns hardcoded/minimal response

**Cross-Hub Connectivity** (current: 50/100):
- Links to 1 other hubs: /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 2 connections

### Phase 3: Polish & Performance

**Workflows** (current: 70/100):
- 7/7 actions have working backends
- No chain workflows found — no automated multi-step flows

## Consequences

### Positive

- Observability hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Observability AI Workflow Suite

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
- Audit report: `observability` hub audit
- Audit timestamp: 2026-02-25T00:23:35.670342

## User Notes

MCP-first priority — Focus on wiring all actions to MCP tools. This hub should showcase the MCP integration pattern. All action backends should route through MCP tools rather than direct API calls.

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-147: Observability Hardening**.

Read the full ADR: `docs/decisions/ADR-147-observability-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-147-observability-hardening", description="Implementing ADR-147: Observability Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-147-observability-hardening", name="{role}",
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

**Team name**: `adr-147-observability-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (35/100): Best candidate: Observability AI Workflow Suite | `plugins/observability/skills/observe/dashboard.yaml`, `plugins/observability/skills/observe/dashboard/` |
| 1.2 | frontend | medium | Fix UI Compliance (25/100): No GlassCard usage in /observability/daemon/health | `plugins/observability/skills/observe/dashboard/daemon/health/page.tsx`, `plugins/observability/skills/observe/dashboard/daemon/health/page.tsx`, `plugins/observability/skills/observe/dashboard/daemon/health/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.3 | developer | medium | Fix Page Coverage (30/100): Missing page.tsx for tab 'Health' (/observability/health) | `plugins/observability/skills/observe/dashboard/` |
| 1.4 | devops | low | Fix MCP Tool Wiring (15/100): Actions defined but none use MCP tools — limited autonomy | `plugins/observability/skills/observe/dashboard.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.5 | frontend | medium | Fix Performance (34/100): Score capped at 60/100 — runtime telemetry needed for ful... | `plugins/observability/skills/observe/dashboard//page.tsx` |
| 1.6 | architect | high | Fix User Value (37/100): Data directory has no substantial data files — empty or t... | `plugins/observability/skills/observe/dashboard.yaml` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.7 | developer | medium | Fix API Completeness (66/100): 1/3 API routes are stubs with no real backend logic | `src/dashboard/app/api/observability/`, `src/dashboard/lib/services/` |
| 2.8 | developer | medium | Fix Cross-Hub Connectivity (50/100): Links to 1 other hubs: /health | `plugins/observability/skills/observe/dashboard/` |

#### Phase 3: Polish & Performance
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.9 | developer | medium | Fix Workflows (70/100): 7/7 actions have working backends | `plugins/observability/skills/observe/dashboard.yaml` | Chains: `generate_delight` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/observability in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 35/100 to >= 90
- [ ] UI Compliance improved from 25/100 to >= 90
- [ ] Page Coverage improved from 30/100 to >= 90
- [ ] MCP Tool Wiring improved from 15/100 to >= 90
- [ ] Performance improved from 34/100 to >= 90
- [ ] User Value improved from 37/100 to >= 90
- [ ] API Completeness improved from 66/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 50/100 to >= 90
- [ ] Workflows improved from 70/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-147 status updated to Accepted
