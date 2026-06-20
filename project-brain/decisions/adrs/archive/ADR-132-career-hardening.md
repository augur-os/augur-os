---
status: Implemented
date: '2026-02-21'
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

# ADR-132: Career Hub Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 58/100 | 12% | significant-gaps | Missing proper layout structure in /career/companies |
| 2 | Page Coverage | 69/100 | 10% | significant-gaps | 4/22 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 88/100 | 12% | needs-work | 2/17 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 7/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 40/100 | 10% | critical | Large page (315 lines): /career/growth/hardening |
| 6 | User Value | 30/100 | 15% | critical | No data directory — hub produces no persisted data |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 50/100 | 5% | significant-gaps | Links to 1 other hubs: /lifestyle |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 36/100 (major-rebuild)

## Wow Effect: AI Resume Tailoring

> Paste a job posting URL, AI generates a tailored resume from career data with downloadable PDF/preview output

**Score**: 0/100

**Demo Flow**:
1. User pastes job posting URL or description
2. AI extracts key requirements and keywords
3. System pulls user's career data (experience, skills, STAR stories)
4. AI generates tailored resume matching job requirements
5. Preview rendered in-page with download option

**Current state**: No interactive workflows
**Gap to demo-ready**: Build action button, MCP tool for resume generation, PDF export, job posting parser

**Cross-hub leverage**: Pulls data from growth/knowledge for skills data, star for STAR stories, companies for company research

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Career Hub** (http://localhost:3000/career) on 2026-02-21.
Composite score: **36/100**.

### Issues Identified

**UI Compliance** (58/100):
- Missing proper layout structure in /career/companies
- No interactive elements in /career/companies — static display only
- No GlassCard usage in /career/content/books

**Page Coverage** (69/100):
- 4/22 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Companies' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Blog Posts' uses hardcoded arrays/objects, no real data fetching

**MCP Tool Wiring** (7/100):
- No explicit MCP tool references in actions/modals
- 6/23 pages have MCP tool calls

**Performance** (40/100):
- Large page (315 lines): /career/growth/hardening
- Large page (300 lines): /career/growth/hardening/quiz
- Large page (351 lines): /career/growth/knowledge

**User Value** (30/100):
- No data directory — hub produces no persisted data
- 15/17 API routes have real backend logic
- 5/23 pages fetch real data

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (50/100):
- Links to 1 other hubs: /lifestyle
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 2 connections

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity

**Wow Effect** (0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 0/100):
- Best candidate: No wow effect identified
- Description: Hub has no complete actions that could serve as a demo
- Gap to demo-ready: Add at least one action with real backend, real data, and visible output

**MCP Tool Wiring** (current: 7/100):
- No explicit MCP tool references in actions/modals
- 6/23 pages have MCP tool calls

**Performance** (current: 40/100):
- Large page (315 lines): /career/growth/hardening
- Large page (300 lines): /career/growth/hardening/quiz
- Large page (351 lines): /career/growth/knowledge

**User Value** (current: 30/100):
- No data directory — hub produces no persisted data
- 15/17 API routes have real backend logic
- 5/23 pages fetch real data

**Workflows** (current: 0/100):
- No actions defined — hub has no workflows

**Action Buttons** (current: 0/100):
- No action buttons defined — hub has no interactivity

### Phase 2: Completeness

**UI Compliance** (current: 58/100):
- Missing proper layout structure in /career/companies
- No interactive elements in /career/companies — static display only
- No GlassCard usage in /career/content/books

**Page Coverage** (current: 69/100):
- 4/22 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Companies' uses hardcoded arrays/objects, no real data fetching
- MOCK DATA: 'Blog Posts' uses hardcoded arrays/objects, no real data fetching

**Cross-Hub Connectivity** (current: 50/100):
- Links to 1 other hubs: /lifestyle
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 2 connections

### Phase 3: Polish & Performance

**API Completeness** (current: 88/100):
- 2/17 API routes are stubs with no real backend logic
- STUB: /api/career/linkedin-writer/posts/delete returns hardcoded/minimal response
- STUB: /api/career/linkedin-writer/posts/publish returns hardcoded/minimal response

## Consequences

### Positive

- Career Hub hub upgraded with standardized hardening across 10 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: AI Resume Tailoring

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
- Audit timestamp: 2026-02-21T01:35:24.513265

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-132: Career Hub Hardening**.

Read the full ADR: `docs/decisions/ADR-132-career-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-132-career-hardening", description="Implementing ADR-132: Career Hub Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-132-career-hardening", name="{role}",
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

**Team name**: `adr-132-career-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (0/100): Best candidate: No wow effect identified | `plugins/career/skills/career/augur.yaml`, `plugins/career/skills/career/augur/` |
| 1.2 | devops | low | Fix MCP Tool Wiring (7/100): No explicit MCP tool references in actions/modals | `plugins/career/skills/career/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.3 | frontend | medium | Fix Performance (40/100): Large page (315 lines): /career/growth/hardening | `plugins/career/skills/career/augur/growth/hardening/page.tsx`, `plugins/career/skills/career/augur/growth/hardening/quiz/page.tsx`, `plugins/career/skills/career/augur/growth/knowledge/page.tsx` |
| 1.4 | architect | high | Fix User Value (30/100): No data directory — hub produces no persisted data | `plugins/career/skills/career/augur.yaml` |
| 1.5 | developer | medium | Fix Workflows (0/100): No actions defined — hub has no workflows | `plugins/career/skills/career/augur.yaml` | Chains: `generate_delight` |
| 1.6 | frontend | medium | Fix Action Buttons (0/100): No action buttons defined — hub has no interactivity | `plugins/career/skills/career/augur.yaml` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.7 | frontend | medium | Fix UI Compliance (58/100): Missing proper layout structure in /career/companies | `plugins/career/skills/career/augur/companies/page.tsx`, `plugins/career/skills/career/augur/companies/page.tsx`, `plugins/career/skills/career/augur/content/books/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.8 | developer | medium | Fix Page Coverage (69/100): 4/22 pages use mock/hardcoded data instead of real fetching | `plugins/career/skills/career/augur/` |
| 2.9 | developer | medium | Fix Cross-Hub Connectivity (50/100): Links to 1 other hubs: /lifestyle | `plugins/career/skills/career/augur/` |

#### Phase 3: Polish & Performance
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.10 | developer | medium | Fix API Completeness (88/100): 2/17 API routes are stubs with no real backend logic | `src/dashboard/app/api/career/`, `src/dashboard/lib/services/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/career in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90
- [ ] MCP Tool Wiring improved from 7/100 to >= 90
- [ ] Performance improved from 40/100 to >= 90
- [ ] User Value improved from 30/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] UI Compliance improved from 58/100 to >= 90
- [ ] Page Coverage improved from 69/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 50/100 to >= 90
- [ ] API Completeness improved from 88/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-132 status updated to Accepted

## User Notes

Career hub is **high-priority** — this is a frequently used hub. Prioritize polish and user value throughout all phases. The wow effect (AI Resume Tailoring) should be the headline feature with a polished, production-quality UX.
