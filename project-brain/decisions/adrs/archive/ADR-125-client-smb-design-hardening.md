---
status: Implemented
date: '2026-02-19'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- smb
- design
- office
- hardening
superseded_by: null
---

# ADR-125: SMB Design Office Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 42/100 | 12% | critical | No GlassCard usage in /client-smb-design/content-pipeline |
| 2 | Page Coverage | 100/100 | 10% | good | - |
| 3 | API Completeness | 50/100 | 12% | significant-gaps | 4/8 API routes are stubs with no real backend logic |
| 4 | MCP Tool Wiring | 20/100 | 10% | critical | No explicit MCP tool references in actions/modals |
| 5 | Performance | 30/100 | 10% | critical | Score capped at 60/100 — runtime telemetry needed for ful... |
| 6 | User Value | 30/100 | 15% | critical | 1 real data files found in client-smb-design/ data dir |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — hub has no workflows |
| 8 | Cross-Hub Connectivity | 0/100 | 5% | critical | No cross-hub navigation links — hub is isolated |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined — hub has no interactivity |
| 10 | Wow Effect | 40/100 | 10% | critical | Selected headline demo: End-to-end Post Lifecycle demo |

**Composite Score**: 30/100 (major-rebuild)

## Wow Effect: End-to-end Post Lifecycle demo

> Demonstrate post detail, status tracking, and publish flow via /posts/[slug] APIs with visible state transitions.

**Score**: 40/100

**Demo Flow**:
1. Open /client-smb-design/content-pipeline/post/{slug}
2. Fetch current post + pipeline status from /api/client-smb-design/content-pipeline/posts/[slug]
3. Run status transition via /status endpoint and render updated stage/timestamps
4. Trigger publish via /publish endpoint and show final published state with confirmation

**Current state**: No interactive workflows
**Gap to demo-ready**: Add at least one action with real backend, real data, and visible output

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **SMB Design Office** (http://localhost:3000/client-smb-design/content-pipeline) on 2026-02-19.
Composite score: **30/100**.

### Issues Identified

**UI Compliance** (42/100):
- No GlassCard usage in /client-smb-design/content-pipeline
- No loading states or error handling in /client-smb-design/content-pipeline
- No GlassCard usage in /client-smb-design

**API Completeness** (50/100):
- 4/8 API routes are stubs with no real backend logic
- STUB: /api/client-smb-design/content-pipeline/posts/[slug]/pipeline returns hardcoded/minimal response
- STUB: /api/client-smb-design/content-pipeline/posts/[slug]/publish returns hardcoded/minimal response

**MCP Tool Wiring** (20/100):
- No explicit MCP tool references in actions/modals
- MCP module registered with 10 tools

**Performance** (30/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (30/100):
- 1 real data files found in client-smb-design/ data dir
- 4/8 API routes have real backend logic
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity

**Wow Effect** (40/100):
- Selected headline demo: End-to-end Post Lifecycle demo
- Implement post detail + status/publish endpoints with real backend state transitions
- Expose an end-to-end visible demo flow in the content pipeline UI

## Decision

Implement hardening in three phases, ordered by severity and user impact.

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect** (current: 40/100):
- Selected headline demo: End-to-end Post Lifecycle demo
- Implement post detail + status/publish endpoints with real backend state transitions
- Expose an end-to-end visible demo flow in the content pipeline UI

**UI Compliance** (current: 42/100):
- No GlassCard usage in /client-smb-design/content-pipeline
- No loading states or error handling in /client-smb-design/content-pipeline
- No GlassCard usage in /client-smb-design

**MCP Tool Wiring** (current: 20/100):
- No explicit MCP tool references in actions/modals
- MCP module registered with 10 tools

**Performance** (current: 30/100):
- Score capped at 60/100 — runtime telemetry needed for full evaluation

**User Value** (current: 30/100):
- 1 real data files found in client-smb-design/ data dir
- 4/8 API routes have real backend logic
- No pages fetch real data — all use hardcoded/mock content

**Workflows** (current: 0/100):
- No actions defined — hub has no workflows

**Cross-Hub Connectivity** (current: 0/100):
- No cross-hub navigation links — hub is isolated
- No src/lib service imports — hub doesn't consume data from other hubs
- No cross-hub data flow — hub operates in a silo

**Action Buttons** (current: 0/100):
- No action buttons defined — hub has no interactivity

### Phase 2: Completeness

**API Completeness** (current: 50/100):
- 4/8 API routes are stubs with no real backend logic
- STUB: /api/client-smb-design/content-pipeline/posts/[slug]/pipeline returns hardcoded/minimal response
- STUB: /api/client-smb-design/content-pipeline/posts/[slug]/publish returns hardcoded/minimal response

## Consequences

### Positive

- SMB Design Office hub upgraded with standardized hardening across 9 dimensions
- Critical gaps addressed in Phase 1, enabling demo-ready wow effect
- Killer demo use case identified: End-to-end Post Lifecycle demo

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
- Audit report: `client-smb-design` hub audit
- Audit timestamp: 2026-02-19T21:39:47.856928

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065.

You are implementing **ADR-125: SMB Design Office Hardening**.

Read the full ADR: `docs/decisions/ADR-125-client-smb-design-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-125-client-smb-design-hardening", description="Implementing ADR-125: SMB Design Office Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-125-client-smb-design-hardening", name="{role}",
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

**Team name**: `adr-125-client-smb-design-hardening`

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Fix Wow Effect (40/100): Selected headline demo: End-to-end Post Lifecycle demo | `plugins/consulting/skills/client-smb-design/augur.yaml`, `plugins/consulting/skills/client-smb-design/augur/` |
| 1.2 | frontend | medium | Fix UI Compliance (42/100): No GlassCard usage in /client-smb-design/content-pipeline | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/page.tsx`, `plugins/consulting/skills/client-smb-design/augur/content-pipeline/page.tsx`, `plugins/consulting/skills/client-smb-design/augur//page.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.3 | devops | low | Fix MCP Tool Wiring (20/100): No explicit MCP tool references in actions/modals | `plugins/consulting/skills/client-smb-design/augur.yaml`, `config/dashboard/mcp_tools.yaml` |
| 1.4 | frontend | medium | Fix Performance (30/100): Score capped at 60/100 — runtime telemetry needed for ful... | `plugins/consulting/skills/client-smb-design/augur//page.tsx` |
| 1.5 | architect | high | Fix User Value (30/100): 1 real data files found in client-smb-design/ data dir | `plugins/consulting/skills/client-smb-design/augur.yaml` |
| 1.6 | developer | medium | Fix Workflows (0/100): No actions defined — hub has no workflows | `plugins/consulting/skills/client-smb-design/augur.yaml` | Chains: `generate_delight` |
| 1.7 | developer | medium | Fix Cross-Hub Connectivity (0/100): No cross-hub navigation links — hub is isolated | `plugins/consulting/skills/client-smb-design/augur/` |
| 1.8 | frontend | medium | Fix Action Buttons (0/100): No action buttons defined — hub has no interactivity | `plugins/consulting/skills/client-smb-design/augur.yaml` |

#### Phase 2: Completeness
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.9 | developer | medium | Fix API Completeness (50/100): 4/8 API routes are stubs with no real backend logic | `src/dashboard/app/api/client-smb-design/`, `src/dashboard/lib/services/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/client-smb-design in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml against mcp/__init__.py registered tools |
| V.4 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria

- [ ] Wow Effect improved from 40/100 to >= 90
- [ ] UI Compliance improved from 42/100 to >= 90
- [ ] MCP Tool Wiring improved from 20/100 to >= 90
- [ ] Performance improved from 30/100 to >= 90
- [ ] User Value improved from 30/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] API Completeness improved from 50/100 to >= 90
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: page renders in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-125 status updated to Accepted
