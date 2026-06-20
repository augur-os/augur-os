---
status: Implemented
date: '2026-02-10'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- observability
- hub
superseded_by: null
---

# ADR-062: Observability Hub

## Context

Observability data is scattered across multiple dashboard hubs and has no CLI entry point:

| Data | Current Location | Problem |
|------|-----------------|---------|
| Plugin health scores | `/daemon/metrics` | Buried in daemon hub |
| System logs | `/daemon/logs` | Mixed with jobs/notifications |
| MCP server status | `/api/mcp/summary` (no dedicated page) | API-only, no dashboard view |
| Agent crew status | `/platform?tab=agents` | Overloaded platform hub (8 tabs) |
| Memory stats | `/platform?tab=memory` | Also in overloaded platform |
| Code markers | `/operations/bugs` (redirects to `/platform?tab=debug`) | Deprecated route |

There is no way to quickly inspect any of these dimensions from the CLI. Users must know specific API routes or navigate to the right dashboard page.

## Decision

### 1. `/inspect <dimension>` Slash Command

A single CLI command with 10 inspectable dimensions, all backed by existing API routes and MCP tools:

| Dimension | Data Source |
|-----------|-----------|
| `teams` | `GET /api/agents/status` |
| `mcp` | `GET /api/mcp/summary` |
| `health` | `GET /api/metrics/system` |
| `memory` | MCP tool: `memory-stats` |
| `plugins` | `GET /api/settings/skills` |
| `markers` | `python3 .github/scripts/scan_code_markers.py --summary` |
| `chains` | `GET /api/agents/chains` |
| `logs` | `GET /api/mcp/logs` |
| `ide` | `GET /api/ide/status` |
| `expiry` | MCP tool: `get-expiry-status` |

No new API routes needed for the CLI command. Each dimension links to the corresponding dashboard page.

### 2. `/observe` Dashboard Hub

New plugin skill at `plugins/observability/skills/observe/` with 7 tabs:

| Tab | Reuses | API Route |
|-----|--------|-----------|
| Overview | New (summary cards) | `/api/metrics/system` + `/api/mcp/summary` |
| Health | `MetricsTab.tsx` from daemon | `/api/metrics/system` |
| Logs | `LogsTab.tsx` from daemon | `/api/mcp/logs` |
| MCP | New | `/api/mcp/summary` |
| Agents | `AgentsTab.tsx` from ai_bridge | `/api/agents/status` |
| Memory | `MemoryTab.tsx` from ai_bridge | MCP: `memory-stats` |
| Markers | New | `/api/markers/summary` (1 new thin route) |

Shared component extraction: `MetricsTab.tsx` and `LogsTab.tsx` move from `plugins/observability/skills/daemon/dashboard/` to `src/dashboard/components/src/lib/` so both daemon and observe can import them.

### 3. Route Consolidation

| Old Route | Redirects To |
|-----------|-------------|
| `/daemon/health` | `/observe?tab=health` |
| `/daemon/metrics` | `/observe?tab=health` |
| `/daemon/logs` | `/observe?tab=logs` |
| `/operations/bugs` | `/observe?tab=markers` |

The `/daemon` overview (jobs, notifications, scheduled tasks) stays as-is — those are operational, not observability.

## Consequences

### Positive

- Single CLI entry point for all observability data via `/inspect`
- One dashboard page for all monitoring instead of 3+ scattered hubs
- Zero new API infrastructure (except 1 thin markers route)
- Reuses existing components rather than building from scratch
- Markers tab (devOnly) surfaces TODO_ markers in the dashboard for the first time

### Negative

- Shared component extraction creates a coupling between daemon and observe plugins
- Old bookmarks to `/daemon/health` etc. require redirect hops

### Neutral

- `/daemon` hub shrinks to jobs + notifications only
- `/platform` hub loses agents/memory tabs (moved to observe)
- Total new files: ~13 created, ~7 edited

## Alternatives Considered

### Alternative 1: Extend `/daemon` Hub

Add MCP, Agents, Memory, Markers tabs to the existing daemon hub and rename it "Observability".

Rejected: Mixes operational concerns (jobs, notifications) with observability. The daemon skill owns background job execution, not system monitoring.

### Alternative 2: Extend `/platform` Hub

Add Health, Logs, Metrics, Markers tabs to the existing platform/ai_bridge hub.

Rejected: Platform already has 8 tabs (Overview, Agents, Tools, Memory, Terminal, Setup, Debug, Catalog). Adding 4 more would make it unwieldy. Platform is about AI infrastructure configuration, not system monitoring.

## References

- Plan file: `.claude/plans/lively-hugging-whale.md`
- Existing MCP summary route: `src/dashboard/app/api/mcp/summary/route.ts`
- Existing metrics route: `src/dashboard/app/api/metrics/system/route.ts`
- Daemon plugin: `plugins/observability/skills/daemon/`
- AI Bridge plugin: `plugins/ai/skills/ai_bridge/`
- Code markers scanner: `.github/scripts/scan_code_markers.py`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

**Team name**: `adr-062-observability-hub`

### Phase 1: Slash Command
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create `/inspect` workflow markdown | `plugins/ai/ai_bridge/agent-workflows/inspect.md` |
| 1.2 | developer | low | Run sync_agents.py to generate command | `.claude/commands/inspect.md` |

### Phase 2: Observe Plugin + Shared Components
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | low | Extract MetricsTab and LogsTab to src/lib components | `src/dashboard/components/src/lib/MetricsTab.tsx`, `src/dashboard/components/src/lib/LogsTab.tsx` |
| 2.2 | developer | low | Update daemon pages to import from src/lib | `plugins/observability/skills/daemon/dashboard/metrics/page.tsx`, `plugins/observability/skills/daemon/dashboard/logs/page.tsx` |
| 2.3 | frontend | medium | Create observe plugin skill (SKILL.md, dashboard.yaml, all 7 tab pages) | `plugins/observability/skills/observe/` |
| 2.4 | developer | low | Create markers API route | `src/dashboard/app/api/markers/summary/route.ts` |
| 2.5 | developer | low | Update page-skills.yaml with observe mappings | `src/dashboard/config/page-skills.yaml` |

### Phase 3: Redirects + Cleanup
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | low | Update daemon health/metrics/logs pages to redirect to /observe | `plugins/observability/skills/daemon/dashboard/health/page.tsx`, `plugins/observability/skills/daemon/dashboard.yaml` |
| 3.2 | developer | low | Update operations/bugs to redirect to /observe?tab=markers | `src/dashboard/app/operations/bugs/page.tsx` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `npm run build` and `npm run test` in src/dashboard/ |
| V.2 | validator | low | Run `npm run mount-plugins` and verify /observe pages mounted |
| V.3 | architect | low | Verify ADR intent matches implementation |

### Completion Criteria
- [ ] `/inspect` command synced and available in Claude Code
- [ ] `/observe` hub renders with all 7 tabs
- [ ] Shared components imported by both daemon and observe
- [ ] Old routes redirect correctly
- [ ] All tests pass
- [ ] ADR status updated to Accepted
