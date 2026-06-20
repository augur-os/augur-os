---
status: Implemented
date: '2026-02-11'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- finance
- hardening
superseded_by: null
---

# ADR-070: Finance Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 55/100 | 12% | significant-gaps | No GlassCard usage in /finance/accounts |
| 2 | Page Coverage | 79/100 | 10% | needs-work | 3/10 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 10/100 | 12% | critical | No API directory but 1 actions need API backends |
| 4 | MCP Tool Wiring | 15/100 | 10% | critical | Actions defined but none use MCP tools — limited autonomy |
| 5 | Performance | 30/100 | 10% | critical | Score capped at 60/100 — runtime telemetry needed for ful... |
| 6 | User Value | 0/100 | 15% | critical | Data directory has no substantial data files — empty or t... |
| 7 | Workflows | 50/100 | 8% | significant-gaps | 2/3 actions have working backends |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 50/100 | 8% | significant-gaps | 3/3 actions are frontend-only |
| 10 | Wow Effect | 15/100 | 10% | critical | Best candidate: Analyze Spending |

**Composite Score**: 29/100 (major-rebuild)

## Wow Effect: Analyze Spending

> AI analysis of spending patterns

**Score**: 15/100

**Demo Flow**:
1. User clicks 'Analyze Spending'
2. IDE chat opens with context
3. AI generates response
4. User reviews and applies

**Current state**: 3 candidate actions evaluated
**Gap to demo-ready**: Action exists but lacks backend or data — wire up real API endpoints

**Other candidates**:
- Tax Strategy (15/100, llm_action)
- Add Transaction (0/100, modal_workflow)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Finance** (http://localhost:3000/finance) on 2026-02-11.
Composite score: **29/100**.

### Issues Identified

**UI Compliance** (55/100):
- No GlassCard usage in /finance/accounts
- No interactive elements in /finance/accounts — static display only
- No loading states or error handling in /finance/accounts

**API Completeness** (10/100):
- No API directory but 1 actions need API backends

**MCP Tool Wiring** (15/100):
- Actions defined but none use MCP tools — limited autonomy

**Performance** (30/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (0/100):
- Data directory has no substantial data files — empty or template-only
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (50/100):
- 2/3 actions have working backends
- 1/3 actions are YAML-only with no working backend
- Modal 'add-transaction' has no submitTool — form submits to nothing

**Cross-Hub Connectivity** (0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Action Buttons** (50/100):
- 3/3 actions are frontend-only
- Modal 'add-transaction' has fields but no submitTool
- 1 actions missing descriptions

**Wow Effect** (15/100):
- Best candidate: Analyze Spending
- Description: AI analysis of spending patterns
- Gap to demo-ready: Action exists but lacks backend or data — wire up real API endpoints

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 15/100):
- Best candidate: Analyze Spending
- Description: AI analysis of spending patterns
- Gap to demo-ready: Action exists but lacks backend or data — wire up real API endpoints

**API Completeness** (current: 10/100):
- No API directory but 1 actions need API backends

**MCP Tool Wiring** (current: 15/100):
- Actions defined but none use MCP tools — limited autonomy

**Performance** (current: 30/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (current: 0/100):
- Data directory has no substantial data files — empty or template-only
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content

**Cross-Hub Connectivity** (current: 0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

### Phase 2: Completeness

**UI Compliance** (current: 55/100):
- No GlassCard usage in /finance/accounts
- No interactive elements in /finance/accounts — static display only
- No loading states or error handling in /finance/accounts

**Workflows** (current: 50/100):
- 2/3 actions have working backends
- 1/3 actions are YAML-only with no working backend
- Modal 'add-transaction' has no submitTool — form submits to nothing

**Action Buttons** (current: 50/100):
- 3/3 actions are frontend-only
- Modal 'add-transaction' has fields but no submitTool
- 1 actions missing descriptions

### Phase 3: Polish & Performance

**Page Coverage** (current: 79/100):
- 3/10 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Dashboard' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Budget' uses hardcoded arrays/objects, no real data fetching

## Consequences

### Positive

- Finance hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Analyze Spending

### Negative

- Requires implementation effort across 10 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## User Notes

- Don't skip any dimensions — include all in the hardening plan
- Data will come in as Excel input — prioritize Excel/CSV import pipeline for financial data ingestion

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `finance` hub audit
- Audit timestamp: 2026-02-11T14:20:13.626873

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-070: Finance Hardening**.

Read the full ADR: `docs/decisions/ADR-070-finance-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-070-finance-hardening", description="Implementing ADR-070: Finance Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-070-finance-hardening", name="{role}",
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

**Team name**: `adr-070-finance-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (15/100): Best candidate: Analyze Spending | `plugins/finance/skills/finance/augur.yaml`, `plugins/finance/skills/finance/augur/` |
| 1.2 | developer | medium | Fix API Completeness (10/100): No API directory but 1 actions need API backends | `src/dashboard/app/api/finance/`, `src/dashboard/lib/services/` |
| 1.3 | devops | low | Fix MCP Tool Wiring (15/100): Actions defined but none use MCP tools — limited autonomy | `plugins/finance/skills/finance/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.4 | frontend | medium | Fix Performance (30/100): Score capped at 60/100 — runtime telemetry needed for ful... | `plugins/finance/skills/finance/augur//page.tsx` |
| 1.5 | architect | high | Fix User Value (0/100): Data directory has no substantial data files — empty or t... | `plugins/finance/skills/finance/augur.yaml` |
| 1.6 | developer | medium | Fix Cross-Hub Connectivity (0/100): No cross-hub navigation links — hub is isolated | `plugins/finance/skills/finance/augur/` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.7 | frontend | medium | Fix UI Compliance (55/100): No GlassCard usage in /finance/accounts | `plugins/finance/skills/finance/augur/accounts/page.tsx`, `plugins/finance/skills/finance/augur/accounts/page.tsx`, `plugins/finance/skills/finance/augur/accounts/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.8 | developer | medium | Fix Workflows (50/100): 2/3 actions have working backends | `plugins/finance/skills/finance/augur.yaml` | Chains: `generate_delight` |
| 2.9 | frontend | medium | Fix Action Buttons (50/100): 3/3 actions are frontend-only | `plugins/finance/skills/finance/augur.yaml` |

#### Phase 3: Polish & Performance
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.10 | developer | medium | Fix Page Coverage (79/100): 3/10 pages use mock/hardcoded data instead of real fetching | `plugins/finance/skills/finance/augur/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 15/100 to >= 90
- [ ] API Completeness improved from 10/100 to >= 90
- [ ] MCP Tool Wiring improved from 15/100 to >= 90
- [ ] Performance improved from 30/100 to >= 90
- [ ] User Value improved from 0/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] UI Compliance improved from 55/100 to >= 90
- [ ] Workflows improved from 50/100 to >= 90
- [ ] Action Buttons improved from 50/100 to >= 90
- [ ] Page Coverage improved from 79/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] ADR-070 status updated to Accepted
