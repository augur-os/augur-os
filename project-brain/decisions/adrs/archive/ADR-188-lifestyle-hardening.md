---
status: Implemented
date: '2026-02-28'
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

# ADR-188: Lifestyle Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 47/100 | 12% | critical | No GlassCard usage in /lifestyle/books/book-notes |
| 2 | Page Coverage | 84/100 | 10% | needs-work | 2/9 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 90/100 | 12% | good | 1/11 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 20/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 73/100 | 10% | needs-work | No code splitting for large page: /lifestyle/books/books |
| 6 | User Value | 66/100 | 15% | significant-gaps | 35 real data files found across 2/2 skills |
| 7 | Workflows | 50/100 | 8% | significant-gaps | 6/12 actions have working backends |
| 8 | Cross-Hub Connectivity | 100/100 | 5% | good | Links to 3 other hubs: /career, /finance, /health |
| 9 | Action Buttons | 55/100 | 8% | significant-gaps | 5/12 actions are fully-wired |
| 10 | Wow Effect | 90/100 | 10% | good | Best candidate: Recommend Books |

**Composite Score**: 66/100 (significant-gaps)

## Wow Effect: Smart Book Notes

> AI-enhanced note-taking that links book concepts across your collection

**Score**: 90/100

**Demo Flow**:
1. User opens a book note and clicks "Find Connections"
2. AI scans all book notes for shared themes, concepts, and cross-references
3. Connections panel shows linked concepts with excerpts from related books
4. User can navigate between connected notes seamlessly

**Current state**: Book notes infrastructure exists with 17 annotated notes, inline editing, and markdown rendering. MCP tools (list-book-notes, get-book-note) provide data access.
**Gap to demo-ready**: Need AI concept linking action + connections panel UI in book-notes page

**Cross-hub leverage**: Pulls data from health (wellness reading), career (professional development books)

**Other candidates**:
- Recommend Books (40/100, llm_action)
- Update Status (40/100, fast_action)
- Find Similar Recipes (40/100, llm_action)
- AI Meal Plan (40/100, llm_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Lifestyle** (http://localhost:3000/lifestyle) on 2026-02-28.
Composite score: **66/100**.

### Issues Identified

**UI Compliance** (47/100):
- No GlassCard usage in /lifestyle/books/book-notes
- Missing proper layout structure in /lifestyle/books/book-notes
- No GlassCard usage in /lifestyle/books/books

**MCP Tool Wiring** (20/100):
- No explicit MCP tool references in actions/modals
- 2/12 pages have MCP tool calls
- MCP module registered with 5 tools

**User Value** (66/100):
- 35 real data files found across 2/2 skills
- 9/11 API routes have real backend logic
- 7/12 pages fetch real data

**Workflows** (50/100):
- 6/12 actions have working backends
- 6/12 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

**Action Buttons** (55/100):
- 5/12 actions are fully-wired
- 1/12 actions are frontend-only
- 6/12 actions are yaml-only

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 90/100):
- Best candidate: Recommend Books
- Description: AI suggests new books based on your collection and reading patterns
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

**UI Compliance** (current: 47/100):
- No GlassCard usage in /lifestyle/books/book-notes
- Missing proper layout structure in /lifestyle/books/book-notes
- No GlassCard usage in /lifestyle/books/books

**MCP Tool Wiring** (current: 20/100):
- No explicit MCP tool references in actions/modals
- 2/12 pages have MCP tool calls
- MCP module registered with 5 tools

### Phase 2: Completeness

**User Value** (current: 66/100):
- 35 real data files found across 2/2 skills
- 9/11 API routes have real backend logic
- 7/12 pages fetch real data

**Workflows** (current: 50/100):
- 6/12 actions have working backends
- 6/12 actions are YAML-only with no working backend
- No chain workflows found — no automated multi-step flows

**Action Buttons** (current: 55/100):
- 5/12 actions are fully-wired
- 1/12 actions are frontend-only
- 6/12 actions are yaml-only

### Phase 3: Polish & Performance

**Page Coverage** (current: 84/100):
- 2/9 pages use mock/hardcoded data instead of real fetching
- Mixed real/mock data in 'Overview' — still has hardcoded content
- MOCK DATA: 'Recipes' uses hardcoded arrays/objects, no real data fetching

**Performance** (current: 73/100):
- No code splitting for large page: /lifestyle/books/books
- Large page (318 lines): /lifestyle
- No code splitting for large page: /lifestyle

## Consequences

### Positive

- Lifestyle hub upgraded with standardized hardening across 7 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Recommend Books

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
- Audit report: `lifestyle` hub audit
- Audit timestamp: 2026-02-28T20:59:37.509896

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-188: Lifestyle Hardening**.

Read the full ADR: `docs/decisions/ADR-188-lifestyle-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-188-lifestyle-hardening", description="Implementing ADR-188: Lifestyle Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-188-lifestyle-hardening", name="{role}",
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

**Team name**: `adr-188-lifestyle-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (90/100): Best candidate: Recommend Books | `plugins/lifestyle/skills/lifestyle/dashboard.yaml`, `plugins/lifestyle/skills/lifestyle/dashboard/` |
| 1.2 | frontend | medium | Fix UI Compliance (47/100): No GlassCard usage in /lifestyle/books/book-notes | `plugins/lifestyle/skills/lifestyle/dashboard/books/book-notes/page.tsx`, `plugins/lifestyle/skills/lifestyle/dashboard/books/book-notes/page.tsx`, `plugins/lifestyle/skills/lifestyle/dashboard/books/books/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.3 | devops | low | Fix MCP Tool Wiring (20/100): No explicit MCP tool references in actions/modals | `plugins/lifestyle/skills/lifestyle/dashboard.yaml`, `config/dashboard/mcp_tools.yaml` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.4 | architect | high | Fix User Value (66/100): 35 real data files found across 2/2 skills | `plugins/lifestyle/skills/lifestyle/dashboard.yaml` |
| 2.5 | developer | medium | Fix Workflows (50/100): 6/12 actions have working backends | `plugins/lifestyle/skills/lifestyle/dashboard.yaml` | Chains: `generate_delight` |
| 2.6 | frontend | medium | Fix Action Buttons (55/100): 5/12 actions are fully-wired | `plugins/lifestyle/skills/lifestyle/dashboard.yaml` |

#### Phase 3: Polish & Performance
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.7 | developer | medium | Fix Page Coverage (84/100): 2/9 pages use mock/hardcoded data instead of real fetching | `plugins/lifestyle/skills/lifestyle/dashboard/` |
| 3.8 | frontend | medium | Fix Performance (73/100): No code splitting for large page: /lifestyle/books/books | `plugins/lifestyle/skills/lifestyle/dashboard/books/books/page.tsx`, `plugins/lifestyle/skills/lifestyle/dashboard//page.tsx`, `plugins/lifestyle/skills/lifestyle/dashboard//page.tsx` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/lifestyle in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 90/100 to >= 90
- [ ] UI Compliance improved from 47/100 to >= 90
- [ ] MCP Tool Wiring improved from 20/100 to >= 90
- [ ] User Value improved from 66/100 to >= 90
- [ ] Workflows improved from 50/100 to >= 90
- [ ] Action Buttons improved from 55/100 to >= 90
- [ ] Page Coverage improved from 84/100 to >= 90
- [ ] Performance improved from 73/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-188 status updated to Accepted

## User Notes

- **Wow Effect choice**: Smart Book Notes — AI-enhanced note-taking that links book concepts across the collection. User chose this over Recommend Books.
- **Scope**: Critical + Completeness — all dimensions below 70, plus Performance and Page Coverage.
- **No dimensions skipped** — include all failing dimensions in implementation.
