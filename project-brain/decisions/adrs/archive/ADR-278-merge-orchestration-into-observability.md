---
status: Deprecated
date: '2026-03-03'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- merge
- orchestration
- bundle
- into
- observability
superseded_by: ADR-403
---

# ADR-278: Merge Orchestration Bundle into Observability

## Context

The orchestration bundle contains 3 purely backend skills (executor, router, swarm) with no dashboard pages, is nav-hidden, and adds maintenance overhead as a standalone bundle. Observability already references orchestration (metrics service maps executor/router/swarm). Merging orchestration into observability reduces the bundle count from 18 to 17 and consolidates related backend infrastructure.

## Decision

Absorb the `plugins/orchestration/` bundle (executor, router, swarm) into `plugins/observability/`. Each moved skill gets `contributes_to: observability`. The executor loses its `hub.owner: true` and `hub.id: orchestration` block, becoming a headless backend contributor. After the move, `plugins/orchestration/` is deleted.

### Execution sequence

1. Move `plugins/orchestration/skills/{executor,router,swarm}` → `plugins/observability/skills/`
2. Update `contributes_to:` and remove hub block in moved augur.yaml files
3. Update ~15 hardcoded path references (bridge scripts, navigation, registry, MCP modules)
4. Delete `plugins/orchestration/`
5. Regenerate via `sync_agents.py --all` + `mount-plugins`
6. Verify with `tsc --noEmit` and MCP diagnostic

### What doesn't change

- Dashboard routes (`/observe/*`, `/daemon/*`)
- Slash commands (`/ops-inspect`, `/ops-kill`, `/ops-perf`, `/ops-daemon`, `/ops-loops`, `/test-heal`)
- MCP tools (all 12 observe tools remain registered)
- Executor data/scripts (3700 files move as-is, no internal changes)

## Consequences

### Positive
- Reduced bundle count (18 → 17) and maintenance overhead
- Logical grouping — observability already references orchestration metrics
- Zero UI impact since orchestration had no dashboard pages

### Negative
- ~15 hardcoded path references require manual updates
- Risk of broken MCP tool registration after path move (mitigated by diagnostic step)

### Neutral
- Historical ADR references remain archival, no updates needed
- RAG indexes are content-addressed, not path-dependent

## Alternatives Considered

**Approach B: New "ops" bundle** — Clean conceptual umbrella but 3x more file changes (route renames, bookmark breakage). Rejected for excessive churn.

**Approach C: Absorb observability into orchestration** — Orchestration is larger but has no dashboard; would require unhiding hub and remounting 9+ tabs. Rejected as higher risk.

## References

- [Design doc](../plans/2026-03-03-merge-orchestration-into-observability-design.md) — full design document
- [Implementation plan](../plans/2026-03-03-merge-orchestration-into-observability.md) — detailed implementation plan

## Impact Manifest

```yaml
impact:
  paths_moved:
    - from: plugins/orchestration/skills/executor/
      to: plugins/observability/skills/executor/
    - from: plugins/orchestration/skills/router/
      to: plugins/observability/skills/router/
    - from: plugins/orchestration/skills/swarm/
      to: plugins/observability/skills/swarm/
  paths_deleted:
    - plugins/orchestration/
  files_modified: ~15 hardcoded references
  regenerated:
    - config/dashboard/generated/assembled_hubs.json
    - src/dashboard/lib/plugin-runtime/assembled-hubs.json
    - src/dashboard/lib/tabs/generated-registry.ts
    - docs/generated/skill-registry.md
    - CLAUDE.md
    - .cursorrules
```
