---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- orchestration
- hardening
superseded_by: null
---

# ADR-153: Orchestration Hardening

## Audit Summary

| # | Dimension | Score | Adjusted | Weight | Status | Key Finding |
|---|-----------|-------|----------|--------|--------|-------------|
| 1 | UI Compliance | 0/100 | — | 12% | critical | No page files found — zero .tsx files in plugin |
| 2 | Page Coverage | 0/100 | — | 10% | critical | Missing page.tsx for tab 'Overview' (/orchestration) |
| 3 | API Completeness | 20/100 | 0 | 12% | critical | No API routes exist; 20 is scanner floor for passive hub |
| 4 | MCP Tool Wiring | 0/100 | ~15 | 10% | critical | Scanner checks dashboard.yaml (missing); 5 tools ARE registered in `mcp/__init__.py` across 3 skills but `augur.yaml` declares `mcp.tools: []` |
| 5 | Performance | 0/100 | — | 10% | critical | No pages to evaluate |
| 6 | User Value | 0/100 | ~20 | 15% | critical | Scanner missed existing `augur/data/` with tasks.json (~150 tasks), sprint_config.yaml, batch_presets.yaml, backlog tree |
| 7 | Workflows | 0/100 | — | 8% | critical | No workflow YAMLs defined |
| 8 | Cross-Hub Connectivity | 0/100 | — | 5% | critical | No pages to check — hub is isolated |
| 9 | Action Buttons | 0/100 | ~5 | 8% | critical | Scanner missed `action-buttons/inbox.yaml` (2 actions: refresh-inbox, route-all-auto) — not wired to dashboard.yaml |
| 10 | Wow Effect | 0/100 | — | 10% | critical | No UI surface — chain_executor.py backend is complete but invisible |

**Composite Score**: 2/100 (major-rebuild)
**Adjusted Estimate**: ~8/100 — scanner under-detected MCP tools, data directory, and action buttons due to missing dashboard.yaml

### Sub-Skill Topology

Three skills contribute to the orchestration hub. All are enabled but have zero dashboard surface.

| Skill | Path | MCP Tools | augur.yaml Declares | Data Files | Scripts |
|-------|------|-----------|---------------------|------------|---------|
| executor | `plugins/orchestration/skills/executor/` | `get-executor-status`, `get-executor-monitoring-report` | `mcp.tools: []` | tasks.json, sprint_config.yaml, batch_presets.yaml, backlog/, inbox.yaml | 13 scripts (124KB chain_executor.py) |
| router | `plugins/orchestration/skills/router/` | `get-router-status`, `select-agent-tier` | `mcp.tools: []` | — | tier_selector.py |
| swarm | `plugins/orchestration/skills/swarm/` | `get-swarm-status`, `run-swarm` | `mcp.tools: []` | — | swarm_executor.py |

**Key gap**: All 3 skills have `mcp.tools: []` in augur.yaml despite registering tools in `mcp/__init__.py`. This must be fixed for tool discovery.

## Wow Effect: Chain Executor Live View

> Mission control for agent chains — execute a multi-step agent chain with real-time progress, showing which CLI agent (Claude, Cursor, Codex) runs each step, live status transitions, and failure recovery. Leverages chain_executor.py (124KB) and monitoring_report.py.

**Score**: 0/100

**Demo Flow**:
1. User opens Chains tab, sees list of existing chain definitions loaded from executor config
2. Selects a chain (e.g. "nightly-hardening") and clicks "Execute Chain" — dispatches via `chain_executor.py`
3. Live progress panel shows each step with: status badge (pending/running/success/failed), assigned CLI agent name and tier, elapsed duration counter
4. Agent routing decisions surface in real time — "Step 3 routed to Cursor (tier: fast) because task is GUI-only"
5. If a step fails, dashboard shows error summary and "Resume from step N" button (chain_executor.py supports resume)
6. On completion, summary card shows total duration, steps completed, per-agent breakdown, outputs

**Current state**: chain_executor.py exists with full execution logic (execute, resume, dry-run, parallel steps, error handling) but no dashboard surface. monitoring_report.py generates JSON stats. Both MCP tools (`get-executor-monitoring-report`, `get-executor-status`) are wired and functional.
**Gap to demo-ready**: Build chain execution UI with step progress cards, wire to MCP monitoring tools for polling, add agent identity badges per step

**Cross-hub leverage**: AI hub (agent registry for agent names/tiers, `select-agent-tier` routing), Observability (execution metrics, error tracking)

**Other candidates**:
- Swarm Dispatch (75/100): Multi-agent swarm launch with live agent count, task distribution, and completion fan-in visualization. Backend exists (`run-swarm` MCP tool, swarm_executor.py).
- Inbox Triage (60/100): AI-powered task inbox that auto-classifies, prioritizes, and routes incoming items. Backend exists (triage_inbox.py) but needs classification UI.
- Sprint Dashboard (55/100): 3-day sprint board with task cards, agent assignments, velocity tracking. Data exists (sprint_config.yaml, tasks.json) but needs kanban UI.

**Priority**: This is the first thing to implement in Phase 1. Aligns directly with User Notes "mission control center for agent activity."

## Context

Automated hardening audit of **Orchestration** (http://localhost:3000/orchestration) on 2026-02-25.
Composite score: **2/100**.

The orchestration hub has a complete backend (13 scripts, 6 MCP tools across 3 skills, rich data files, comprehensive tests) but zero dashboard surface. This is a pure "UI build on solid backend" hardening — no backend rework needed.

### Issues Identified

**UI Compliance** (0/100):
- No page files found — zero .tsx files in any orchestration skill

**Page Coverage** (0/100):
- Missing page.tsx for tab 'Overview' (/orchestration)
- No tabs defined in any dashboard.yaml (file does not exist)

**API Completeness** (20/100, adjusted ~0):
- No API routes exist under `/api/orchestration/`
- Scanner awarded 20 as floor for passive hub; real completeness is 0

**MCP Tool Wiring** (0/100, adjusted ~15):
- 5 tools registered in `mcp/__init__.py` across 3 skills (executor: 2, router: 2, swarm: 2)
- All 3 `augur.yaml` files declare `mcp.tools: []` — tool discovery broken
- No `dashboard.yaml` exists to reference tools for UI wiring

**Performance** (0/100):
- No pages to evaluate

**User Value** (0/100, adjusted ~20):
- Scanner reported "No data directory" — **incorrect**: `augur/data/` contains tasks.json (~150 tasks), sprint_config.yaml, batch_presets.yaml, backlog hierarchy, inbox.yaml
- No API routes — rich data exists but cannot be accessed from dashboard
- No pages fetch real data — all backend value is invisible

**Workflows** (0/100):
- No workflow YAMLs defined
- Existing scripts (chain_executor, triage_inbox, batch_offload) have no workflow wrappers

**Cross-Hub Connectivity** (0/100):
- No pages to check — hub is isolated
- Natural connections exist: AI (agent registry), Observability (metrics), Admin (config)

**Action Buttons** (0/100, adjusted ~5):
- `action-buttons/inbox.yaml` exists with 2 actions (refresh-inbox, route-all-auto) but not wired to dashboard.yaml
- No additional action buttons for chain execution, swarm dispatch, sprint planning

**Wow Effect** (0/100):
- Best candidate: Chain Executor Live View
- Description: Execute multi-step agent chains with real-time progress, agent identity, and failure recovery
- Gap to demo-ready: Build chain execution UI, wire to MCP monitoring tools, add agent tier badges and resume UX

## Decision

Implement hardening in two phases plus verification, ordered by severity and dependency.

### Phase 1: Foundation & Wow Effect (PIPELINE)

Build the critical path: dashboard manifest, skeleton pages, API routes, MCP wiring, and the headline Chain Executor Live View. These steps have serial dependencies.

### Phase 2: Completeness & Polish (PARALLEL)

Independent improvements: performance optimization, action buttons, cross-hub links, workflow definitions. These steps have no mutual dependencies and can execute concurrently.

## User Notes

Focus on CLI agent visibility — the hub should primarily surface what CLI agents (Claude, Cursor, etc.) are doing: task claims, execution progress, agent routing decisions. The orchestration dashboard should feel like a mission control center for agent activity.

## Consequences

### Positive

- Orchestration hub upgraded from 2/100 to target >=90/100 across all 10 dimensions
- CLI agent mission control vision realized — surfaces chain execution, agent routing, task progress
- Chain Executor Live View provides a differentiated demo: real-time multi-agent orchestration with failure recovery
- Rich existing backend (124KB chain_executor, 6 MCP tools, 150+ tasks) finally gets a UI surface

### Negative

- Requires implementation effort across 10 dimensions (~12 steps + verification)
- Chain dependency graph visualization adds frontend complexity (dynamic import recommended)

### Neutral

- All existing backend scripts, MCP tools, and tests remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065) and then manually refined to:
1. Correct under-detected audit scores (User Value, MCP Wiring, Action Buttons)
2. Split single PIPELINE into 2-phase PIPELINE+PARALLEL strategy
3. Strengthen wow effect demo flow with agent identity, failure recovery, and User Notes alignment
4. Add Sub-Skill Topology table covering all 3 skills (executor, router, swarm)

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- Audit report: `orchestration` hub audit
- Audit timestamp: 2026-02-25T12:07:21.171985
- Hardening report: `plugins/dev/skills/frontend/augur/data/hardening-reports/orchestration_20260225.yaml`
- Backend entry point: `plugins/orchestration/skills/executor/scripts/chain_executor.py` (124KB)
- Existing tests: `plugins/orchestration/skills/executor/tests/test_executor.py`, `test_chain_executor_regression.py`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065, manually refined.

You are implementing **ADR-153: Orchestration Hardening**.

Read the full ADR: `docs/decisions/ADR-153-orchestration-hardening.md`

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

### Hub Architecture

Three skills contribute to the orchestration hub — **executor** is primary (owns all dashboard pages), **router** and **swarm** contribute MCP tools only:

| Skill | Role | Dashboard Contribution |
|-------|------|----------------------|
| executor | Primary — chain execution, task management, monitoring | Owns all pages, API routes, dashboard.yaml |
| router | Agent tier routing | MCP tools only (`select-agent-tier`) — consumed by executor pages |
| swarm | Multi-agent swarm execution | MCP tools only (`run-swarm`, `get-swarm-status`) — consumed by executor pages |

All MCP tools from all 3 skills should be referenced in executor's `dashboard.yaml` so the UI can invoke them.

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-153-orchestration-hardening", description="Implementing ADR-153: Orchestration Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies. Phase 2 tasks are blocked by final Phase 1 task only.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-153-orchestration-hardening", name="{role}",
        model="{tier-model}", prompt="You are '{{role}}' on the {team_name} team.
        Read your profile: .claude/agents/{{role}}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: Phase 1 is PIPELINE (serial blocking). Phase 2 is PARALLEL (all tasks unblock simultaneously when Phase 1 completes). Verification blocks on Phase 2.
7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-153-orchestration-hardening`

#### Phase 1: Foundation & Wow Effect
**Strategy**: PIPELINE (each step depends on the previous)
**Dimensions addressed**: UI Compliance, Page Coverage, API Completeness, MCP Tool Wiring, Wow Effect, User Value

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | devops | low | Create `dashboard.yaml` manifest for executor skill — declare hub tabs (Overview, Chains, Tasks, Agents), register all 6 MCP tools from all 3 skills (`get-executor-status`, `get-executor-monitoring-report`, `select-agent-tier`, `get-router-status`, `get-swarm-status`, `run-swarm`). Fix `augur.yaml` in all 3 skills to declare their `mcp.tools` (currently `[]`). This is the mount-plugins discovery prerequisite. | `plugins/orchestration/skills/executor/dashboard.yaml`, `plugins/orchestration/skills/executor/augur.yaml`, `plugins/orchestration/skills/router/augur.yaml`, `plugins/orchestration/skills/swarm/augur.yaml` |
| 1.2 | frontend | medium | Create dashboard skeleton with GlassCard UI — hub layout with tab navigation (Overview, Chains, Tasks, Agents). Overview page shows agent activity feed placeholder, chain status summary, and routing decision log. Use existing hub layout patterns from ai/career hubs. | `plugins/orchestration/skills/executor/dashboard/` |
| 1.3 | developer | medium | Build all tab pages — Overview (agent mission control with activity feed), Chains (chain list from executor config + execution trigger), Tasks (sprint board from tasks.json), Agents (active agent roster with tier/status from router). Create page.tsx for each tab route. | `plugins/orchestration/skills/executor/dashboard/` |
| 1.4 | developer | medium | Create API routes — `/api/orchestration/chains` (list/execute chains via `get-executor-status`), `/api/orchestration/tasks` (read tasks.json), `/api/orchestration/agents` (agent tier info via `select-agent-tier`), `/api/orchestration/monitoring` (execution stats via `get-executor-monitoring-report`). All routes call MCP tools as backend — no direct Python script calls. | `plugins/orchestration/skills/executor/dashboard/api/` |
| 1.5 | architect | high | Build Chain Executor Live View wow effect — chain execution UI with real-time step progress cards, CLI agent identity badges (showing which agent runs each step and why), duration counters, status transitions (pending/running/success/failed). Wire to `get-executor-monitoring-report` and `get-executor-status` MCP tools for polling. Add "Resume from step N" button for failed chains. This is the headline demo and the CLI agent mission control centerpiece. | `plugins/orchestration/skills/executor/dashboard/` |
| 1.6 | architect | high | Build CLI agent visibility layer — real-time agent activity feed on Overview tab showing task claims, execution progress, routing decisions (which agent tier was selected and why via `select-agent-tier`). Surface data from tasks.json (~150 tasks), sprint_config.yaml, batch_presets.yaml. This addresses User Notes: "mission control center for agent activity." | `plugins/orchestration/skills/executor/dashboard/` |

#### Phase 2: Completeness & Polish
**Strategy**: PARALLEL (all steps independent, blocked only by Phase 1 completion)
**Dimensions addressed**: Performance, Workflows, Cross-Hub Connectivity, Action Buttons

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Add code splitting, Suspense boundaries, and skeleton loaders. Chain execution view uses dynamic imports for the progress visualization. Ensure all tab pages lazy-load. | `plugins/orchestration/skills/executor/dashboard/` |
| 2.2 | developer | medium | Create action button YAMLs — Execute Chain (`dispatch: 'ide'`), Dispatch Swarm (`dispatch: 'ide'`, modal confirmation), Triage Inbox (`dispatch: 'oneshot'`), Plan Sprint (`dispatch: 'ide'`), Refresh Monitoring (`dispatch: 'oneshot'`). Extend existing `inbox.yaml` (2 actions) and add new files. Wire all into dashboard.yaml `actions` section. Add workflow definitions. | `plugins/orchestration/skills/executor/augur/data/action-buttons/`, `plugins/orchestration/skills/executor/dashboard.yaml` |
| 2.3 | developer | medium | Add cross-hub links — link to AI hub (agent registry page), Observability hub (execution metrics), Admin hub (system config). Add breadcrumb navigation on all tab pages. | `plugins/orchestration/skills/executor/dashboard/` |
| 2.4 | frontend | medium | Build action button bar component — render all action buttons from YAML, wire dispatch to `useActionRunner` with appropriate dispatch mode. Include modal confirmations for destructive actions (swarm dispatch, chain execute). | `plugins/orchestration/skills/executor/dashboard/` |

#### Final Phase: Verification
**Strategy**: PIPELINE (blocked by all Phase 2 tasks)

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run existing tests (`pytest plugins/orchestration/skills/executor/tests/`), verify no regressions. Run `npm run build` to catch TypeScript/Next.js errors. |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/orchestration in Chrome MCP, screenshot each tab (Overview, Chains, Tasks, Agents), check console for runtime errors, verify GlassCard UI renders cleanly |
| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in dashboard.yaml against `mcp/__init__.py` registered tools across all 3 skills. Verify `augur.yaml` in executor, router, and swarm all declare their tools correctly. |
| V.4 | architect | low | Verify ADR intent matches implementation — check User Notes "mission control" vision is realized, chain executor live view works end-to-end, agent identity is visible per step |

### Completion Criteria

- [ ] Wow Effect improved from 0/100 to >= 90
- [ ] UI Compliance improved from 0/100 to >= 90
- [ ] Page Coverage improved from 0/100 to >= 90
- [ ] API Completeness improved from 20/100 to >= 90
- [ ] MCP Tool Wiring improved from 0/100 to >= 90
- [ ] Performance improved from 0/100 to >= 90
- [ ] User Value improved from 0/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 0/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] All 3 skill `augur.yaml` files declare their `mcp.tools` (not empty `[]`)
- [ ] All phases executed (Phase 1 PIPELINE, Phase 2 PARALLEL, Verification)
- [ ] Existing tests pass (`pytest plugins/orchestration/skills/executor/tests/`, `npm run build`)
- [ ] Browser validation: all 4 tabs render in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools across all 3 skills
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-153 status updated to Accepted
