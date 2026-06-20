---
status: Implemented
date: '2025-01-01'
deciders:
- Core team
related: []
hub: null
tags:
- skill
- owned
- pattern
superseded_by: null
---

# ADR-003: Skill-Owned UI Pattern

## Context

The Augur dashboard needs to display UI for dozens of skills (careers, recipes, medical, finance, etc.). Two approaches were considered:

1. **Centralized UI**: All UI code lives in the dashboard, skills are pure backend
2. **Skill-Owned UI**: Each skill owns its UI components, dashboard is just a shell

Early centralized approach caused problems:
- Dashboard became bloated with skill-specific code
- Adding a new skill required modifying central dashboard code
- Skill developers needed to understand dashboard architecture
- UI and skill logic drifted apart over time
- Hard to port skills to other systems

## Decision

Adopt a **skill-owned UI pattern**:

### Directory Structure
```
plugins/{category}/{skill}/
├── SKILL.md              # Skill definition
├── scripts/              # Python backend logic
└── _dev/ui/              # Skill-owned UI components
    ├── pages/            # Next.js page components
    ├── components/       # Skill-specific components
    └── manifest.json     # UI registration metadata
```

### Dashboard as Shell
```
src/dashboard/
├── app/                  # Stable routes (import from skill UIs)
├── components/           # Shared UI components
└── lib/                  # Shared utilities
```

### Routing Strategy
- Stable routes in `src/dashboard/app/**`
- Routes import skill UI from `plugins/**/_dev/ui/**`
- Shared pages (cross-skill dashboards) live directly in dashboard

### UI Registration
Skills declare their UI presence in `manifest.json`:
```json
{
  "hub": "/careers",
  "tabs": ["overview", "jobs", "applications"],
  "actions": ["refresh", "analyze"]
}
```

## Consequences

### Positive

- **Cohesion**: Skill logic and UI live together, evolve together
- **Portability**: Skill can be exported with its UI intact
- **Scalability**: Adding skills doesn't bloat the dashboard
- **Ownership**: Skill maintainers own their full stack
- **Reusability**: Shared components in dashboard, custom components in skill

### Negative

- **Build complexity**: Dashboard must resolve imports from plugins/
- **Potential duplication**: Skills might reinvent src/lib patterns
- **Learning curve**: Contributors need to understand the indirection
- **Testing overhead**: UI tests may need both skill and dashboard context

### Neutral

- Dashboard provides src/lib components (DashboardWidget, UnifiedHubTabs)
- Skills must follow design standards for visual consistency
- `_dev/` prefix indicates development-time assets

## Alternatives Considered

### Alternative 1: Centralized UI in Dashboard

All UI code in `src/dashboard/`, skills are headless. Rejected because:
- Dashboard becomes monolithic
- Skill portability suffers
- UI/logic drift over time
- Single point of failure for UI changes

### Alternative 2: Micro-Frontends

Each skill as an independent frontend app, composed at runtime. Rejected because:
- Excessive complexity for personal tool
- Performance overhead of multiple bundles
- Coordination challenges for src/lib state
- Overkill for current scale

### Alternative 3: Configuration-Driven UI

Skills define UI via configuration, dashboard renders dynamically. Rejected because:
- Limited expressiveness for complex UIs
- Configuration becomes as complex as code
- Hard to support skill-specific interactions
- Poor developer experience for custom UIs

## References

- Architecture Overview - Skill-owned UI pattern
- Design Standards
- Dashboard README
