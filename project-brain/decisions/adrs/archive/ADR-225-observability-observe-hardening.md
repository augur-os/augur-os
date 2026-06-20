---
status: Implemented
date: '2026-03-04'
deciders:
- Project team
related:
- ADR-065 (dashboard hardening workflow automation)
- ADR-130 (distributed action manifests)
- ADR-163 (plugin decentralization)
hub: null
tags:
- observability
- hardening
superseded_by: null
---

# ADR-223: Observability Hardening

## Context

Hardening audit for `http://localhost:3000/observability/observe` started at **87/100** with user-requested focus on:

1. Page consolidation
2. Repatriation of non-observability concerns to owning plugins

This ADR captures the implementation and verification evidence for that scope.

## Decision

Implement all hardening phases, with consolidation and repatriation as the primary architectural constraint:

1. Keep observe workflows observability-owned.
2. Move shared/non-owned implementation concerns out of duplicated observe surfaces.
3. Preserve cross-hub integrations as links/contracts, not duplicated feature ownership.

## Implementation

### Phase 1: Critical Wiring + Wow Surface Preservation

- Added explicit distributed action manifests under `plugins/observability/skills/observe/augur/data/actions/` for:
  - `check-system-health`
  - `trigger-scan`
  - `analyze-health`
  - `export-diagnostics`
  - `refresh-sessions`
  - `filter-self-heal-events` (modal)
- Removed inline observe action definitions from `plugins/observability/skills/observe/augur.yaml` in favor of ADR-130 action files.
- Hardened observe API routes with explicit MCP bridge calls:
  - `plugins/observability/skills/observe/augur/api/daemon-status/route.ts`
  - `plugins/observability/skills/observe/augur/api/sessions/route.ts`

### Phase 2: Consolidation + Repatriation

- Consolidated duplicated observe subpage shells with shared component:
  - `plugins/observability/skills/observe/augur/dashboard/components/ObserveTabScreen.tsx`
- Updated observe subpages (`health/logs/mcp/agents/memory/sessions/self-heal`) to use the shared screen.
- Refactored `WorkflowSuiteCard` to consume daemon-owned actions through action discovery/API wiring rather than hardcoded duplication.
- Updated cross-hub links to canonical ownership paths:
  - observe links point to `/observability/observe/...`
  - memory hub link updated to `/ai?tab=memory`
- Added repatriation and ownership documentation:
  - `plugins/observability/skills/observe/augur/data/repatriation-map.yaml`
  - `plugins/observability/skills/observe/augur/data/observe-surface.yaml`
  - `plugins/observability/skills/observe/augur/data/cross-hub-contracts.yaml`

### Phase 3: Cleanup + Supporting Fixes

- Updated observe ops documentation links to canonical observe routes:
  - `plugins/observability/skills/observe/commands/ops-inspect.md`
- Added missing dashboard page required by plugin rebuild validation:
  - `plugins/consulting/skills/client-smb-design/augur/dashboard/assets/page.tsx`
- Fixed test regressions/blockers surfaced during verification:
  - `src/dashboard/app/api/actions/run/route.ts` (MCP bridge import assertion compatibility)
  - `plugins/ai/skills/ai_bridge/scripts/sync_agents/discovery.py` (`distribute_imported_agents` now loads adapter config from passed `project_root`)
- Removed noisy observe log-tab runtime console errors on fetch failure:
  - `src/dashboard/components/shared/LogsTab.tsx`

## Final Audit Result

Source report: `plugins/dev/skills/frontend/augur/data/hardening-reports/observability_observe_20260304_f73b_after4.yaml`

| Dimension | Before | After |
|---|---:|---:|
| Composite | 87 | **97** |
| UI Compliance | 100 | 100 |
| Page Coverage | 100 | 100 |
| API Completeness | 100 | 100 |
| MCP Tool Wiring | 48 | **100** |
| Performance | 100 | 93 |
| User Value | 78 | **94** |
| Workflows | 87 | **100** |
| Cross-Hub Connectivity | 95 | 95 |
| Action Buttons | 68 | **100** |
| Wow Effect | 100 | 90 |

Interpretation: **production-ready**.

## Verification Evidence

### Automated checks

- `pytest plugins/observability/skills/observe/tests/test_observe.py -q` passed.
- `pytest tests/ -q` passed: **791 passed, 22 skipped**.
- `cd src/dashboard && npm run build` passed (includes `build:scripts`, `rebuild-plugins`, Next.js production build).

### Browser validation

- Playwright validation run across:
  - `/observability/observe`
  - `/observability/observe/sessions`
  - `/observability/observe/mcp`
  - `/observability/observe/agents`
  - `/observability/observe/memory`
  - `/observability/observe/health`
  - `/observability/observe/logs`
  - `/observability/observe/self-heal`
- Routes rendered and returned successful responses in local runtime.
- App-level observe log-fetch console errors were removed.
- Residual console noise observed from Turbopack dev HMR chunk reload (development runtime artifact, not observe feature logic).

## Completion Criteria

- [x] Wow Effect maintained at >= 90 with verified runtime interaction surface
- [x] MCP Tool Wiring improved from 48 to >= 90
- [x] Action Buttons improved from 68 to >= 90
- [x] User Value improved from 78 to >= 90
- [x] Workflows improved from 87 to >= 90
- [x] Consolidation complete for observe subpage shells/workflow surfaces
- [x] Repatriation documented and reflected in ownership/cross-hub contracts
- [x] All hardening phases executed
- [x] Tests pass (`pytest tests/`)
- [x] Dashboard build passes (`npm run build`)
- [x] Browser validation completed for observe routes
- [x] MCP/action references resolve via distributed action manifests and bridge-backed APIs

## Consequences

### Positive

- Observe is now consolidated around shared tab-screen architecture.
- Action and MCP wiring is explicit, discoverable, and auditable.
- Repatriation boundaries are documented and enforced as contracts.
- Hardening score moved from good-foundation (87) to production-ready (97).

### Tradeoffs

- Build and plugin rebuild regenerate mounted dashboard copies, increasing change surface.
- Development-runtime HMR can still emit transient console noise unrelated to observe logic.

## References

- Hardening reports:
  - `plugins/dev/skills/frontend/augur/data/hardening-reports/observability_observe_20260304_f73b.yaml`
  - `plugins/dev/skills/frontend/augur/data/hardening-reports/observability_observe_20260304_f73b_after4.yaml`
- Observe skill sources:
  - `plugins/observability/skills/observe/augur.yaml`
  - `plugins/observability/skills/observe/augur/data/actions/`
  - `plugins/observability/skills/observe/augur/dashboard/`
