---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related: [ADR-483]
hub: null
tags: [dashboard, architecture, migration]
superseded_by: null
---

# ADR-490: Framework Migration — Dual-Alias Architecture

## Context

After ADR-483 moved pages to `skills/dashboard/pages/`, all components, hooks, and lib files remained in `apps/dashboard/`. Domain-specific code (chat, agents, action-bar) was mixed with framework infrastructure (MCP client, plugin system, UI primitives). Additionally, `apps/dashboard/lib/plugins/` contained ~91 dead mount files from the old plugin system.

No architectural boundary existed between stable infrastructure and volatile feature code, making it hard to reason about dependencies and change impact.

## Decision

Establish a dual TypeScript path alias architecture partitioning the dashboard codebase by stability:

- `@/` → `apps/dashboard/*` (framework — stable, changes rarely)
- `@skill/` → `skills/dashboard/*` (features — volatile, changes with every skill)

**Dependency rule:** `@/` never imports `@skill/`. Enforced by convention.

**What moved to `@skill/`:** ~135 domain files — chat components (~27), agents (~14), action-bar (~6), attention/inbox/layout-config/files (~13), ~53 top-level domain widgets, ~21 domain hooks, lib/prompts.

**What stayed at `@/`:** Plugin rendering framework, UI primitives (shadcn/ui), block system, MCP client, server utilities, stores, and 9 framework hooks.

**Cleanup:** Deleted ~91 dead `lib/plugins/` mount files, 62 orphaned page components (~15,600 lines), consolidated daemon pages (removed duplicates/wrapper chains).

## Consequences

### Positive

- Clear stability boundary — framework and feature code are in separate directory trees
- Feature code can be modified without risk of breaking framework
- Import paths signal intent: `@/` = infrastructure, `@skill/` = domain
- 15,600 lines of dead code removed

### Negative

- Some framework components (GlobalShell, HubTabBar) must import from `@skill/` for domain features — temporary violation until those components are refactored
- Test imports needed updating for `@skill/` alias (jest config + test files)

## References

- Spec: `docs/superpowers/specs/2026-03-23-framework-migration-design.md`
- Plan: `docs/superpowers/plans/2026-03-23-framework-migration.md`
- Depends on: ADR-483 (UI Skill Architecture)
