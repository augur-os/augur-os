---
status: Implemented
date: '2026-02-11'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- lifestyle
- hardening
superseded_by: null
---

# ADR-069: Lifestyle Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 66/100 | 12% | significant-gaps | No loading states or error handling in /lifestyle/ideas |
| 2 | Page Coverage | 47/100 | 10% | critical | 6/8 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 10/100 | 12% | critical | No API directory but 7 actions need API backends |
| 4 | MCP Tool Wiring | 15/100 | 10% | critical | Actions defined but none use MCP tools — limited autonomy |
| 5 | Performance | 26/100 | 10% | critical | No code splitting for large page: /lifestyle/ideas |
| 6 | User Value | 25/100 | 15% | critical | 23 real data files found in lifestyle/ data dir |
| 7 | Workflows | 47/100 | 8% | critical | 11/24 actions have working backends |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 50/100 | 8% | significant-gaps | 24/24 actions are frontend-only |
| 10 | Wow Effect | 15/100 | 10% | critical | Best candidate: Find Similar Recipes |

**Composite Score**: 30/100 (major-rebuild)

## Wow Effect: Find Similar Recipes

> AI finds recipes with similar ingredients or flavor profiles

**Score**: 15/100

**Demo Flow**:
1. User clicks 'Find Similar Recipes'
2. IDE chat opens with context
3. AI generates response
4. User reviews and applies

**Current state**: 25 candidate actions evaluated
**Gap to demo-ready**: Action exists but lacks backend or data — wire up real API endpoints

**Other candidates**:
- Complete Recipe (15/100, llm_action)
- Recipe Ideas (15/100, llm_action)
- Improve Recipe (15/100, llm_action)
- Plan Meals (15/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Lifestyle** (http://localhost:3000/lifestyle) on 2026-02-11.
Composite score: **30/100**.

### Issues Identified

**UI Compliance** (66/100):
- No loading states or error handling in /lifestyle/ideas
- No loading states or error handling in /lifestyle/movies
- No GlassCard usage in /lifestyle

**Page Coverage** (47/100):
- 6/8 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Shopping' uses hardcoded arrays/objects, no real data fetching

**API Completeness** (10/100):
- No API directory but 7 actions need API backends

**MCP Tool Wiring** (15/100):
- Actions defined but none use MCP tools — limited autonomy

**Performance** (26/100):
- No code splitting for large page: /lifestyle/ideas
- No code splitting for large page: /lifestyle/movies
- No code splitting for large page: /lifestyle

**User Value** (25/100):
- 23 real data files found in lifestyle/ data dir
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (47/100):
- 11/24 actions have working backends
- 13/24 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

**Cross-Hub Connectivity** (0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Action Buttons** (50/100):
- 24/24 actions are frontend-only

**Wow Effect** (15/100):
- Best candidate: Find Similar Recipes
- Description: AI finds recipes with similar ingredients or flavor profiles
- Gap to demo-ready: Action exists but lacks backend or data — wire up real API endpoints

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 15/100):
- Best candidate: Find Similar Recipes
- Description: AI finds recipes with similar ingredients or flavor profiles
- Gap to demo-ready: Action exists but lacks backend or data — wire up real API endpoints

**Page Coverage** (current: 47/100):
- 6/8 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Shopping' uses hardcoded arrays/objects, no real data fetching

**API Completeness** (current: 10/100):
- No API directory but 7 actions need API backends

**MCP Tool Wiring** (current: 15/100):
- Actions defined but none use MCP tools — limited autonomy

**Performance** (current: 26/100):
- No code splitting for large page: /lifestyle/ideas
- No code splitting for large page: /lifestyle/movies
- No code splitting for large page: /lifestyle

**User Value** (current: 25/100):
- 23 real data files found in lifestyle/ data dir
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (current: 47/100):
- 11/24 actions have working backends
- 13/24 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

**Cross-Hub Connectivity** (current: 0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

### Phase 2: Completeness

**UI Compliance** (current: 66/100):
- No loading states or error handling in /lifestyle/ideas
- No loading states or error handling in /lifestyle/movies
- No GlassCard usage in /lifestyle

**Action Buttons** (current: 50/100):
- 24/24 actions are frontend-only

## Consequences

### Positive

- Lifestyle hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Find Similar Recipes

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
- Audit report: `lifestyle` hub audit
- Audit timestamp: 2026-02-11T14:20:53.830833

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-069: Lifestyle Hardening**.

Read the full ADR: `docs/decisions/ADR-069-lifestyle-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-069-lifestyle-hardening", description="Implementing ADR-069: Lifestyle Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-069-lifestyle-hardening", name="{role}",
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

**Team name**: `adr-069-lifestyle-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (15/100): Best candidate: Find Similar Recipes | `plugins/lifestyle/skills/lifestyle/augur.yaml`, `plugins/lifestyle/skills/lifestyle/augur/` |
| 1.2 | developer | medium | Fix Page Coverage (47/100): 6/8 pages use mock/hardcoded data instead of real fetching | `plugins/lifestyle/skills/lifestyle/augur/` |
| 1.3 | developer | medium | Fix API Completeness (10/100): No API directory but 7 actions need API backends | `src/dashboard/app/api/lifestyle/`, `src/dashboard/lib/services/` |
| 1.4 | devops | low | Fix MCP Tool Wiring (15/100): Actions defined but none use MCP tools — limited autonomy | `plugins/lifestyle/skills/lifestyle/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.5 | frontend | medium | Fix Performance (26/100): No code splitting for large page: /lifestyle/ideas | `plugins/lifestyle/skills/lifestyle/augur/ideas/page.tsx`, `plugins/lifestyle/skills/lifestyle/augur/movies/page.tsx`, `plugins/lifestyle/skills/lifestyle/augur//page.tsx` |
| 1.6 | architect | high | Fix User Value (25/100): 23 real data files found in lifestyle/ data dir | `plugins/lifestyle/skills/lifestyle/augur.yaml` |
| 1.7 | developer | medium | Fix Workflows (47/100): 11/24 actions have working backends | `plugins/lifestyle/skills/lifestyle/augur.yaml` | Chains: `generate_delight` |
| 1.8 | developer | medium | Fix Cross-Hub Connectivity (0/100): No cross-hub navigation links — hub is isolated | `plugins/lifestyle/skills/lifestyle/augur/` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.9 | frontend | medium | Fix UI Compliance (66/100): No loading states or error handling in /lifestyle/ideas | `plugins/lifestyle/skills/lifestyle/augur/ideas/page.tsx`, `plugins/lifestyle/skills/lifestyle/augur/movies/page.tsx`, `plugins/lifestyle/skills/lifestyle/augur//page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.10 | frontend | medium | Fix Action Buttons (50/100): 24/24 actions are frontend-only | `plugins/lifestyle/skills/lifestyle/augur.yaml` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 15/100 to >= 90
- [ ] Page Coverage improved from 47/100 to >= 90
- [ ] API Completeness improved from 10/100 to >= 90
- [ ] MCP Tool Wiring improved from 15/100 to >= 90
- [ ] Performance improved from 26/100 to >= 90
- [ ] User Value improved from 25/100 to >= 90
- [ ] Workflows improved from 47/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] UI Compliance improved from 66/100 to >= 90
- [ ] Action Buttons improved from 50/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] ADR-069 status updated to Accepted

## User Notes

User should be able to paste a link as an idea draft and those will be converted to their special recipes — recipe URL import is a key user workflow. The wow effect ("Find Similar Recipes") and the broader recipe actions should support this: paste a URL, scrape/parse the recipe, normalize it into the user's format, and make it available for similarity matching, meal planning, and other AI actions.
