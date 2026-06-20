---
status: Superseded
date: '2026-02-11'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- career
- hub
- hardening
superseded_by: null
---

# ADR-066: Career Hub Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 54/100 | 12% | significant-gaps | No GlassCard usage in /career/companies |
| 2 | Page Coverage | 67/100 | 10% | significant-gaps | 7/15 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 9/100 | 12% | critical | 10/11 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 50/100 | 10% | significant-gaps | mcp_tools.yaml not found — cannot verify tool existence |
| 5 | Performance | 27/100 | 10% | critical | No code splitting for large page: /career/hardening/history |
| 6 | User Value | 59/100 | 15% | significant-gaps | 19 real data files found in career/ data dir |
| 7 | Workflows | 70/100 | 8% | needs-work | 10/12 actions have working backends |
| 8 | Cross-Hub Connectivity | 45/100 | 5% | critical | Links to 1 other hubs: /knowledge |
| 9 | Action Buttons | 58/100 | 8% | significant-gaps | 2/12 actions are fully-wired |
| 10 | Wow Effect | 40/100 | 10% | critical | Best candidate: Generate Report |

**Composite Score**: 47/100 (major-rebuild)

## Wow Effect: Generate Report

> Generate weekly activity report from all sources

**Score**: 40/100

**Demo Flow**:
1. User clicks 'Generate Report'
2. Runs automatically
3. Results displayed immediately

**Current state**: 13 candidate actions evaluated
**Gap to demo-ready**: Good static foundation — run /harden with dashboard running to verify live behavior

**Cross-hub leverage**: Pulls data from knowledge

**Other candidates**:
- Analyze Job (35/100, llm_action)
- Prep Interview (35/100, llm_action)
- Update Resume (35/100, llm_action)
- Harden Knowledge (35/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Career Hub** (http://localhost:3000/career) on 2026-02-11.
Composite score: **47/100**.

### Issues Identified

**UI Compliance** (54/100):
- No GlassCard usage in /career/companies
- Missing proper layout structure in /career/companies
- No interactive elements in /career/companies — static display only

**Page Coverage** (67/100):
- 7/15 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Companies' uses hardcoded arrays/objects, no real data fetching

**API Completeness** (9/100):
- 10/11 API routes are stubs with no real backend logic
- STUB: /api/career/habits returns hardcoded/minimal response
- STUB: /api/career/hardening/reading returns hardcoded/minimal response

**MCP Tool Wiring** (50/100):
- mcp_tools.yaml not found — cannot verify tool existence
- No pages make direct MCP tool calls — tools defined but not used in UI

**Performance** (27/100):
- No code splitting for large page: /career/hardening/history
- Large page (424 lines): /career/hardening
- No code splitting for large page: /career/hardening

**User Value** (59/100):
- 19 real data files found in career/ data dir
- 9/11 API routes have real backend logic
- 1/15 pages fetch real data

**Cross-Hub Connectivity** (45/100):
- Links to 1 other hubs: /knowledge
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 2 connections

**Action Buttons** (58/100):
- 2/12 actions are fully-wired
- 10/12 actions are frontend-only
- Modal 'add-star' has fields but no submitTool

**Wow Effect** (40/100):
- Best candidate: Generate Report
- Description: Generate weekly activity report from all sources
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 40/100):
- Best candidate: Generate Report
- Description: Generate weekly activity report from all sources
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

**API Completeness** (current: 9/100):
- 10/11 API routes are stubs with no real backend logic
- STUB: /api/career/habits returns hardcoded/minimal response
- STUB: /api/career/hardening/reading returns hardcoded/minimal response

**Performance** (current: 27/100):
- No code splitting for large page: /career/hardening/history
- Large page (424 lines): /career/hardening
- No code splitting for large page: /career/hardening

**Cross-Hub Connectivity** (current: 45/100):
- Links to 1 other hubs: /knowledge
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 2 connections

### Phase 2: Completeness

**UI Compliance** (current: 54/100):
- No GlassCard usage in /career/companies
- Missing proper layout structure in /career/companies
- No interactive elements in /career/companies — static display only

**Page Coverage** (current: 67/100):
- 7/15 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Companies' uses hardcoded arrays/objects, no real data fetching

**MCP Tool Wiring** (current: 50/100):
- mcp_tools.yaml not found — cannot verify tool existence
- No pages make direct MCP tool calls — tools defined but not used in UI

**User Value** (current: 59/100):
- 19 real data files found in career/ data dir
- 9/11 API routes have real backend logic
- 1/15 pages fetch real data

**Action Buttons** (current: 58/100):
- 2/12 actions are fully-wired
- 10/12 actions are frontend-only
- Modal 'add-star' has fields but no submitTool

### Phase 3: Polish & Performance

**Workflows** (current: 70/100):
- 10/12 actions have working backends
- 2/12 actions are YAML-only with no working backend
- Modal 'add-star' has no submitTool — form submits to nothing

## Consequences

### Positive

- Career Hub hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Generate Report

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
- Audit report: `career` hub audit
- Audit timestamp: 2026-02-11T14:08:23.420370

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-066: Career Hub Hardening**.

Read the full ADR: `docs/decisions/ADR-066-career-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-066-career-hardening", description="Implementing ADR-066: Career Hub Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-066-career-hardening", name="{role}",
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

**Team name**: `adr-066-career-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (40/100): Best candidate: Generate Report | `plugins/career/skills/career/augur.yaml`, `plugins/career/skills/career/augur/` |
| 1.2 | developer | medium | Fix API Completeness (9/100): 10/11 API routes are stubs with no real backend logic | `src/dashboard/app/api/career/`, `src/dashboard/lib/services/` |
| 1.3 | frontend | medium | Fix Performance (27/100): No code splitting for large page: /career/hardening/history | `plugins/career/skills/career/augur/hardening/history/page.tsx`, `plugins/career/skills/career/augur/hardening/page.tsx`, `plugins/career/skills/career/augur/hardening/page.tsx` |
| 1.4 | developer | medium | Fix Cross-Hub Connectivity (45/100): Links to 1 other hubs: /knowledge | `plugins/career/skills/career/augur/` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.5 | frontend | medium | Fix UI Compliance (54/100): No GlassCard usage in /career/companies | `plugins/career/skills/career/augur/companies/page.tsx`, `plugins/career/skills/career/augur/companies/page.tsx`, `plugins/career/skills/career/augur/companies/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.6 | developer | medium | Fix Page Coverage (67/100): 7/15 pages use mock/hardcoded data instead of real fetching | `plugins/career/skills/career/augur/` |
| 2.7 | devops | low | Fix MCP Tool Wiring (50/100): mcp_tools.yaml not found — cannot verify tool existence | `plugins/career/skills/career/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 2.8 | architect | high | Fix User Value (59/100): 19 real data files found in career/ data dir | `plugins/career/skills/career/augur.yaml` |
| 2.9 | frontend | medium | Fix Action Buttons (58/100): 2/12 actions are fully-wired | `plugins/career/skills/career/augur.yaml` |

#### Phase 3: Polish & Performance
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.10 | developer | medium | Fix Workflows (70/100): 10/12 actions have working backends | `plugins/career/skills/career/augur.yaml` | Chains: `generate_delight` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 40/100 to >= 90
- [ ] API Completeness improved from 9/100 to >= 90
- [ ] Performance improved from 27/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 45/100 to >= 90
- [ ] UI Compliance improved from 54/100 to >= 90
- [ ] Page Coverage improved from 67/100 to >= 90
- [ ] MCP Tool Wiring improved from 50/100 to >= 90
- [ ] User Value improved from 59/100 to >= 90
- [ ] Action Buttons improved from 58/100 to >= 90
- [ ] Workflows improved from 70/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] ADR-066 status updated to Accepted
