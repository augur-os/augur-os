---
status: Implemented
date: '2026-02-12'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- knowledge
- hardening
superseded_by: null
---

# ADR-082: Knowledge Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 55/100 | 12% | significant-gaps | No GlassCard usage in /knowledge/documents |
| 2 | Page Coverage | 88/100 | 10% | needs-work | 1/6 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 90/100 | 12% | good | 2/22 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 25/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 29/100 | 10% | critical | Large page (764 lines): /knowledge/memory |
| 6 | User Value | 49/100 | 15% | critical | 4 real data files found in knowledge/ data dir |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 40/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 40/100 (major-rebuild)

## Wow Effect: Semantic Memory Search

> Type a question, get real-time hybrid search results across decisions, patterns, and preferences with confidence scores and source links

**Score**: 0/100

**Demo Flow**:
1. User types a natural language question in the search bar
2. Frontend calls POST /api/knowledge/memory/search with hybrid mode
3. Backend runs BM25 + semantic search across MEMORY.md and daily logs
4. Results displayed with confidence scores, category badges, and date
5. Click a result to navigate to the source (daily log or MEMORY.md section)

**Current state**: Memory search widget exists on memory page but search API is not wired to it
**Gap to demo-ready**: Wire existing memory search API into a polished search UI with real-time results, filters, and source navigation

**Cross-hub leverage**: Pulls data from career decisions surface in career hub context, health patterns link to health hub

**Other candidates**:
- Curate Memory (60/100, )
- Knowledge Graph (50/100, )
- Human API Profile (45/100, )

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Knowledge** (http://localhost:3000/knowledge) on 2026-02-12.
Composite score: **40/100**.

### Issues Identified

**UI Compliance** (55/100):
- No GlassCard usage in /knowledge/documents
- No interactive elements in /knowledge/documents — static display only
- No loading states or error handling in /knowledge/documents

**MCP Tool Wiring** (25/100):
- No explicit MCP tool references in actions/modals
- 1/6 pages have MCP tool calls
- MCP module registered with 15 tools

**Performance** (29/100):
- Large page (764 lines): /knowledge/memory
- No code splitting for large page: /knowledge/memory
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (49/100):
- 4 real data files found in knowledge/ data dir
- 18/22 API routes have real backend logic
- 1/6 pages fetch real data

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (40/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 3 connections

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

**MCP Tool Wiring** (current: 25/100):
- No explicit MCP tool references in actions/modals
- 1/6 pages have MCP tool calls
- MCP module registered with 15 tools

**Performance** (current: 29/100):
- Large page (764 lines): /knowledge/memory
- No code splitting for large page: /knowledge/memory
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (current: 49/100):
- 4 real data files found in knowledge/ data dir
- 18/22 API routes have real backend logic
- 1/6 pages fetch real data

**Workflows** (current: 0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (current: 40/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 3 connections

**Action Buttons** (current: 0/100):
- No action buttons defined — hub has no interactivity

### Phase 2: Completeness

**UI Compliance** (current: 55/100):
- No GlassCard usage in /knowledge/documents
- No interactive elements in /knowledge/documents — static display only
- No loading states or error handling in /knowledge/documents

### Phase 3: Polish & Performance

**Page Coverage** (current: 88/100):
- 1/6 pages use mock/hardcoded data instead of real fetching
- MOCK DATA: 'Overview' uses hardcoded arrays/objects, no real data fetching

## Consequences

### Positive

- Knowledge hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Semantic Memory Search

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
- Audit report: `knowledge` hub audit
- Audit timestamp: 2026-02-12T09:34:48.030651

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-082: Knowledge Hardening**.

Read the full ADR: `docs/decisions/ADR-082-knowledge-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-082-knowledge-hardening", description="Implementing ADR-082: Knowledge Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-082-knowledge-hardening", name="{role}",
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

**Team name**: `adr-082-knowledge-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (0/100): Best candidate: No wow effect identified | `plugins/ai/skills/knowledge/augur.yaml`, `plugins/ai/skills/knowledge/augur/` |
| 1.2 | devops | low | Fix MCP Tool Wiring (25/100): No explicit MCP tool references in actions/modals | `plugins/ai/skills/knowledge/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.3 | frontend | medium | Fix Performance (29/100): Large page (764 lines): /knowledge/memory | `plugins/ai/skills/knowledge/augur/memory/page.tsx`, `plugins/ai/skills/knowledge/augur/memory/page.tsx`, `plugins/ai/skills/knowledge/augur//page.tsx` |
| 1.4 | architect | high | Fix User Value (49/100): 4 real data files found in knowledge/ data dir | `plugins/ai/skills/knowledge/augur.yaml` |
| 1.5 | developer | medium | Fix Workflows (0/100): No actions defined — hub has no workflows | `plugins/ai/skills/knowledge/augur.yaml` | Chains: `generate_delight` |
| 1.6 | developer | medium | Fix Cross-Hub Connectivity (40/100): No cross-hub navigation links — hub is isolated | `plugins/ai/skills/knowledge/augur/` |
| 1.7 | frontend | medium | Fix Action Buttons (0/100): No action buttons defined — hub has no interactivity | `plugins/ai/skills/knowledge/augur.yaml` |

#### Phase 2: Completeness
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.8 | frontend | medium | Fix UI Compliance (55/100): No GlassCard usage in /knowledge/documents | `plugins/ai/skills/knowledge/augur/documents/page.tsx`, `plugins/ai/skills/knowledge/augur/documents/page.tsx`, `plugins/ai/skills/knowledge/augur/documents/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |

#### Phase 3: Polish & Performance
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.9 | developer | medium | Fix Page Coverage (88/100): 1/6 pages use mock/hardcoded data instead of real fetching | `plugins/ai/skills/knowledge/augur/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/knowledge in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90
- [ ] MCP Tool Wiring improved from 25/100 to >= 90
- [ ] Performance improved from 29/100 to >= 90
- [ ] User Value improved from 49/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 40/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] UI Compliance improved from 55/100 to >= 90
- [ ] Page Coverage improved from 88/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] ADR-082 status updated to Accepted

## User Notes

Search is the priority — RAG search and document discovery are the primary use cases for this hub. Implementation should prioritize wiring the search and memory search APIs into polished UIs before addressing other dimensions.
