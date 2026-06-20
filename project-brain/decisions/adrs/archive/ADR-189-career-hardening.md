---
status: Implemented
date: '2026-03-01'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- career
- hardening
superseded_by: null
---

# ADR-189: Career Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 58/100 | 12% | significant-gaps | Missing proper layout structure in /career/companies |
| 2 | Page Coverage | 75/100 | 10% | needs-work | 6/17 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 95/100 | 12% | good | 1/20 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 82/100 | 10% | needs-work | 1 actions use API-wrapped MCP pattern |
| 5 | Performance | 93/100 | 10% | good | Runtime probe: pages 4/4 (avg 38ms), apis 4/4 (avg 51ms) |
| 6 | User Value | 63/100 | 15% | significant-gaps | 20 real data files found across 4/5 skills |
| 7 | Workflows | 72/100 | 8% | needs-work | 15/17 actions have working backends |
| 8 | Cross-Hub Connectivity | 80/100 | 5% | needs-work | Links to 4 other hubs: /ai, /lifestyle, /productivity, /p... |
| 9 | Action Buttons | 94/100 | 8% | good | 15/17 actions are fully-wired |
| 10 | Wow Effect | 100/100 | 10% | good | Best candidate: Analyze Job |

**Composite Score**: 80/100 (good-foundation)

## Wow Effect: Analyze Job

> Deep analysis of a job posting with fit scoring against career profile, skills inventory, and experience

**Score**: 100/100

**Demo Flow**:
1. User clicks 'Analyze Job' on Pipeline page or via action bar
2. IDE chat opens with job URL context and career profile
3. AI analyzes the job posting — fit scoring, skills match, gap analysis
4. User reviews analysis and decides next steps (apply, prep interview, tailor resume)

**Current state**: 18 candidate actions evaluated with runtime verification
**Gap to demo-ready**: Verify Analyze Job dispatch triggers IDE with correct context envelope

**Cross-hub leverage**: Pulls data from ai, lifestyle, productivity, professional

**Other candidates**:
- Analyze Job (40/100, llm_action)
- ATS Review (40/100, llm_action)
- Recalculate Scores (40/100, fast_action)
- Improve Writing (40/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Career** (http://localhost:3000/career) on 2026-03-01.
Composite score: **80/100**.

### Issues Identified

**UI Compliance** (58/100):
- Missing proper layout structure in /career/companies
- No GlassCard usage in /career/content/linkedin
- No interactive elements in /career/content/linkedin — static display only

**User Value** (63/100):
- 20 real data files found across 4/5 skills
- 13/20 API routes have real backend logic
- 9/25 pages fetch real data

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 100/100):
- Best candidate: Analyze Job
- Description: Deep analysis of a job posting with fit scoring against career profile, skills inventory, and experience
- Gap to demo-ready: Good static foundation — verify live Analyze Job flow end-to-end

### Phase 2: Completeness

**UI Compliance** (current: 58/100):
- Missing proper layout structure in /career/companies
- No GlassCard usage in /career/content/linkedin
- No interactive elements in /career/content/linkedin — static display only

**User Value** (current: 63/100):
- 20 real data files found across 4/5 skills
- 13/20 API routes have real backend logic
- 9/25 pages fetch real data

### Phase 3: Polish & Performance

**Page Coverage** (current: 75/100):
- 6/17 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Pipeline' uses hardcoded arrays/objects, no real data fetching

**MCP Tool Wiring** (current: 82/100):
- 1 actions use API-wrapped MCP pattern
- 10/25 pages have MCP tool calls
- MCP module registered with 25 tools

**Workflows** (current: 72/100):
- 15/17 actions have working backends
- 2/17 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

**Cross-Hub Connectivity** (current: 80/100):
- Links to 4 other hubs: /ai, /lifestyle, /productivity, /professional
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 3 connections

## Consequences

### Positive

- Career hub upgraded with standardized hardening across 6 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Wow effect: Analyze Job — deep job analysis with fit scoring

### Negative

- Requires implementation effort across 6 dimensions
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
- Audit timestamp: 2026-03-01T00:01:25.457608

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-189: Career Hardening**.

Read the full ADR: `docs/decisions/ADR-189-career-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-189-career-hardening", description="Implementing ADR-189: Career Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-189-career-hardening", name="{role}",
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

**Team name**: `adr-189-career-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (100/100): Best candidate: AI Tailor Resume | `plugins/career/skills/career/augur.yaml`, `plugins/career/skills/career/augur/dashboard/` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.2 | frontend | medium | Fix UI Compliance (58/100): Missing proper layout structure in /career/companies | `plugins/career/skills/career/augur/dashboard/companies/page.tsx`, `plugins/career/skills/career/augur/dashboard/content/linkedin/page.tsx`, `plugins/career/skills/career/augur/dashboard/content/linkedin/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.3 | architect | high | Fix User Value (63/100): 20 real data files found across 4/5 skills | `plugins/career/skills/career/augur.yaml` |

#### Phase 3: Polish & Performance
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.4 | developer | medium | Fix Page Coverage (75/100): 6/17 pages use mock/hardcoded data instead of real fetching | `plugins/career/skills/career/augur/dashboard/` |
| 3.5 | devops | low | Fix MCP Tool Wiring (82/100): 1 actions use API-wrapped MCP pattern | `plugins/career/skills/career/augur.yaml`, `plugins/career/skills/career/augur/mcp/__init__.py` |
| 3.6 | developer | medium | Fix Workflows (72/100): 15/17 actions have working backends | `plugins/career/skills/career/augur.yaml` | Chains: `generate_delight` |
| 3.7 | developer | medium | Fix Cross-Hub Connectivity (80/100): Links to 4 other hubs: /ai, /lifestyle, /productivity, /p... | `plugins/career/skills/career/augur/dashboard/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/career in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in augur.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 100/100 to >= 90
- [ ] UI Compliance improved from 58/100 to >= 90
- [ ] User Value improved from 63/100 to >= 90
- [ ] Page Coverage improved from 75/100 to >= 90
- [ ] MCP Tool Wiring improved from 82/100 to >= 90
- [ ] Workflows improved from 72/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 80/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in augur.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `augur.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-189 status updated to Accepted
