---
status: Implemented
date: '2026-03-02'
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

# ADR-228: Lifestyle Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 78/100 | 12% | needs-work | Missing proper layout structure in /lifestyle/books/book-... |
| 2 | Page Coverage | 50/100 | 10% | significant-gaps | 5/7 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 93/100 | 12% | good | 1/15 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 58/100 | 10% | significant-gaps | 13 actions have mcp_tool field (API-wrapped pattern) |
| 5 | Performance | 100/100 | 10% | good | No code splitting for large page: /lifestyle/books/book-n... |
| 6 | User Value | 74/100 | 15% | needs-work | 37 real data files found across 2/2 skills |
| 7 | Workflows | 52/100 | 8% | significant-gaps | 7/13 actions have working backends |
| 8 | Cross-Hub Connectivity | 100/100 | 5% | good | Links to 3 other hubs: /career, /finance, /health |
| 9 | Action Buttons | 76/100 | 8% | needs-work | 7/13 actions are fully-wired |
| 10 | Wow Effect | 100/100 | 10% | good | Best candidate: Recommend Books |

**Composite Score**: 77/100 (good-foundation)

**Scoring Confidence Note**: Action metrics use different semantics across dimensions (User Value: 1/13 autonomous, Workflows: 7/13 functional). Reconcile this classification during implementation. Perfect scores can still carry non-blocking advisory findings (for example, performance hygiene or environment-specific live validation) that must be verified in the execution plan.

## Wow Effect: Recommend Books

> AI suggests new books based on your collection and reading patterns

**Score**: 100/100

**Score breakdown**: static evidence 40/100 + runtime bonus 70 = 100/100

**Demo Flow**:
1. User clicks 'Recommend Books'
2. IDE chat opens with context
3. AI generates response
4. User reviews and applies at least one recommendation
5. User sees a persisted, dashboard-visible outcome from the applied recommendation

**Expected visible output**: AI suggests new books based on your collection and reading patterns, and at least one accepted recommendation becomes visible in dashboard state

**Current state**: 14 candidate actions/workflows evaluated with runtime verification
**Gap to demo-ready**: Good foundation, but the end-to-end live flow must be re-validated after all hardening changes to confirm no regressions

**Cross-hub leverage**: Pulls data from health

**Other candidates**:
- Find Connections (40/100, llm_action)
- Update Status (40/100, fast_action)
- Find Similar Recipes (40/100, llm_action)
- AI Meal Plan (40/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Lifestyle** (http://localhost:3000/lifestyle) on 2026-03-02.
Composite score: **77/100**.

### Issues Identified

**Page Coverage** (50/100):
- 5/7 pages use mock/hardcoded data instead of real fetching
- Mixed real/mock data in 'Overview' — still has hardcoded content
- Mixed real/mock data in 'Recipes' — still has hardcoded content

**MCP Tool Wiring** (58/100):
- 13 actions have mcp_tool field (API-wrapped pattern)
- 5/50 source files have MCP/API tool calls
- MCP module registered with 5 tools

**Workflows** (52/100):
- 7/13 actions have working backends
- 6/13 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

## Decision

Implement hardening in 3 phases, ordered by severity and user impact.

User-selected scope: **All Phases**.

Phase dependency rule: complete Phase 1 acceptance gate before starting Phase 2; rerun the full wow-effect acceptance gate in the Final Phase after all code changes.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 100/100):
- Best candidate: Recommend Books
- Description: AI suggests new books based on your collection and reading patterns
- Gap to demo-ready: Good foundation, but rerun full live flow after Phases 2-3 to confirm regression-free behavior

### Phase 2: Completeness

**Page Coverage** (current: 50/100):
- 5/7 pages use mock/hardcoded data instead of real fetching
- Mixed real/mock data in 'Overview' — still has hardcoded content
- Mixed real/mock data in 'Recipes' — still has hardcoded content

**MCP Tool Wiring** (current: 58/100):
- 13 actions have mcp_tool field (API-wrapped pattern)
- 5/50 source files have MCP/API tool calls
- MCP module registered with 5 tools

**Workflows** (current: 52/100):
- 7/13 actions have working backends
- 6/13 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

### Phase 3: Polish & Performance

**UI Compliance** (current: 78/100):
- Missing proper layout structure in /lifestyle/books/book-notes
- Hardcoded background in /lifestyle/books/books
- Missing proper layout structure in /lifestyle/books/books

**User Value** (current: 74/100):
- 37 real data files found across 2/2 skills
- 13/15 API routes have real backend logic
- 3/12 pages fetch real data

**Action Buttons** (current: 76/100):
- 7/13 actions are fully-wired
- 6/13 actions are frontend-only
- Action 'add-book' references missing modal ''

## Consequences

### Positive

- Lifestyle hub upgraded with standardized hardening across 6 dimensions
- Phase 1 defines and protects the wow-effect acceptance gate; critical remediation executes in Phases 2-3
- Killer demo use case identified: Recommend Books

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
- Audit report: `lifestyle` hub audit
- Audit timestamp: 2026-03-02T20:58:32.973505

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-228: Lifestyle Hardening**.

Read the full ADR: `docs/decisions/ADR-228-lifestyle-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-193-lifestyle-hardening", description="Implementing ADR-228: Lifestyle Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-193-lifestyle-hardening", name="{role}",
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

**Team name**: `adr-193-lifestyle-hardening`

**Execution dependency rule**: Do not start Phase 2 until Step 1.1 passes. Do not close the ADR until Final Phase reruns and passes the wow-effect flow in a post-hardening state.

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Preserve Wow Effect (100/100) by defining executable acceptance checks and baseline evidence for: Recommend Books | `plugins/lifestyle/skills/lifestyle/augur/dashboard`, `plugins/lifestyle/skills/books/augur/dashboard`, `plugins/lifestyle/skills/books/dashboard` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Fix Page Coverage (50/100): 5/7 pages use mock/hardcoded data instead of real fetching | `plugins/lifestyle/skills/lifestyle/augur/dashboard`, `plugins/lifestyle/skills/books/augur/dashboard` |
| 2.2 | devops | low | Fix MCP Tool Wiring (58/100): 13 actions have mcp_tool field (API-wrapped pattern) | `plugins/lifestyle/skills/lifestyle/augur/mcp/__init__.py`, `plugins/lifestyle/skills/books/augur/mcp/__init__.py`, `plugins/lifestyle/skills/lifestyle/augur.yaml` |
| 2.3 | developer | medium | Fix Workflows (52/100): 7/13 actions have working backends (Chains: `generate_delight`) | `plugins/lifestyle/skills/lifestyle/augur/data/actions`, `plugins/lifestyle/skills/books/augur/data/actions` |

#### Phase 3: Polish & Performance
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Fix UI Compliance (78/100): Missing proper layout structure in /lifestyle/books/book-... (Chains: `ui_quality_audit`, `redesign_page`) | `plugins/lifestyle/skills/books/augur/dashboard/book-notes/page.tsx`, `plugins/lifestyle/skills/books/augur/dashboard/books/page.tsx`, `plugins/lifestyle/skills/books/augur/dashboard/page.tsx` |
| 3.2 | architect | high | Fix User Value (74/100): 37 real data files found across 2/2 skills | `plugins/lifestyle/skills/lifestyle/augur/api`, `plugins/lifestyle/skills/books/augur/api`, `plugins/lifestyle/skills/lifestyle/augur/data` |
| 3.3 | frontend | medium | Fix Action Buttons (76/100): 7/13 actions are fully-wired | `plugins/lifestyle/skills/lifestyle/augur.yaml`, `plugins/lifestyle/skills/books/augur.yaml`, `plugins/lifestyle/skills/lifestyle/augur/data` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/lifestyle in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` and `augur/data/actions/*.yaml` against `augur/mcp/__init__.py` registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |
| V.5 | developer | medium | Re-run the full Recommend Books wow-flow after Phases 2-3 and verify a user-visible persisted outcome in the dashboard |

### Completion Criteria

## Implementation Results (2026-03-02)

- Final hardening audit (`http://localhost:3003/lifestyle`, worktree-scoped):
  - Composite: **98/100**
  - UI Compliance: **90**
  - Page Coverage: **100**
  - API Completeness: **100**
  - MCP Tool Wiring: **100**
  - User Value: **100**
  - Workflows: **90**
  - Action Buttons: **100**
  - Wow Effect: **100** (candidate shifted to **Add Book** after hardening)
- Build/test verification:
  - `pytest tests/src/` -> **21 passed**
  - `npm run build` (with `AUGUR_ROOT`, `AUGUR_RUNTIME`) -> **passed**
- Browser validation:
  - Chrome MCP route sweep completed for `/lifestyle`, all core tabs, and books subpages
  - Screenshots captured for each validated tab
  - Console errors: **0**
  - Auth/UX leak check: no `"Failed to fetch"` surfaced in page content
- MCP validation:
  - Registered tools discovered from `plugins/lifestyle/skills/{lifestyle,books}/augur/mcp/__init__.py`: 11
  - `mcp_tool` references checked in `augur.yaml` + `augur/data/actions/*.yaml`: 13
  - Missing references: **0**
- Structural integrity:
  - `structural_issues` in final audit report: empty

- [x] Wow Effect maintained at >= 95/100 with a verified live demo flow
- [x] Post-hardening wow-flow rerun passes after Phases 2-3 with a user-visible persisted outcome
- [x] Page Coverage improved from 50/100 to >= 90
- [x] MCP Tool Wiring improved from 58/100 to >= 90
- [x] Workflows improved from 52/100 to >= 90
- [x] UI Compliance improved from 78/100 to >= 90
- [x] User Value improved from 74/100 to >= 90
- [x] Action Buttons improved from 76/100 to >= 90
- [x] All phases executed
- [x] All tests pass (`pytest tests/src/`, `npm run build`)
- [x] Browser validation: page renders in Chrome MCP with zero console errors
- [x] MCP validation: all tool references in `augur.yaml` and `augur/data/actions/*.yaml` resolve to registered tools
- [x] No orphaned files or broken references
- [x] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)
- [x] No structural integrity issues (`structural_issues` in audit report is empty)
- [x] ADR-228 status updated to Accepted
