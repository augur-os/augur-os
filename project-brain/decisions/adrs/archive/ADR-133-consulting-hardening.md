---
status: Implemented
date: '2026-02-21'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- consulting
- hardening
superseded_by: null
---

# ADR-133: Consulting Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 50/100 | 12% | significant-gaps | No GlassCard usage in /consulting/client-ai-consulting/op... |
| 2 | Page Coverage | 65/100 | 10% | significant-gaps | 4/8 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 16/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 31/100 | 10% | critical | No code splitting for large page: /consulting/client-ai-c... |
| 6 | User Value | 38/100 | 15% | critical | No data directory — hub produces no persisted data |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 90/100 | 5% | good | Links to 2 other hubs: /ai, /health |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 0/100 | 10% | critical | Best candidate: No wow effect identified |

**Composite Score**: 39/100 (major-rebuild)

## Wow Effect: Smart Session Prep

> Before a client meeting, AI prepares briefing notes from session history, project status, and open items

**Score**: 0/100

**Demo Flow**:
1. User selects upcoming client meeting/session
2. System pulls session history, project status, and open items for that client
3. AI generates briefing notes with key discussion points, risks, and action items
4. Briefing rendered in-page with print/export option

**Current state**: No interactive workflows
**Gap to demo-ready**: Build action button, MCP tool for session prep, client data aggregation, briefing template

**Cross-hub leverage**: Pulls data from ai/knowledge for AI context, health for engagement health data

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Consulting** (http://localhost:3000/consulting) on 2026-02-21.
Composite score: **39/100**.

### Issues Identified

**UI Compliance** (50/100):
- No GlassCard usage in /consulting/client-ai-consulting/opportunities
- Missing proper layout structure in /consulting/client-ai-consulting/opportunities
- No loading states or error handling in /consulting/client-ai-consulting/opportunities

**Page Coverage** (65/100):
- 4/8 pages use mock/hardcoded data instead of real fetching
- STUB: 'Overview' is only 13 lines — likely placeholder
- MOCK DATA: 'Sessions' uses hardcoded arrays/objects, no real data fetching

**MCP Tool Wiring** (16/100):
- No explicit MCP tool references in actions/modals
- 6/11 pages have MCP tool calls

**Performance** (31/100):
- No code splitting for large page: /consulting/client-ai-consulting/opportunities
- No code splitting for large page: /consulting/client-ai-consulting
- Large page (406 lines): /consulting/client-ai-consulting/sessions

**User Value** (38/100):
- No data directory — hub produces no persisted data
- 9/14 API routes have real backend logic
- 6/11 pages fetch real data

**Workflows** (0/100):
- No actions defined — hub has no workflows

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

**MCP Tool Wiring** (current: 16/100):
- No explicit MCP tool references in actions/modals
- 6/11 pages have MCP tool calls

**Performance** (current: 31/100):
- No code splitting for large page: /consulting/client-ai-consulting/opportunities
- No code splitting for large page: /consulting/client-ai-consulting
- Large page (406 lines): /consulting/client-ai-consulting/sessions

**User Value** (current: 38/100):
- No data directory — hub produces no persisted data
- 9/14 API routes have real backend logic
- 6/11 pages fetch real data

**Workflows** (current: 0/100):
- No actions defined — hub has no workflows

**Action Buttons** (current: 0/100):
- No action buttons defined — hub has no interactivity

### Phase 2: Completeness

**UI Compliance** (current: 50/100):
- No GlassCard usage in /consulting/client-ai-consulting/opportunities
- Missing proper layout structure in /consulting/client-ai-consulting/opportunities
- No loading states or error handling in /consulting/client-ai-consulting/opportunities

**Page Coverage** (current: 65/100):
- 4/8 pages use mock/hardcoded data instead of real fetching
- STUB: 'Overview' is only 13 lines — likely placeholder
- MOCK DATA: 'Sessions' uses hardcoded arrays/objects, no real data fetching

## Consequences

### Positive

- Consulting hub upgraded with standardized hardening across 8 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Smart Session Prep

### Negative

- Requires implementation effort across 8 dimensions
- Some dimensions may require runtime testing (performance, cross-hub connectivity)

### Neutral

- Existing working features remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
No manual alternatives were evaluated.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `consulting` hub audit
- Audit timestamp: 2026-02-21T09:49:04.081348

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-133: Consulting Hardening**.

Read the full ADR: `docs/decisions/ADR-133-consulting-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-133-consulting-hardening", description="Implementing ADR-133: Consulting Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-133-consulting-hardening", name="{role}",
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

**Team name**: `adr-133-consulting-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (0/100): Best candidate: No wow effect identified | `plugins/consulting/skills/client-ai-consulting/dashboard.yaml`, `plugins/consulting/skills/client-ai-consulting/dashboard/` |
| 1.2 | devops | low | Fix MCP Tool Wiring (16/100): No explicit MCP tool references in actions/modals | `plugins/consulting/skills/client-ai-consulting/dashboard.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.3 | frontend | medium | Fix Performance (31/100): No code splitting for large page: /consulting/client-ai-c... | `plugins/consulting/skills/client-ai-consulting/dashboard/client-ai-consulting/opportunities/page.tsx`, `plugins/consulting/skills/client-ai-consulting/dashboard/client-ai-consulting/page.tsx`, `plugins/consulting/skills/client-ai-consulting/dashboard/client-ai-consulting/sessions/page.tsx` |
| 1.4 | architect | high | Fix User Value (38/100): No data directory — hub produces no persisted data | `plugins/consulting/skills/client-ai-consulting/dashboard.yaml` |
| 1.5 | developer | medium | Fix Workflows (0/100): No actions defined — hub has no workflows | `plugins/consulting/skills/client-ai-consulting/dashboard.yaml` | Chains: `generate_delight` |
| 1.6 | frontend | medium | Fix Action Buttons (0/100): No action buttons defined — hub has no interactivity | `plugins/consulting/skills/client-ai-consulting/dashboard.yaml` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.7 | frontend | medium | Fix UI Compliance (50/100): No GlassCard usage in /consulting/client-ai-consulting/op... | `plugins/consulting/skills/client-ai-consulting/dashboard/client-ai-consulting/opportunities/page.tsx`, `plugins/consulting/skills/client-ai-consulting/dashboard/client-ai-consulting/opportunities/page.tsx`, `plugins/consulting/skills/client-ai-consulting/dashboard/client-ai-consulting/opportunities/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.8 | developer | medium | Fix Page Coverage (65/100): 4/8 pages use mock/hardcoded data instead of real fetching | `plugins/consulting/skills/client-ai-consulting/dashboard/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/consulting in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90
- [ ] MCP Tool Wiring improved from 16/100 to >= 90
- [ ] Performance improved from 31/100 to >= 90
- [ ] User Value improved from 38/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] UI Compliance improved from 50/100 to >= 90
- [ ] Page Coverage improved from 65/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-133 status updated to Accepted

## User Notes

Focus on SMB client — deprioritize AI consulting and terminal automation skills in favor of SMB design client.
