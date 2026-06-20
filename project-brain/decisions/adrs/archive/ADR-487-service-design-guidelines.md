---
status: Cancelled
date: 2026-03-23
deciders:
- Gur Sannikov
related:
- 260
- 483
- 163
hub: system
tags:
- dashboard
- services
- data-layer
- guidelines
- architecture
superseded_by: null
---

# ADR-487: Service Design Guidelines

## Context

The dashboard codebase has grown organically with inconsistent data access patterns — some pages fetch data inline in server components, others call Python scripts directly, others use API routes. There was no documented rule for when to create a service, where it lives, or how UI components should consume it. This creates drift and makes it hard to audit compliance with the MCP-first rule (CLAUDE.md rule 11).

This ADR captures the intended design pattern as a codified decision so new plugin contributors follow the same model.

## Decision

Services are the data layer between dashboard UI and data sources. They are always server-side, live in `apps/dashboard/lib/services/`, and are the only place where `fs`, `path`, `child_process`, and `unstable_cache` are used.

### Design rule: start with the UI, work backwards

For each dashboard feature, identify what data it needs to display, then determine the service:

| Data source | Service pattern |
|-------------|----------------|
| Files (YAML, markdown) | `fs.readFile` + parse in service function |
| External API | `fetch` wrapped in service function |
| System data (calendar, contacts) | Service calls Python/native via MCP tool |
| Computed/aggregated data | Service transforms raw data from other sources |
| Expensive data | Wrap with `unstable_cache` |

Each service file is named after the plugin (`{plugin-name}.ts`) and exports typed functions that return data for React to render.

### Consumption pattern

Services are consumed by:
- **Server Components** — direct import (zero latency, no API round-trip)
- **API Routes** — direct import (exposes to client components)
- **Client Components** — via `fetch` to an API route (never directly)

Client components never import service files. Service files never contain JSX or React hooks.

### MCP-first constraint

For data that requires calling Python tools or external integrations, the service function calls an MCP tool via the proxy (`/api/mcp/tool`), not via `runPythonScript`, `execFile`, `execSync`, or `spawn`. This keeps Python execution centralized in the MCP server and auditable via the wiring audit (ADR-485).

### New plugin checklist

1. Sketch pages/widgets first
2. List what data each needs
3. Group by data source — each group is one service file
4. Create `apps/dashboard/lib/services/{plugin-name}.ts`
5. Export typed functions returning data for React

## Consequences

### Positive
- Clear boundary: services own all data access, pages own rendering
- `unstable_cache` usage is localized — easy to audit caching behavior
- New contributors have a documented pattern to follow instead of inferring from existing code
- MCP-first constraint enforced in the only place where `exec`/`spawn` violations could appear

### Negative
- Existing pages that fetch data inline must be refactored to use a service — this is cleanup work, not new feature work
- Services that currently use `fs` for data that should go through MCP tools need to be migrated (violates rule 11 if they're calling Python scripts)

### Neutral
- This is a codification of an existing pattern, not a new architectural invention — some services already follow this model
- The guideline does not address caching strategy (TTL, invalidation) — that is left to the implementing PR

## Alternatives Considered

### All data access through API routes (no server-side services)
Rejected: forces unnecessary client-server round-trips for data that could be fetched at render time in server components. Also makes server-only operations (file reads) awkward to express.

### Inline data fetching in page components
Rejected: makes data access opaque and untestable. Services provide a named, typed, independently-testable unit.

### Centralized data layer with a single service file
Rejected: violates decentralization principle. One service per plugin means each plugin owns its data access, consistent with CLAUDE.md rule 2.

## References

- Source spec: `docs/guides/service-design.md`
- ADR-260: MCP proxy catch-all routes (the target for MCP tool calls from services)
- ADR-483: UI Skill Architecture (defines where service files live within `skills/dashboard/`)
- CLAUDE.md rule 11: MCP-first API
