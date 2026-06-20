---
status: Implemented
date: '2026-02-11'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- health
- hub
- hardening
superseded_by: null
---

# ADR-068: Health Hub Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 35/100 | 12% | critical | No GlassCard usage in /health |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 0/100 | 12% | critical | 6/6 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 50/100 | 10% | significant-gaps | mcp_tools.yaml not found — cannot verify tool existence |
| 5 | Performance | 30/100 | 10% | critical | Score capped at 60/100 — runtime telemetry needed for ful... |
| 6 | User Value | 30/100 | 15% | critical | 1 real data files found in health/ data dir |
| 7 | Workflows | 60/100 | 8% | significant-gaps | 2/2 actions have working backends |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 100/100 | 8% | good | 2/2 actions are fully-wired |
| 10 | Wow Effect | 10/100 | 10% | critical | Best candidate: Add Symptom |

**Composite Score**: 40/100 (major-rebuild)

## Wow Effect: Virtual Doctor Chat

> AI-powered symptom analysis conversation — user describes symptoms, gets structured health insights and suggested actions

**Score**: 10/100

**Demo Flow**:
1. User clicks 'Virtual Doctor' action button
2. Chat interface opens with health context pre-loaded
3. User describes symptoms in natural language
4. AI analyzes against health history, medications, and symptom log
5. Returns structured assessment with severity, possible causes, and next steps
6. Conversation and findings saved to health data

**Current state**: Virtual doctor page exists but is static — no chat functionality
**Gap to demo-ready**: Requires new chat UI component, AI integration via action button flow, and wired-up health data APIs

**Cross-hub leverage**: Pulls data from wearables (Apple Health data for context)

**Other candidates**:
- Add Symptom (10/100, modal_workflow)
- Add Medication (10/100, modal_workflow)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Health Hub** (http://localhost:3000/health) on 2026-02-11.
Composite score: **40/100**.

### Issues Identified

**UI Compliance** (35/100):
- No GlassCard usage in /health
- No interactive elements in /health — static display only
- No loading states or error handling in /health

**API Completeness** (0/100):
- 6/6 API routes are stubs with no real backend logic
- STUB: /api/health/data returns hardcoded/minimal response
- STUB: /api/health/documents returns hardcoded/minimal response

**MCP Tool Wiring** (50/100):
- mcp_tools.yaml not found — cannot verify tool existence
- mcp_tools.yaml not found — cannot verify tool existence
- No pages make direct MCP tool calls — tools defined but not used in UI

**Performance** (30/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (30/100):
- 1 real data files found in health/ data dir
- All 6 API routes are stubs — no real processing
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (60/100):
- 2/2 actions have working backends
- No chain workflows found — no automated multi-step flows

**Cross-Hub Connectivity** (0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Wow Effect** (10/100):
- Best candidate: Add Symptom
- Gap to demo-ready: Action exists but lacks backend or data — wire up real API endpoints

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 10/100):
- Best candidate: Add Symptom
- Gap to demo-ready: Action exists but lacks backend or data — wire up real API endpoints

**UI Compliance** (current: 35/100):
- No GlassCard usage in /health
- No interactive elements in /health — static display only
- No loading states or error handling in /health

**API Completeness** (current: 0/100):
- 6/6 API routes are stubs with no real backend logic
- STUB: /api/health/data returns hardcoded/minimal response
- STUB: /api/health/documents returns hardcoded/minimal response

**Performance** (current: 30/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (current: 30/100):
- 1 real data files found in health/ data dir
- All 6 API routes are stubs — no real processing
- No pages fetch real data — all use hardcoded/mock content

**Cross-Hub Connectivity** (current: 0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

### Phase 2: Completeness

**MCP Tool Wiring** (current: 50/100):
- mcp_tools.yaml not found — cannot verify tool existence
- mcp_tools.yaml not found — cannot verify tool existence
- No pages make direct MCP tool calls — tools defined but not used in UI

**Workflows** (current: 60/100):
- 2/2 actions have working backends
- No chain workflows found — no automated multi-step flows

## Consequences

### Positive

- Health Hub hub upgraded with standardized hardening across 8 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Virtual Doctor Chat

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
- Audit report: `health` hub audit
- Audit timestamp: 2026-02-11T14:20:32.201023

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-068: Health Hub Hardening**.

Read the full ADR: `docs/decisions/ADR-068-health-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-068-health-hardening", description="Implementing ADR-068: Health Hub Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-068-health-hardening", name="{role}",
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

**Team name**: `adr-068-health-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (10/100): Best candidate: Add Symptom | `plugins/health/skills/health/dashboard.yaml`, `plugins/health/skills/health/dashboard/` |
| 1.2 | frontend | medium | Fix UI Compliance (35/100): No GlassCard usage in /health | `plugins/health/skills/health/dashboard//page.tsx`, `plugins/health/skills/health/dashboard//page.tsx`, `plugins/health/skills/health/dashboard//page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.3 | developer | medium | Fix API Completeness (0/100): 6/6 API routes are stubs with no real backend logic | `src/dashboard/app/api/health/`, `src/dashboard/lib/services/` |
| 1.4 | frontend | medium | Fix Performance (30/100): Score capped at 60/100 — runtime telemetry needed for ful... | `plugins/health/skills/health/dashboard//page.tsx` |
| 1.5 | architect | high | Fix User Value (30/100): 1 real data files found in health/ data dir | `plugins/health/skills/health/dashboard.yaml` |
| 1.6 | developer | medium | Fix Cross-Hub Connectivity (0/100): No cross-hub navigation links — hub is isolated | `plugins/health/skills/health/dashboard/` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.7 | devops | low | Fix MCP Tool Wiring (50/100): mcp_tools.yaml not found — cannot verify tool existence | `plugins/health/skills/health/dashboard.yaml`, `config/dashboard/mcp_tools.yaml` |
| 2.8 | developer | medium | Fix Workflows (60/100): 2/2 actions have working backends | `plugins/health/skills/health/dashboard.yaml` | Chains: `generate_delight` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 10/100 to >= 90
- [ ] UI Compliance improved from 35/100 to >= 90
- [ ] API Completeness improved from 0/100 to >= 90
- [ ] Performance improved from 30/100 to >= 90
- [ ] User Value improved from 30/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] MCP Tool Wiring improved from 50/100 to >= 90
- [ ] Workflows improved from 60/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] ADR-068 status updated to Accepted

## User Notes

Health data is sourced from user files added in a folder. APIs should read from local YAML/markdown files in the health data directory (`plugins/consulting/health/`). Privacy-first — no cloud sync for health data. All processing stays local.
