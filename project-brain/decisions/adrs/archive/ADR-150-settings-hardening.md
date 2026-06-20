---
status: Implemented
date: '2026-02-25'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
hub: null
tags:
- settings
- hub
- hardening
superseded_by: null
---

# ADR-150: Settings Hub Hardening

## Audit Summary

| # | Dimension | Score | Weight | Status | Key Finding |
|---|-----------|-------|--------|--------|-------------|
| 1 | UI Compliance | 15/100 | 12% | critical | No GlassCard in GeneralTab/SecurityTab/PermissionsTab (use SettingsCard); inconsistent component pattern |
| 2 | Page Coverage | 0/100 | 10% | critical | No tabs in generated registry (uses hardcoded coreTabRegistry) — score artificially 0; adjusted ~70 |
| 3 | API Completeness | 90/100 | 12% | good | 9/10 API routes functional; 1 stub (`/paths/cleanup`) |
| 4 | MCP Tool Wiring | 0/100 | 10% | critical | No actions, no MCP integration — entirely passive hub |
| 5 | Performance | 34/100 | 10% | critical | PluginsTab 1697 lines (monolith), apis 589 lines; 3 tabs stuck loading in browser |
| 6 | User Value | 26/100 | 15% | critical | 1/11 pages fetch real data successfully; hub is read-only |
| 7 | Workflows | 0/100 | 8% | critical | No actions defined — zero workflows |
| 8 | Cross-Hub Connectivity | 50/100 | 5% | significant-gaps | Links to /ai only; no service imports from other hubs |
| 9 | Action Buttons | 0/100 | 8% | critical | No action buttons defined |
| 10 | Wow Effect | 0/100 | 10% | critical | No interactive demo candidate exists |

**Composite Score**: 22/100 (major-rebuild) — **adjusted ~29/100** accounting for Page Coverage audit engine limitation

## Wow Effect: Security Audit Report

> Generate a comprehensive security posture report — scan permissions, guardrails, API keys, audit log analysis — exportable markdown with action items. One-click security health check that combines Security tab data with live permission/service status.

**Score**: 0/100

**Demo Flow**:
1. User clicks "Run Security Audit" action button on Security tab
2. System scans permissions status, guardrail config, API key inventory, recent audit logs
3. Report generated with risk score, findings, and recommended actions
4. Export as markdown or copy to clipboard

**Current state**: Security tab has static guardrail toggles and audit log table but no aggregated report generation
**Gap to demo-ready**: Need action YAML, MCP tool for permission/guardrail scanning, report template, export functionality

**Cross-hub leverage**: Pulls data from observe (`/api/observability/daemon/services` for service health, `/api/observability/daemon/self-heal` for self-heal status), ai (`/api/ai/providers` for provider health)

**Priority**: Implement after loading issues are fixed (Phase 0).

## User Notes

Fix loading issues first — priority should be fixing tabs that are stuck loading (Integrations, APIs, Permissions) before adding new features. Settings is a daily-use utility hub; every tab must work reliably.

## Context

Automated hardening audit of **settings** (http://localhost:3000/settings) on 2026-02-25.
Composite score: **22/100**.

**Architecture note**: Settings is a **core dashboard hub** at `src/dashboard/app/settings/`, not a plugin-mounted hub. It uses `coreTabRegistry.settings` from `src/dashboard/lib/tabs/registry.ts` for tab definitions. This means:
- Pages live in `src/dashboard/app/settings/` (not `plugins/`)
- API routes live in `src/dashboard/app/api/settings/`
- No `dashboard.yaml` manifest — tabs are hardcoded in the core registry

### Live Browser Findings (Chrome MCP)

| Tab | Status | Issue |
|-----|--------|-------|
| General | Partial | Console error: `Failed to fetch services: SyntaxError: Unexpected token '<'` — daemon API returning HTML instead of JSON |
| Plugins | Working | 42 plugins visible, search/filter functional, install/enable/disable working |
| Integrations | Broken | Infinite spinner — stuck loading indefinitely |
| Providers | Not verified | Likely loading issues similar to Integrations |
| Services | Not verified | Likely loading issues similar to Integrations |
| APIs | Broken | Stuck on "Scanning API routes..." indefinitely |
| Security | Working | API keys placeholder, budget limits, guardrails toggles, audit log table |
| Permissions | Broken | Stuck on "Checking permissions..." indefinitely |
| Notifications | Placeholder | Static "coming soon" text only |

### Issues Identified

**UI Compliance** (15/100):
- GlassCard used in: IntegrationsTab, ProvidersTab, APIs page, NotificationsTab
- GlassCard **missing** in: GeneralTab, SecurityTab, PermissionsTab (use custom SettingsCard instead)
- Inconsistent component usage: must standardize on GlassCard or SettingsCard
- No interactive elements in AI settings — static display only

**Page Coverage** (0/100):
- Tabs defined in hardcoded `coreTabRegistry`, not in generated registry
- Audit engine can't detect them — score artificially 0

**MCP Tool Wiring** (0/100):
- No actions and no MCP integration — hub is entirely passive
- No `dashboard.yaml` manifest for action definitions

**Performance** (34/100):
- `PluginsTab.tsx` is 1697 lines — monolith needing refactoring into sub-components
- `apis/page.tsx` is 589 lines — needs code splitting
- 3 tabs stuck loading in browser (Integrations, APIs, Permissions) — API calls timing out or failing
- No lazy loading for heavy tab content

**User Value** (26/100):
- Only General and Plugins tabs successfully load and show real data
- Security tab works but with placeholder sections
- 3 tabs completely broken (stuck loading)
- Notifications tab is a placeholder with zero functionality
- No actions defined — hub is entirely read-only

**Workflows** (0/100):
- No actions defined — hub has no workflows
- Settings changes don't trigger any automation

**Cross-Hub Connectivity** (50/100):
- Links to `/ai` hub only
- No service imports from other hubs
- Should connect to: observe (health status), ai (provider config), admin (system state)

**Action Buttons** (0/100):
- No action buttons defined — hub has no interactivity beyond form inputs

**Wow Effect** (0/100):
- No interactive demo candidate exists
- Target: Security Audit Report (see above)

## Decision

Implement hardening in four phases. **Phase 0 is mandatory first** — fix all broken tabs before adding new features.

### Phase 0: Fix Broken Tabs (MUST DO FIRST)

Fix the 3 tabs stuck loading and the General tab console error:
- **Integrations** (`src/dashboard/app/settings/ai/tabs/IntegrationsTab.tsx`): Debug why `/api/ide/integrations` or `/api/cli/configs` fails; add error handling and timeouts
- **APIs** (`src/dashboard/app/settings/apis/page.tsx`): Debug why `/api/debug/routes` fetch hangs; add error handling
- **Permissions** (`src/dashboard/app/settings/tabs/PermissionsTab.tsx`): Debug why `/api/permissions/status` fetch hangs; add error handling
- **General** (`src/dashboard/app/settings/tabs/GeneralTab.tsx`): Fix daemon services fetch returning HTML — fetches `/api/daemon/services` but route lives at `/api/observability/daemon/services`; either fix fetch URL or add proxy route

### Phase 1: Wow Effect & Critical Gaps

**Wow Effect — Security Audit Report**:
- Create action YAML for "Run Security Audit" button
- Build MCP tool `security_audit_report` that aggregates: permissions status, guardrail config, API key inventory, audit log summary, service health
- Build report template with risk score, findings table, recommended actions
- Add export to markdown/clipboard
- Wire into Security tab with progress indicator

**UI Compliance** (15 -> 90):
- Migrate all settings pages to GlassCard where appropriate
- Standardize on GlassCard vs SettingsCard — pick one pattern
- Add interactive elements and loading states to AI/Integrations/Notifications pages

**MCP Tool Wiring** (0 -> 90):
- Core hubs have no `dashboard.yaml` — define actions in `src/dashboard/lib/tabs/registry.ts` alongside the tab definitions (add an `actions` array per tab entry)
- Wire existing API functionality through MCP tools
- Add at least: `security_audit_report`, `plugin_health_check`, `system_diagnostics`

**Performance** (34 -> 90):
- Refactor `PluginsTab.tsx` (1697 lines) into sub-components: PluginGrid, PluginCard, DependencyResolver, SearchFilters
- Code-split `apis/page.tsx` with dynamic imports
- Add proper error boundaries and loading timeouts to all tabs
- Implement `React.lazy` for heavy tab content

**User Value** (26 -> 90):
- Ensure all 9 tabs load real data with proper error handling
- Add meaningful actions to Notifications tab (notification preferences, channel config)
- Make Security tab fully interactive (save budget changes, toggle guardrails with confirmation)
- Add API key management to replace "coming soon" placeholder

**Workflows** (0 -> 90):
- Define settings-related action flows: backup config, export settings, reset to defaults
- Wire security audit workflow with chained steps

**Action Buttons** (0 -> 90):
- Add action buttons to each tab where relevant:
  - General: "Refresh All", "Reset Paths"
  - Plugins: "Rebuild Dashboard" (already exists as dialog), "Export Plugin List"
  - Security: "Run Security Audit", "Export Audit Log"
  - Permissions: "Request All Permissions", "Check System Health"

### Phase 2: Completeness

**Cross-Hub Connectivity** (50 -> 90):
- Add links to observe hub (system health, self-heal status)
- Add links to ai hub (provider configuration, agent status)
- Import service data from other hubs where relevant (e.g., show plugin health from observe)
- Add "Related Settings" cross-references between settings sections and hub-specific settings

**Page Coverage** (0 -> 90):
- Register settings tabs in the generated registry (or document why core tabs are exempt)
- Ensure every tab route has a working page.tsx that loads without errors
- Fill in Notifications tab with real content

## Consequences

### Positive

- Settings hub upgraded from 22/100 to target 90+ across all dimensions
- All 9 tabs load and function reliably — critical for daily-use utility hub
- Security Audit Report provides a compelling wow-effect demo
- PluginsTab refactored from 1697-line monolith to maintainable sub-components

### Negative

- Significant implementation effort across 10 dimensions (8 critical)
- Phase 0 may uncover deeper API infrastructure issues
- MCP tool creation for settings is new pattern for core hubs

### Neutral

- Existing working features (Plugins tab, Security tab basics) remain untouched
- Audit report stored for trend tracking

## Alternatives Considered

This ADR was auto-generated by the dashboard hardening audit engine (ADR-065), enhanced with live Chrome MCP browser validation. User chose "Security Audit Report" as wow effect over System Health Dashboard, Plugin Dependency Visualizer, and AI Configuration Wizard.

## References

- ADR-065: Dashboard hardening workflow automation (parent)
- ADR-054: Cross-tool swarm offloading (offload protocol)
- Audit report: `plugins/dev/skills/frontend/augur/data/hardening-reports/settings_20260225.yaml`
- Audit timestamp: 2026-02-25T00:37:34.322094

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `generate_hardening_adr.py` from ADR-065, then manually corrected for core hub paths.

You are implementing **ADR-150: Settings Hub Hardening**.

Read the full ADR: `docs/decisions/ADR-150-settings-hardening.md`

### Key Context

Settings is a **core dashboard hub** (not plugin-mounted). All files are in `src/dashboard/app/settings/`, NOT in `plugins/`. There is no `dashboard.yaml` — tabs are defined in `src/dashboard/lib/tabs/registry.ts`.

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

1. **Create team**: `TeamCreate(team_name="adr-150-settings-hardening", description="Implementing ADR-150: Settings Hub Hardening")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-150-settings-hardening", name="{role}",
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

**Team name**: `adr-150-settings-hardening`

#### Phase 0: Fix Broken Tabs (BLOCKING — must complete before Phase 1)
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 0.1 | frontend | medium | Fix Integrations tab infinite spinner — debug API calls in IntegrationsTab.tsx, add error handling and timeouts | `src/dashboard/app/settings/ai/tabs/IntegrationsTab.tsx`, `src/dashboard/app/api/ide/integrations/route.ts`, `src/dashboard/app/api/cli/configs/route.ts` |
| 0.2 | frontend | medium | Fix APIs tab stuck on "Scanning API routes..." — debug /api/debug/routes fetch, add error handling | `src/dashboard/app/settings/apis/page.tsx`, `src/dashboard/app/api/debug/routes/route.ts` |
| 0.3 | frontend | medium | Fix Permissions tab stuck on "Checking permissions..." — debug /api/permissions/status fetch, add timeout | `src/dashboard/app/settings/tabs/PermissionsTab.tsx`, `src/dashboard/app/api/permissions/status/route.ts` |
| 0.4 | frontend | medium | Fix General tab console error — fetches `/api/daemon/services` but route is at `/api/observability/daemon/services`; fix URL or add proxy route | `src/dashboard/app/settings/tabs/GeneralTab.tsx`, `src/dashboard/app/api/observability/daemon/services/route.ts` |

#### Phase 1: Wow Effect & Critical Gaps
**Strategy**: Blocked by Phase 0. Group A = PARALLEL, Group B = PIPELINE after Group A.

**Group A** (PARALLEL — no file overlap):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | high | Build Security Audit Report wow effect — action YAML, MCP tool, report template, export | `src/dashboard/app/settings/tabs/SecurityTab.tsx`, `src/dashboard/app/api/settings/security-audit/route.ts` |
| 1.2 | frontend | medium | Fix UI Compliance (15/100) — migrate GeneralTab/PermissionsTab to GlassCard, standardize component pattern, add loading states | `src/dashboard/app/settings/tabs/GeneralTab.tsx`, `src/dashboard/app/settings/tabs/PermissionsTab.tsx`, `src/dashboard/app/settings/ai/tabs/*.tsx` |
| 1.3 | frontend | high | Fix Performance (34/100) — refactor PluginsTab.tsx (1697 lines) into sub-components, code-split apis page, add error boundaries | `src/dashboard/app/settings/tabs/PluginsTab.tsx`, `src/dashboard/app/settings/apis/page.tsx` |
| 1.4 | developer | medium | Fix MCP Tool Wiring (0/100) — add actions array to coreTabRegistry settings entry, wire MCP tools for security_audit, plugin_health, system_diagnostics | `src/dashboard/lib/tabs/registry.ts` |

**Group B** (SEQUENTIAL — blocked by Group A; run 1.5 then 1.6 due to shared SecurityTab.tsx):

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.5 | architect | high | Fix User Value (26/100) — make all tabs interactive with real data, replace placeholders, add API key management | `src/dashboard/app/settings/tabs/NotificationsTab.tsx`, `src/dashboard/app/settings/tabs/SecurityTab.tsx` |
| 1.6 | developer | medium | Fix Workflows & Action Buttons (0/100) — add action buttons to each tab, define settings workflows (runs after 1.5) | `src/dashboard/app/settings/tabs/GeneralTab.tsx`, `src/dashboard/app/settings/tabs/SecurityTab.tsx`, `src/dashboard/app/settings/tabs/PermissionsTab.tsx` |

#### Phase 2: Completeness
**Strategy**: PIPELINE (blocked by Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Fix Cross-Hub Connectivity (50/100) — add links to observe, ai hubs; import service data; add Related Settings | `src/dashboard/app/settings/tabs/GeneralTab.tsx`, `src/dashboard/app/settings/tabs/SecurityTab.tsx` |
| 2.2 | developer | low | Fix Page Coverage (0/100) — register settings tabs in generated registry or document exemption; fill Notifications tab | `src/dashboard/lib/tabs/registry.ts`, `src/dashboard/app/settings/tabs/NotificationsTab.tsx` |

#### Final Phase: Verification

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions: `pytest tests/src/`, `npm run build` |
| V.2 | frontend | low | Browser validation: open http://localhost:3000/settings in Chrome MCP, screenshot each tab, check console for runtime errors |
| V.3 | devops | low | MCP validation: cross-check all action definitions against registered MCP tools |
| V.4 | architect | low | Verify ADR intent matches implementation; re-run audit to confirm score improvement |

### Completion Criteria

- [ ] All 9 tabs load without errors or infinite spinners (Phase 0)
- [ ] Wow Effect: Security Audit Report generates a real report with export
- [ ] UI Compliance improved from 15/100 to >= 90
- [ ] Page Coverage improved from 0/100 to >= 90
- [ ] MCP Tool Wiring improved from 0/100 to >= 90
- [ ] Performance improved from 34/100 to >= 90 (PluginsTab refactored)
- [ ] User Value improved from 26/100 to >= 90
- [ ] Workflows improved from 0/100 to >= 90
- [ ] Action Buttons improved from 0/100 to >= 90
- [ ] Cross-Hub Connectivity improved from 50/100 to >= 90
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] Browser validation: all 9 tabs render in Chrome MCP with zero console errors
- [ ] No orphaned files or broken references
- [ ] ADR-150 status updated to Accepted
