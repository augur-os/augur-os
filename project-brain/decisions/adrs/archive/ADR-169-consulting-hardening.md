---
status: Implemented
date: '2026-02-27'
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

# ADR-169: Consulting Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 57/100 | 12% | significant-gaps | No GlassCard usage in /consulting/client-ai-consulting/op... |
| 2 | Page Coverage | 91/100 | 10% | good | 1/8 pages use mock/hardcoded data instead of real fetching |
| 3 | API Completeness | 100/100 | 12% | good | - |
| 4 | MCP Tool Wiring | 87/100 | 10% | needs-work | 7 actions have mcp_tool field (API-wrapped pattern) |
| 5 | Performance | 43/100 | 10% | critical | Large page (723 lines): /consulting/client-terminal-autom... |
| 6 | User Value | 89/100 | 15% | needs-work | 6 real data files found across 3/4 skills |
| 7 | Workflows | 70/100 | 8% | needs-work | 7/7 actions have working backends |
| 8 | Cross-Hub Connectivity | 60/100 | 5% | significant-gaps | Links to 2 other hubs: /ai, /health |
| 9 | Action Buttons | 100/100 | 8% | good | 7/7 actions are fully-wired |
| 10 | Wow Effect | 40/100 | 10% | critical | Best candidate: Consulting Assistant |

**Composite Score**: 74/100 (good-foundation)

## Wow Effect: Consulting Assistant

> AI assistant that helps plan sessions, analyze client progress, and suggest next actions for the consulting engagement

**Score**: 40/100

**Demo Flow**:
1. User clicks 'Consulting Assistant'
2. IDE chat opens with context
3. AI generates response
4. User reviews and applies

**Current state**: 8 candidate actions evaluated
**Gap to demo-ready**: Good static foundation — run /harden with dashboard running to verify live behavior

**Cross-hub leverage**: Pulls data from ai, health

**Other candidates**:
- Analyze Opportunities (40/100, llm_action)
- Prepare Briefing (40/100, fast_action)
- Session History (40/100, fast_action)
- Publish to Facebook (40/100, fast_action)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Consulting** (http://localhost:3000/consulting/client-smb-design/content-pipeline) on 2026-02-27.
Composite score: **74/100**.

### Issues Identified

**UI Compliance** (57/100):
- No GlassCard usage in /consulting/client-ai-consulting/opportunities
- No GlassCard usage in /consulting/client-ai-consulting
- No GlassCard usage in /consulting/client-ai-consulting/sessions

**Performance** (43/100):
- Large page (723 lines): /consulting/client-terminal-automation/automations
- No code splitting for large page: /consulting/client-terminal-automation/automations
- No code splitting for large page: /consulting/client-terminal-automation

**Cross-Hub Connectivity** (60/100):
- Links to 2 other hubs: /ai, /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 4 connections

**Wow Effect** (40/100):
- Best candidate: Consulting Assistant
- Description: AI assistant that helps plan sessions, analyze client progress, and suggest next actions for the consulting engagement
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 40/100):
- Best candidate: Consulting Assistant
- Description: AI assistant that helps plan sessions, analyze client progress, and suggest next actions for the consulting engagement
- Gap to demo-ready: Good static foundation — run /harden with dashboard running to verify live behavior

**Performance** (current: 43/100):
- Large page (723 lines): /consulting/client-terminal-automation/automations
- No code splitting for large page: /consulting/client-terminal-automation/automations
- No code splitting for large page: /consulting/client-terminal-automation

### Phase 2: Completeness

**UI Compliance** (current: 57/100):
- No GlassCard usage in /consulting/client-ai-consulting/opportunities
- No GlassCard usage in /consulting/client-ai-consulting
- No GlassCard usage in /consulting/client-ai-consulting/sessions

**Cross-Hub Connectivity** (current: 60/100):
- Links to 2 other hubs: /ai, /health
- No src/lib service imports — hub doesn't consume data from other hubs
- Cross-hub data flow detected: 4 connections

### Phase 3: Polish & Performance

**MCP Tool Wiring** (current: 87/100):
- 7 actions have mcp_tool field (API-wrapped pattern)
- 10/11 pages have MCP tool calls
- MCP module registered with 24 tools

**User Value** (current: 89/100):
- 6 real data files found across 3/4 skills
- 10/24 API routes have real backend logic
- 10/11 pages fetch real data

**Workflows** (current: 70/100):
- 7/7 actions have working backends
- No chain workflows found — no automated multi-step flows

## Consequences

### Positive

- Consulting hub upgraded with standardized hardening across 7 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: Consulting Assistant

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
- Audit report: `consulting` hub audit
- Audit timestamp: 2026-02-27T00:11:42.794927

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-169: Consulting Hardening**.

Read the full ADR: `docs/decisions/ADR-169-consulting-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-169-consulting-hardening", description="Implementing ADR-169: Consulting Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-169-consulting-hardening", name="{role}",
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

**Team name**: `adr-169-consulting-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (40/100): Best candidate: Consulting Assistant | `plugins/consulting/skills/client-hub/dashboard.yaml`, `plugins/consulting/skills/client-hub/dashboard/` |
| 1.2 | frontend | medium | Fix Performance (43/100): Large page (723 lines): /consulting/client-terminal-autom... | `plugins/consulting/skills/client-hub/dashboard/client-terminal-automation/automations/page.tsx`, `plugins/consulting/skills/client-hub/dashboard/client-terminal-automation/automations/page.tsx`, `plugins/consulting/skills/client-hub/dashboard/client-terminal-automation/page.tsx` |

#### Phase 2: Completeness
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.3 | frontend | medium | Fix UI Compliance (57/100): No GlassCard usage in /consulting/client-ai-consulting/op... | `plugins/consulting/skills/client-hub/dashboard/client-ai-consulting/opportunities/page.tsx`, `plugins/consulting/skills/client-hub/dashboard/client-ai-consulting/page.tsx`, `plugins/consulting/skills/client-hub/dashboard/client-ai-consulting/sessions/page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 2.4 | developer | medium | Fix Cross-Hub Connectivity (60/100): Links to 2 other hubs: /ai, /health | `plugins/consulting/skills/client-hub/dashboard/` |

#### Phase 3: Polish & Performance
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.5 | devops | low | Fix MCP Tool Wiring (87/100): 7 actions have mcp_tool field (API-wrapped pattern) | `plugins/consulting/skills/client-hub/dashboard.yaml`, `config/dashboard/mcp_tools.yaml` |
| 3.6 | architect | high | Fix User Value (89/100): 6 real data files found across 3/4 skills | `plugins/consulting/skills/client-hub/dashboard.yaml` |
| 3.7 | developer | medium | Fix Workflows (70/100): 7/7 actions have working backends | `plugins/consulting/skills/client-hub/dashboard.yaml` | Chains: `generate_delight` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/consulting in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [x] Wow Effect improved from 40/100 to >= 90
- [x] Performance improved from 43/100 to >= 90
- [x] UI Compliance improved from 57/100 to >= 90
- [x] Cross-Hub Connectivity improved from 60/100 to >= 90
- [x] MCP Tool Wiring improved from 87/100 to >= 90
- [x] User Value improved from 89/100 to >= 90
- [x] Workflows improved from 70/100 to >= 90
- [x] All phases executed
- [x] All tests pass (`pytest tests/src/`, `npm run build`)
- [x] Browser validation: page renders in Chrome MCP with zero console errors
- [x] MCP validation: all tool references in dashboard manifests/actions resolve to registered tools
- [x] No orphaned files or broken references
- [x] Every skill with `dashboard/` has a dashboard manifest (`augur.yaml` or `dashboard.yaml`) for mount-plugins discovery
- [x] No structural integrity issues (`structural_issues` in audit report is empty)
- [x] ADR-169 status updated to Accepted
