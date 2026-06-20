---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- dev
- hardening
superseded_by: null
---

# ADR-155: Dev Hardening

## Audit Summary

| # | Dimension | Raw | Adj.* | Weight | Status | Key Finding |
|---|-----------|-----|-------|--------|--------|-------------|
| 1 | UI Compliance | 0 | 0 | 12% | critical | No page files found — hub is greenfield |
| 2 | Page Coverage | 0 | 0 | 10% | critical | Missing page.tsx for tab 'Overview' (/dev) |
| 3 | API Completeness | 20 | ~15 | 12% | critical | 12 action endpoints defined in augur.yaml but zero implemented; 20/100 overstates actual state |
| 4 | MCP Tool Wiring | 0 | 0 | 10% | critical | `mcp: tools: []` in all 5 skill augur.yaml files — no MCP integration |
| 5 | Performance | 0 | 0 | 10% | critical | No pages to evaluate |
| 6 | User Value | 0 | ~20 | 15% | critical | No dashboard surface, but 49 backend scripts and 12 defined actions exist |
| 7 | Workflows | 0 | ~15 | 8% | critical | 12 actions defined in augur.yaml across 5 skills, but no dashboard.yaml or action YAMLs wired |
| 8 | Cross-Hub Connectivity | 0 | 0 | 5% | critical | No pages to check — hub is isolated |
| 9 | Action Buttons | 0 | ~10 | 8% | critical | augur.yaml defines 12 action buttons across 5 skills — none rendered |
| 10 | Wow Effect | 0 | 0 | 10% | critical | No wow effect — scripts exist with no visual surface |

\* **Adjusted scores** account for backend assets the audit engine can't see. Raw scores reflect dashboard surface state; adjusted scores reflect actual hub capability (scripts, augur.yaml definitions). Unlike ADR-148 (AI hub, adjusted ~49), the dev hub has zero dashboard implementation, so adjustments are modest.

**Raw Composite**: 2/100 (major-rebuild) | **Adjusted Composite**: ~8/100 (major-rebuild)

## Wow Effect: Nightly Health Dashboard

> Hit "Run Health Check" on /dev Overview — repo health scanner runs live, composite health score with trend sparkline updates, dependency graph visualizes plugin relationships, CI status cards flip to pass/fail, and the nightly quality checks surface code smell trends. The dev hub monitors Augur itself.

**Score**: 0/100 (current) -> 95/100 (target)

**Demo Flow**:
1. User opens /dev Overview tab
2. Dashboard fetches latest nightly check results via MCP tool (`run-nightly-checks`)
3. Displays composite health score with trend sparkline (backed by `check_repo_health.py`)
4. Shows interactive dependency graph visualization (backed by `dependency_tracker.py`)
5. CI/CD status cards with pass/fail indicators (backed by `ci_failure_analyzer.py`)
6. One-click "Run Health Check" action button triggers live scan via IDE dispatch
7. Results update in real-time with toast notification and animated badge transitions

**Current state**: 4 key scripts exist (`augur_nightly_checks.py`, `check_repo_health.py`, `dependency_tracker.py`, `health_check.py`) but no dashboard surface, no MCP tools, no API routes

**Gap to demo-ready** (4 items):
1. **Dashboard skeleton**: Create dashboard.yaml + dashboard/page.tsx for devops skill with GlassCard layout, health score hero card, and tab navigation
2. **MCP tool wiring**: Register nightly-checks, repo-health, and dependency-graph as MCP tools; add `mcp_tool:` refs to action YAMLs
3. **API routes**: Create `/api/dev/health`, `/api/dev/nightly-checks`, `/api/dev/dependencies` routes calling MCP tools (MCP-first pattern)
4. **Live interaction**: Action button with `dispatch: fire` triggers scan; polling/toast shows results; trend sparkline requires persisted data directory

**Cross-hub leverage**: Pulls data from observability (daemon health feeds via `/api/observe/`), ai (agent status monitoring via `/api/ai-bridge/client-test`)

**Other candidates**:
- dependency-graph (0/100, fire action — could be secondary wow)
- pre-merge-gate (0/100, fire action — validator skill)
- self-hardening-audit (0/100, fire action — frontend skill audits other hubs from dev)

**Priority**: This is the first thing to implement in Phase 1.

## Context

Automated hardening audit of **Dev** (http://localhost:3000/dev) on 2026-02-25.
Composite score: **2/100**.

The dev hub is an **architectural skeleton**: 5 stable enabled skills, 49 backend scripts, 12 action endpoints defined in augur.yaml — but zero dashboard implementation. This is a greenfield build, not a polish pass.

### Hub Architecture

| Skill | Role | Scripts | Defined Actions | Dashboard State | Target Contribution |
|-------|------|---------|-----------------|-----------------|---------------------|
| **devops** | Hub owner | 20+ (`augur_nightly_checks.py`, `check_repo_health.py`, `dependency_tracker.py`, `health_check.py`, `ci_failure_analyzer.py`, `release.py`) | 3 (nightly-checks, dependency-graph, data-backup) | None | Overview tab: health dashboard, CI status, dependency graph |
| **validator** | Quality gate | 10+ (`augur_pre_merge.py`, `validate_plugin_compliance.py`, `security/` dir) | 3 (plugin-compliance, security-scan, pre-merge-gate) | None | Compliance tab: plugin validation, security scan results, pre-merge gate |
| **frontend** | Self-hardening | 5+ (`dashboard_hardening_audit.py`, `pattern_compliance_audit.py`, `batch_ui_audit.py`) | 2 (verify-mounts, verify-wiring) | None | Audit tab: run hardening audit against other hubs from dev hub |
| **developer** | Refactoring | 5+ (`augur_refactor.py`, `feature_machine.py`, `data_migration_safety.py`) | 1 (data-migration-safety) | None | Tools tab: migration safety checks, refactoring utilities |
| **advisor** | Analytics | `scripts/analytics/`, `scripts/design/` | 3 (skill-health, audit-chains, memory-audit) | None | Analytics tab: design guidance, skill health metrics |

### Issues Identified

**UI Compliance** (0/100):
- No page files found — entire dashboard surface is missing

**Page Coverage** (0/100):
- Missing page.tsx for tab 'Overview' (/dev)
- No sub-pages for any of the 5 skills

**API Completeness** (20/100):
- 12 action endpoints defined in augur.yaml but zero implemented as Next.js route handlers
- All endpoints use stale `/api/crew/` prefix (should be `/api/dev/`)

**MCP Tool Wiring** (0/100):
- All 5 skills have `mcp: tools: []` — no MCP tool registrations
- No `mcp_tool:` field in any action definitions
- Backend scripts exist but aren't wrapped as MCP tools

**Performance** (0/100):
- No pages to evaluate (greenfield)

**User Value** (0/100):
- No data directory — hub produces no persisted data
- No API routes — hub cannot process data autonomously
- No pages fetch real data — all use hardcoded/mock content
- 49 backend scripts represent latent value with no dashboard exposure

**Workflows** (0/100):
- 12 actions defined in augur.yaml but no action YAML files, no dashboard.yaml manifests, no workflow chains

**Cross-Hub Connectivity** (0/100):
- No pages to check — hub is isolated
- Natural cross-hub connections unbuilt: observability (daemon health), ai (agent status), admin (system config)

**Action Buttons** (0/100):
- augur.yaml files define 12 action buttons across 5 skills — none rendered because no dashboard exists

**Wow Effect** (0/100):
- Scripts for health checks, nightly scans, and dependency tracking exist but have no visual surface
- "Nightly Health Dashboard" is the clear wow candidate — dev hub monitoring Augur itself

## Decision

Implement hardening in three phases, ordered by severity and user impact. Phase 1 builds the core dashboard and wow effect. Phase 2 integrates all 5 sub-skills. Phase 3 polishes cross-hub connectivity and data persistence.

### Phase 1: Wow Effect & Core Infrastructure

**Wow Effect — Nightly Health Dashboard** (current: 0/100, target: 95/100):
- Create devops dashboard.yaml manifest with hub registration and action references
- Build Overview page with GlassCard health score hero, CI status cards, and trend sparkline
- Wire "Run Health Check" fire action to `health_check.py` via MCP tool
- Wire "Nightly Checks" fire action to `augur_nightly_checks.py` via MCP tool
- Add dependency graph visualization backed by `dependency_tracker.py`
- Polling/toast pattern for live scan results (10s refresh)

**UI Compliance** (current: 0/100):
- Create `dashboard/page.tsx` in devops skill as hub Overview with `glass-panel p-6` root layout
- Add loading skeletons, error boundaries, and GlassCard wrappers per design-standards.md
- Devops skill layout must be passthrough (`<>{children}</>`) since it owns the hub

**Page Coverage** (current: 0/100):
- Create page.tsx for Overview (/dev) in devops skill
- Create page.tsx for Compliance tab in validator skill
- Minimum 3 pages in Phase 1: Overview, Health Detail, Compliance

**API Completeness** (current: 20/100):
- Create `/api/dev/health`, `/api/dev/nightly-checks`, `/api/dev/dependencies` route handlers
- All routes must call MCP tools as backend (MCP-first pattern, no `runPythonScript`)
- Fix stale `/api/crew/` endpoint prefix to `/api/dev/` in all augur.yaml files

**MCP Tool Wiring** (current: 0/100):
- Register MCP tools in devops augur.yaml: `run-nightly-checks`, `check-repo-health`, `get-dependency-graph`
- Register MCP tools in validator augur.yaml: `validate-plugin-compliance`, `run-security-scan`, `run-pre-merge-gate`
- Add `mcp_tool:` field to all action definitions in augur.yaml files

**Workflows** (current: 0/100):
- Create action YAML files for all 12 defined actions across 5 skills
- Add workflow chains: health-check -> nightly-report, compliance-scan -> pre-merge-gate
- Register all actions in respective dashboard.yaml manifests

**Action Buttons** (current: 0/100):
- Wire action buttons to Overview page: Run Health Check, Nightly Checks, Plugin Dependencies
- Wire action buttons to Compliance page: Plugin Compliance, Security Scan, Pre-Merge Gate
- Consistent GlassCard action areas with dispatch mode badges

### Phase 2: Sub-Skill Integration

**Multi-Skill Dashboard Surface**:
- Each of the 5 skills contributes pages/tabs to the dev hub — not just devops
- Sub-skills with `nav_mode: hidden` contribute via sub-routes inside the hub owner (devops)

| Skill | Tab/Route | Key Pages | Actions to Wire |
|-------|-----------|-----------|-----------------|
| **devops** | Overview (default) | Health dashboard, CI status, dependency graph | nightly-checks, dependency-graph, data-backup |
| **validator** | /dev/compliance | Plugin validation results, security scan, pre-merge gate | plugin-compliance, security-scan, pre-merge-gate |
| **frontend** | /dev/audit | Hub hardening scores, mount verification, wiring checks | verify-mounts, verify-wiring |
| **developer** | /dev/tools | Migration safety check, refactoring utilities | data-migration-safety |
| **advisor** | /dev/analytics | Skill health metrics, chain audit, memory audit | skill-health, audit-chains, memory-audit |

**Dashboard.yaml Manifests**:
- Create dashboard.yaml for devops (hub owner — registers all tabs and actions)
- Create dashboard.yaml for validator, frontend, developer, advisor (sub-skill manifests)
- Ensure mount-plugins.ts discovers all 5 skills via their dashboard.yaml files

**Performance** (current: 0/100):
- All new pages must be < 200 lines with code splitting
- Extract heavy components (dependency graph viz, compliance table, health trend chart) into lazy-loaded client components
- Use dynamic imports for chart/visualization libraries

### Phase 3: Polish & Cross-Hub

**User Value** (current: 0/100):
- Create `augur/data/` directory in devops skill for persisted health reports and nightly check history
- Wire Overview aggregation from all sub-skill APIs (not hardcoded arrays)
- Store trend data for sparkline visualization

**Cross-Hub Connectivity** (current: 0/100):
- Wire observability cross-link: daemon health status on Overview (pull from `/api/observe/`)
- Wire AI hub cross-link: agent health summary on Overview (pull from `/api/ai-bridge/client-test`)
- Wire admin cross-link: system config references
- Add shared service imports for cross-hub data consumption

## Consequences

### Positive

- Dev hub upgraded from greenfield skeleton (2/100) to functional developer tool across 10 dimensions
- All 5 skills contribute to the dashboard — devops, validator, frontend, developer, advisor
- Killer demo: Nightly Health Dashboard — the dev hub monitors Augur itself
- 12 action endpoints wired to MCP tools and rendered with action buttons
- Self-hardening capability: dev hub can audit other hubs via frontend skill

### Negative

- Requires building entire dashboard surface from scratch (greenfield, not polish)
- 5 dashboard.yaml manifests + 5 dashboard/ directories + API routes = significant volume
- MCP tool registration for 6+ new tools requires Python wrapper code

### Neutral

- Existing backend scripts remain untouched — dashboard adds a visual surface
- Audit report stored for trend tracking
- Adjusted composite (~8) vs raw (2) gap is small because the hub genuinely lacks dashboard code

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065).
Manual review improved: adjusted scores, sub-skill integration plan, phase restructuring, and wow effect specificity.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- ADR-148: AI hub hardening (reference for adjusted scores, sub-skill integration, phase structure)
- Audit report: `plugins/dev/skills/frontend/augur/data/hardening-reports/dev_20260225.yaml`
- Audit timestamp: 2026-02-25T12:09:18.968559

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065. Manually revised.

You are implementing **ADR-155: Dev Hardening**.

Read the full ADR: `docs/decisions/ADR-155-dev-hardening.md`

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

1. **Create team**: `TeamCreate(team_name="adr-155-dev-hardening", description="Implementing ADR-155: Dev Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-155-dev-hardening", name="{role}",
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

**Team name**: `adr-155-dev-hardening`

#### Phase 1: Wow Effect & Core Infrastructure
**Strategy**: PARALLEL-then-PIPELINE

**Group A** (parallel — no file overlap):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Implement Wow Effect — Nightly Health Dashboard: Create devops dashboard.yaml manifest, build Overview page.tsx with GlassCard health score hero card + trend sparkline + CI status cards + dependency graph placeholder. Wire "Run Health Check" fire action to `health_check.py` via MCP tool. Add polling/toast for live results. | `plugins/dev/skills/devops/dashboard.yaml`, `plugins/dev/skills/devops/dashboard/page.tsx`, `plugins/dev/skills/devops/augur/actions/` |
| 1.2 | devops | medium | Register MCP tools + wire action YAMLs: Add `run-nightly-checks`, `check-repo-health`, `get-dependency-graph` to devops augur.yaml. Add `validate-plugin-compliance`, `run-security-scan`, `run-pre-merge-gate` to validator augur.yaml. Create action YAML files for all 12 defined actions across 5 skills. Add `mcp_tool:` field to each. Fix stale `/api/crew/` prefix to `/api/dev/` in all augur.yaml files. | `plugins/dev/skills/*/augur.yaml`, `plugins/dev/skills/*/augur/actions/` |
| 1.3 | developer | medium | Create API routes (MCP-first): `/api/dev/health` (calls `check-repo-health`), `/api/dev/nightly-checks` (calls `run-nightly-checks`), `/api/dev/dependencies` (calls `get-dependency-graph`), `/api/dev/compliance` (calls `validate-plugin-compliance`), `/api/dev/security` (calls `run-security-scan`). All routes call MCP tools, never Python scripts directly. | `src/dashboard/app/api/dev/` |

**Group B** (after Group A — depends on dashboard.yaml and page.tsx from Group A):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.4 | frontend | medium | Fix UI Compliance + Performance: Ensure all new pages use `glass-panel p-6` root, GlassCard wrappers, loading skeletons, error boundaries per design-standards.md. Code-split heavy components (dependency graph viz, health trend chart) into lazy-loaded client components. No page.tsx > 200 lines. Devops layout must be passthrough (`<>{children}</>`). | `plugins/dev/skills/devops/dashboard/`, `plugins/dev/skills/devops/dashboard/layout.tsx` | Chains: `ui_quality_audit`, `redesign_page` |
| 1.5 | frontend | medium | Wire action buttons to Overview: Run Health Check, Nightly Checks, Plugin Dependencies (from devops). Wire action buttons to Compliance page: Plugin Compliance, Security Scan, Pre-Merge Gate (from validator). Consistent GlassCard action areas with dispatch mode badges. Add workflow chains: health-check -> nightly-report, compliance-scan -> pre-merge-gate. | `plugins/dev/skills/devops/dashboard/page.tsx`, `plugins/dev/skills/validator/dashboard/` |

#### Phase 2: Sub-Skill Integration
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create validator dashboard: dashboard.yaml manifest + dashboard/compliance/page.tsx showing plugin validation results table, security scan summary, pre-merge gate status. Wire 3 action buttons. | `plugins/dev/skills/validator/dashboard.yaml`, `plugins/dev/skills/validator/dashboard/` |
| 2.2 | developer | medium | Create frontend skill dashboard: dashboard.yaml manifest + dashboard/audit/page.tsx showing hub hardening scores across all hubs, mount verification results, wiring check results. Wire verify-mounts + verify-wiring action buttons. | `plugins/dev/skills/frontend/dashboard.yaml`, `plugins/dev/skills/frontend/dashboard/` |
| 2.3 | developer | low | Create developer skill dashboard: dashboard.yaml manifest + dashboard/tools/page.tsx showing migration safety check form, refactoring utilities. Wire data-migration-safety action button. | `plugins/dev/skills/developer/dashboard.yaml`, `plugins/dev/skills/developer/dashboard/` |
| 2.4 | developer | low | Create advisor skill dashboard: dashboard.yaml manifest + dashboard/analytics/page.tsx showing skill health metrics, chain audit results, memory audit summary. Wire 3 action buttons (skill-health, audit-chains, memory-audit). | `plugins/dev/skills/advisor/dashboard.yaml`, `plugins/dev/skills/advisor/dashboard/` |

#### Phase 3: Polish & Cross-Hub
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Fix User Value: Create `augur/data/` directory in devops skill for persisted health reports and nightly check history. Wire Overview to aggregate stats from all sub-skill APIs (validator compliance count, frontend audit scores, developer migration status). Store trend data for sparkline. | `plugins/dev/skills/devops/augur/data/`, `plugins/dev/skills/devops/dashboard/page.tsx` |
| 3.2 | developer | medium | Fix Cross-Hub Connectivity: Wire observability cross-link (daemon health from `/api/observe/`), AI hub cross-link (agent health from `/api/ai-bridge/client-test`), admin cross-link (system config). Add shared service imports. Add cross-hub link cards on Overview. | `plugins/dev/skills/devops/dashboard/page.tsx`, `plugins/dev/skills/devops/dashboard/` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions (`pytest tests/src/`, `npm run build`) |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/dev in Chrome MCP, screenshot each tab (Overview, Compliance, Audit, Tools, Analytics), check console for runtime errors, verify GlassCard compliance |
| V.3 | devops | low | MCP validation: cross-check all mcp_tool refs in dashboard.yaml files against mcp/__init__.py registered tools. Verify all 12 action YAMLs have valid `mcp_tool:` refs |
| V.4 | architect | low | Verify ADR intent matches implementation: all 5 skills contribute tabs, wow effect is demo-ready, self-monitoring narrative holds |

### Completion Criteria

**Dimension targets** (all >= 90/100 on re-audit):
- [ ] Wow Effect: 0 -> 90+ (Nightly Health Dashboard demo-ready with live scan)
- [ ] UI Compliance: 0 -> 90+ (GlassCard, loading states, error boundaries on all pages)
- [ ] Page Coverage: 0 -> 90+ (5+ pages across 5 skills, all fetching real data)
- [ ] API Completeness: 20 -> 90+ (5+ API routes calling MCP tools, no stubs)
- [ ] MCP Tool Wiring: 0 -> 90+ (6+ MCP tools registered, all action YAMLs have `mcp_tool:` refs)
- [ ] Performance: 0 -> 90+ (no page.tsx > 200 lines, heavy components code-split)
- [ ] User Value: 0 -> 90+ (data directory, persisted health history, real data fetching)
- [ ] Workflows: 0 -> 90+ (12 action YAMLs, 2+ workflow chains wired)
- [ ] Cross-Hub Connectivity: 0 -> 90+ (3 cross-hub links: observability, ai, admin)
- [ ] Action Buttons: 0 -> 90+ (buttons on all tab pages with consistent GlassCard action areas)

**Sub-skill integration:**
- [ ] All 5 skills have dashboard.yaml manifests
- [ ] All 5 skills have dashboard/ directories with page.tsx files
- [ ] Devops owns hub (Overview), other 4 skills contribute sub-routes
- [ ] 12 action endpoints migrated from `/api/crew/` to `/api/dev/`
- [ ] Consistent action button + GlassCard patterns across all sub-skill pages

**Structural:**
- [ ] All phases executed (Phase 1 -> Phase 2 -> Phase 3 -> Verification)
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: all 5 tabs render in Chrome MCP with zero console errors
- [ ] MCP validation: all tool references in dashboard.yaml resolve to registered tools
- [ ] No orphaned files or broken references
- [ ] Every skill with `dashboard/` has a `dashboard.yaml` manifest (required for mount-plugins discovery)
- [ ] No structural integrity issues (`structural_issues` in audit report is empty)
- [ ] ADR-155 status updated to Accepted

## User Notes

Prioritize self-monitoring — the dev hub should focus on monitoring the health of Augur itself (system status, CI, quality metrics). This is an internal developer tool — optimize for productivity, not polish.

### Additional Context from Exploration

The dev hub has **5 skills** (advisor, developer, devops, frontend, validator) with **70+ backend scripts** already built. Key assets to surface in the dashboard:

| Skill | Key Scripts to Wire | Dashboard Value |
|-------|-------------------|-----------------|
| **devops** | `augur_nightly_checks.py`, `check_repo_health.py`, `dependency_tracker.py`, `health_check.py` | System health, CI status, dependency graph |
| **validator** | `augur_pre_merge.py`, `validate_plugin_compliance.py`, `security/` | Pre-merge gate, compliance dashboard, security audit |
| **frontend** | `dashboard_hardening_audit.py`, `pattern_compliance_audit.py`, `batch_ui_audit.py` | Self-hardening: audit other hubs from the dev hub |
| **developer** | `augur_refactor.py`, `feature_machine.py`, `data_migration_safety.py` | Refactoring tools, migration safety checks |
| **advisor** | `scripts/analytics/`, `scripts/design/` | Design guidance, analytics references |

All 5 skills should contribute tabs/subpages to the dev hub, not just devops.

### Stale Endpoint Prefix

All 5 augur.yaml files use `/api/crew/{skill}/` endpoints — this is a legacy prefix from before hub-based routing. Implementation must update all endpoints to `/api/dev/{action-id}` to match the hub-based API pattern used by other hardened hubs.
