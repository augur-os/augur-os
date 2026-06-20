---
status: Implemented
date: '2026-02-13'
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

# ADR-099: Finance Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 0/100 | 12% | critical | No page files found |
| 2 | Page Coverage | 0/100 | 10% | critical | Missing page.tsx for tab 'Dashboard' (/finance) |
| 3 | API Completeness | 10/100 | 12% | critical | No API directory but 1 actions need API backends |
| 4 | MCP Tool Wiring | 20/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 0/100 | 10% | critical | No pages to evaluate |
| 6 | User Value | 25/100 | 15% | critical | 7 real data files found in finance/ data dir |
| 7 | Workflows | 80/100 | 8% | needs-work | 4/4 actions have working backends |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No pages to check — hub is isolated |
| 9 | Action Buttons | 100/100 | 8% | good | 4/4 actions are fully-wired |
| 10 | Wow Effect | 20/100 | 10% | critical | Best candidate: Add Transaction |

**Composite Score**: 23/100 (major-rebuild)

## Wow Effect: Import Data

> Import and analyze financial data from Excel files (e.g., balance sheets)

**Score**: 20/100

**Demo Flow**:
1. User clicks "Import Data"
2. Select Excel file containing balance sheet
3. AI parses and categorizes transactions
4. View analyzed data with insights

**Current state**: 4 candidate actions evaluated
**Gap to demo-ready**: Needs file upload UI, Excel parser integration, and AI analysis pipeline

**Priority**: This is the first thing to implement in Phase 1.

## User Notes

> The main dashboard is top priority — currently looks bad and many buttons not working. Focus on dashboard UX first.

This informs the implementation order:
1. **Dashboard page** (`/finance`) must be the first page implemented and polished
2. Button functionality should be verified and fixed before moving to other tabs
3. Visual improvements should prioritize the main dashboard experience

## Context

Automated hardening audit of **Finance** (http://localhost:3000/finance) on 2026-02-13.
Composite score: **23/100**.

### Issues Identified

**UI Compliance** (0/100):
- No page files found

**Page Coverage** (0/100):
- Missing page.tsx for tab 'Dashboard' (/finance)
- Missing page.tsx for tab 'Accounts' (/finance/accounts)
- Missing page.tsx for tab 'Transactions' (/finance/transactions)

**API Completeness** (10/100):
- No API directory but 1 actions need API backends

**MCP Tool Wiring** (20/100):
- No explicit MCP tool references in actions/modals
- MCP module registered with 7 tools

**Performance** (0/100):
- No pages to evaluate

**User Value** (25/100):
- 7 real data files found in finance/ data dir
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content

**Cross-Hub Connectivity** (0/100):
- No pages to check — hub is isolated

**Wow Effect** (20/100):
- Best candidate: Add Transaction
- Description: Manually add a new income, expense, or transfer transaction
- Gap to demo-ready: Backend exists — needs live browser verification and end-to-end testing

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 20/100):
- Best candidate: Add Transaction
- Description: Manually add a new income, expense, or transfer transaction
- Gap to demo-ready: Backend exists — needs live browser verification and end-to-end testing

**UI Compliance** (current: 0/100):
- No page files found

**Page Coverage** (current: 0/100):
- Missing page.tsx for tab 'Dashboard' (/finance)
- Missing page.tsx for tab 'Accounts' (/finance/accounts)
- Missing page.tsx for tab 'Transactions' (/finance/transactions)

**API Completeness** (current: 10/100):
- No API directory but 1 actions need API backends

**MCP Tool Wiring** (current: 20/100):
- No explicit MCP tool references in actions/modals
- MCP module registered with 7 tools

**Performance** (current: 0/100):
- No pages to evaluate

**User Value** (current: 25/100):
- 7 real data files found in finance/ data dir
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content

**Cross-Hub Connectivity** (current: 0/100):
- No pages to check — hub is isolated

### Phase 3: Polish & Performance

**Workflows** (current: 80/100):
- 4/4 actions have working backends
- 1 chain workflow(s) found for this hub

## Consequences

### Positive

- Finance hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Import Data

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
- Audit report: `finance` hub audit
- Audit timestamp: 2026-02-13T22:31:02.128471

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-099: Finance Hardening**.

Read the full ADR: `docs/decisions/ADR-099-finance-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-099-finance-hardening", description="Implementing ADR-099: Finance Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-099-finance-hardening", name="{role}",
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

**Team name**: `adr-099-finance-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (20/100): Best candidate: Add Transaction | `plugins/finance/skills/finance/augur.yaml`, `plugins/finance/skills/finance/augur/` |
| 1.2 | frontend | medium | Fix UI Compliance (0/100): No page files found | `plugins/finance/skills/finance/augur/` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.3 | developer | medium | Fix Page Coverage (0/100): Missing page.tsx for tab 'Dashboard' (/finance) | `plugins/finance/skills/finance/augur/` |
| 1.4 | developer | medium | Fix API Completeness (10/100): No API directory but 1 actions need API backends | `src/dashboard/app/api/finance/`, `src/dashboard/lib/services/` |
| 1.5 | devops | low | Fix MCP Tool Wiring (20/100): No explicit MCP tool references in actions/modals | `plugins/finance/skills/finance/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.6 | frontend | medium | Fix Performance (0/100): No pages to evaluate | `plugins/finance/skills/finance/augur/` |
| 1.7 | architect | high | Fix User Value (25/100): 7 real data files found in finance/ data dir | `plugins/finance/skills/finance/augur.yaml` |
| 1.8 | developer | medium | Fix Cross-Hub Connectivity (0/100): No pages to check — hub is isolated | `plugins/finance/skills/finance/augur/` |

#### Phase 3: Polish & Performance
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.9 | developer | medium | Fix Workflows (80/100): 4/4 actions have working backends | `plugins/finance/skills/finance/augur.yaml` | Chains: `generate_delight` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/finance in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 20/100 to >= 90
- [ ] UI Compliance improved from 0/100 to >= 90
- [ ] Page Coverage improved from 0/100 to >= 90
- [ ] API Completeness improved from 10/100 to >= 90
- [ ] MCP Tool Wiring improved from 20/100 to >= 90
- [ ] Performance improved from 0/100 to >= 90
- [ ] User Value improved from 25/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] Workflows improved from 80/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] ADR-099 status updated to Accepted
