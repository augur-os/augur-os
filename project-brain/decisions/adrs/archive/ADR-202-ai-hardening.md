---
status: Implemented
date: '2026-03-03'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- hardening
superseded_by: null
---

# ADR-202: Ai Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 51/100 | 12% | significant-gaps | No GlassCard usage in /ai/scraper/jobs |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 60/100 | 10% | significant-gaps | 0 actions have mcp_tool field (API-wrapped pattern) |
| 5 | Performance | 78/100 | 10% | needs-work | Runtime probe: pages 4/4 (avg 293ms), apis 4/4 (avg 42ms) |
| 6 | User Value | 45/100 | 15% | critical | 8 real data files found across 1/1 skills |
| 7 | Workflows | 60/100 | 8% | significant-gaps | 5/5 actions have working backends |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 100/100 | 8% | good | 5/5 actions are fully-wired |
| 10 | Wow Effect | 100/100 | 10% | good | Best candidate: Add Source |

**Composite Score**: 71/100 (good-foundation)

## Wow Effect: Add Source

> Register a new source domain for local-first scraping

**Score**: 100/100

**Score breakdown**: static evidence 40/100 + runtime bonus 70 = 100/100

**Demo Flow**:
1. User clicks 'Add Source'
2. IDE chat opens with context
3. AI generates response
4. User reviews and applies

**Expected visible output**: Register a new source domain for local-first scraping

**Current state**: 6 candidate actions/workflows evaluated with runtime verification
**Gap to demo-ready**: Runtime verified — polish the demo narrative and visible output for stakeholder walkthroughs

**Cross-hub leverage**: Pulls data from career

**Other candidates**:
- Ai AI Workflow Suite (35/100, multi_action_suite)
- Analyze Content (20/100, llm_action)
- Capture Authenticated Page (20/100, llm_action)
- Clear Old Content (20/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Ai** (http://localhost:3000/ai/scraper) on 2026-03-03.
Composite score: **71/100**.

### Issues Identified

**UI Compliance** (51/100):
- No GlassCard usage in /ai/scraper/jobs
- No interactive elements in /ai/scraper/jobs — static display only
- No loading states or error handling in /ai/scraper/jobs

**MCP Tool Wiring** (60/100):
- 0 actions have mcp_tool field (API-wrapped pattern)
- MCP module registered with 10 tools

**User Value** (45/100):
- 8 real data files found across 1/1 skills
- All 4 API routes are stubs — no real processing
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (60/100):
- 5/5 actions have working backends
- No chain workflows found — no automated multi-step flows

**Cross-Hub Connectivity** (0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

## Decision

Implement hardening in 3 phases, ordered by severity and user impact.

User-selected scope: **All Phases**.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 100/100):
- Best candidate: Add Source
- Description: Register a new source domain for local-first scraping
- UI evidence: surfaced in 1 hub source files

**User Value** (current: 45/100):
- 8 real data files found across 1/1 skills
- All 4 API routes are stubs — no real processing
- No pages fetch real data — all use hardcoded/mock content

**Cross-Hub Connectivity** (current: 0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

### Phase 2: Completeness

**UI Compliance** (current: 51/100):
- No GlassCard usage in /ai/scraper/jobs
- No interactive elements in /ai/scraper/jobs — static display only
- No loading states or error handling in /ai/scraper/jobs

**MCP Tool Wiring** (current: 60/100):
- 0 actions have mcp_tool field (API-wrapped pattern)
- MCP module registered with 10 tools

**Workflows** (current: 60/100):
- 5/5 actions have working backends
- No chain workflows found — no automated multi-step flows

### Phase 3: Polish & Performance

**Performance** (current: 78/100):
- Runtime probe: pages 4/4 (avg 293ms), apis 4/4 (avg 42ms)

## Consequences

### Positive

- Ai hub upgraded with standardized hardening across 7 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Add Source

### Negative

- Requires implementation effort across 7 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `ai_scraper` extension audit (/ai/scraper)
- Audit timestamp: 2026-03-03T16:52:58.519291

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-202: Ai Hardening**.

Read the full ADR: `docs/decisions/ADR-202-ai-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-202-ai-hardening", description="Implementing ADR-202: Ai Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-202-ai-hardening", name="{role}",
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

**Team name**: `adr-202-ai-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: MIXED (lock wow-effect acceptance criteria first, then parallelize remaining critical dimensions)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Preserve Wow Effect (100/100) with live demo validation: Best candidate: Add Source | `plugins/ai/skills/scraper/augur/dashboard`, `plugins/ai/skills/scraper/augur.yaml` |
| 1.2 | architect | high | Fix User Value (45/100): 8 real data files found across 1/1 skills | `plugins/ai/skills/scraper/augur/api`, `plugins/ai/skills/scraper/augur/data`, `plugins/ai/skills/scraper/augur.yaml` |
| 1.3 | developer | medium | Fix Cross-Hub Connectivity (0/100): No cross-hub navigation links — hub is isolated | `plugins/ai/skills/scraper/augur/dashboard` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

Dependency: complete Phase 1 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Fix UI Compliance (51/100): No GlassCard usage in /ai/scraper/jobs (Chains: `ui_quality_audit`, `redesign_page`) | `plugins/ai/skills/scraper/augur/dashboard/jobs/page.tsx`, `plugins/ai/skills/scraper/augur/dashboard/page.tsx`, `plugins/ai/skills/scraper/augur/dashboard/settings/page.tsx` |
| 2.2 | devops | low | Fix MCP Tool Wiring (60/100): 0 actions have mcp_tool field (API-wrapped pattern) | `plugins/ai/skills/scraper/augur/mcp/__init__.py`, `plugins/ai/skills/scraper/augur.yaml` |
| 2.3 | developer | medium | Fix Workflows (60/100): 5/5 actions have working backends | `plugins/ai/skills/scraper/augur/data/actions` |

#### Phase 3: Polish & Performance
**Strategy**: PIPELINE

Dependency: complete Phase 2 and merge results before starting.

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Fix Performance (78/100): Runtime probe: pages 4/4 (avg 293ms), apis 4/4 (avg 42ms) | `plugins/ai/skills/scraper/augur/dashboard` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/ai/scraper in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` and `augur/data/actions/*.yaml` against the current MCP tool registry/exposed server tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect maintained at >= 95/100 with a verified live demo flow
- [ ] Wow candidate is confirmed in hub UI source (action label/id binding), not manifest-only
- [ ] Wow demo includes before/after screenshots showing visible output
- [ ] User Value improved from 45/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] UI Compliance improved from 51/100 to >= 90
- [ ] MCP Tool Wiring improved from 60/100 to >= 90
- [ ] Workflows improved from 60/100 to >= 90
- [ ] Performance improved from 78/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in `augur.yaml` and `augur/data/actions/*.yaml` resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-202 status updated to Accepted
