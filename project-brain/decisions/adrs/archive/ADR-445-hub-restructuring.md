---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: []
tags: [dashboard, hubs, apps, navigation, ui]
---

# ADR-445: Hub Restructuring -- 15 Hubs to 5 Apps

## Context

Post plugin restructuring (ADR-430-434), the UI hubs still reflect the old 15-hub taxonomy. The dashboard needs realignment for investor demos that showcase Augur's breadth through cohesive, user-journey-based apps. 33 dashboard pages across 15 hubs create navigation confusion and dilute each hub's identity.

## Decision

Collapse 15 UI hubs into 5 visible apps optimized for demo impact, consolidating 33 pages into 13 tabs (2-3 per app). Adaptive auto-* skills (~56) become invisible infrastructure with no sidebar entry. 3 client-specific pages are hidden (direct URL access only).

The 5 apps:
- **Brain** (memory, library, agents) -- AI second brain
- **Career** (pipeline, venture) -- hiring, growth, brand
- **Life** (wealth, dashboard, home) -- AI life management
- **Studio** (workbench, design, factory) -- build, test, ship
- **Command** (monitor, system) -- self-managing infrastructure

Key mechanics:
- Skills update `x-augur-hub` frontmatter to new hub IDs + new `x-augur-tab` field
- Hub assembly generates consolidated tab pages composing sections from multiple skills
- Sidebar shows 5 apps with 2-3 tab sub-navigation each
- Sections within tabs use a 12-column CSS grid with `grid-span` declarations

## Consequences

### Positive

- 5 coherent apps tell a clear product story for demos
- Tab consolidation reduces cognitive load (13 tabs vs 33 scattered pages)
- Adaptive layer becomes invisible infrastructure, reducing noise

### Negative

- Consolidated tab pattern is net-new infrastructure (section-level mounting doesn't exist yet)
- Migration touches every skill's SKILL.md frontmatter (~130 skills)
- Cross-hub skill reassignments may have route/MCP implications

### Neutral

- Old hub directories are deleted after migration
- `adaptive` and `hidden` hub IDs exist but have no sidebar presence

## Alternatives Considered

### Alternative 1: Keep 15 Hubs, Improve Navigation

Add better grouping/search to existing 15-hub layout. Rejected because it doesn't solve the demo story problem or reduce cognitive load.

### Alternative 2: 3 Super-Apps

Consolidate into just 3 apps (personal, professional, system). Rejected as too aggressive -- Career and Studio serve distinct user journeys.

## References

- Design spec
