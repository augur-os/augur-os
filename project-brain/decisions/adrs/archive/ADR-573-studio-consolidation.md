---
status: Cancelled
date: 2026-03-20
deciders:
- Gur Sannikov
related: []
hub: studio
tags:
- dashboard
- studio
- consolidation
- routes
superseded_by: null
---

# ADR-573: Studio Hub Consolidation

## Context

The Studio hub had grown to 18 routes, many of which were duplicates, thin stubs, or already-inlined sections of larger mega-pages. The existing pages (`advisor/page.tsx`, `frontend/page.tsx`, `mcp-app-factory/page.tsx`) were already consolidated mega-pages with section components, but lived under non-canonical routes alongside duplicate landing pages and empty `SkillAutoPage` shells.

Users could not find a clear path through Studio. Decorative "Cross-Hub Navigation" cards and static description-only `GlassCard` sections added visual noise without interactivity. Tab discovery surfaced 17+ entries instead of a focused set of working surfaces.

The work targets a 5-page Studio: workbench (advisor + dev tools + capability audit), design (frontend audit + page builder), factory (MCP app factory + plugins + compliance), terminal (terminal automation), and the existing page-builder canvas.

## Decision

Reduce the Studio hub from 18 routes to 5 focused pages by moving consolidated mega-pages to clean routes, deleting duplicates and stubs, removing decorative fluff, and inlining sub-routes as tab state.

### Route map

- `plugins/ui/pages/studio/workbench/page.tsx` — advisor mega-page (with `analytics/` sub-page preserved)
- `plugins/ui/pages/studio/design/page.tsx` — frontend mega-page (audit + page builder section)
- `plugins/ui/pages/studio/factory/page.tsx` — mcp-app-factory mega-page with inline tabs
- `plugins/ui/pages/studio/terminal/page.tsx` — terminal automation page
- `plugins/ui/pages/studio/page-builder/builder/page.tsx` — full-screen canvas editor (kept as-is)

### Deletions (13 routes)

`advisor/`, `advisor/analytics/`, `developer/`, `devops/overview/`, `devops/refactor/`, `frontend/`, `frontend/audit/`, `mcp-app-factory/{audit,create,import,migrate,templates}/`, `renderer/`, `validator/compliance/`, `terminal-automation-template/`.

### Page-level cleanup

- Strip "Cross-Hub Navigation" link cards and static `GlassCard` description-only sections.
- Convert factory sub-route Quick Actions to `onClick` tab switches; sub-page tabs render inline via tab state.
- Update Studio hub landing to redirect to `/studio/workbench`.
- Regenerate the tab registry so Studio shows 5 tabs instead of 17+.

## Consequences

### Positive
- Studio surfaces 5 focused, working pages instead of 18 noisy routes.
- Users land on actionable workbenches, not stubs.
- Tab registry shrinks; navigation discoverability improves.
- Decorative fluff is removed in favor of interactive sections.

### Negative
- Bookmarks and external links to old routes (`/studio/advisor`, `/studio/frontend`, etc.) break unless redirects are added.
- API route audits are required to ensure moved pages do not reference stale `/api/dev/`, `/api/consulting/`, or `/api/admin/` prefixes.

### Neutral
- Sub-routes are reachable as tab state inside parent pages instead of as independent URLs.
- The existing page-builder canvas keeps its dedicated route because of full-screen editing requirements.

## Alternatives Considered

### Alternative 1: Keep all 18 routes and improve in place
Rejected because the duplicates and stubs are structural, not cosmetic. Cleanup-in-place leaves the registry bloated and discovery confused.

### Alternative 2: Replace each old route with a redirect
Rejected as default; redirects can be added selectively for high-traffic routes if breakage is observed, but persistent compatibility shims would obscure the intended Studio shape.

## References
- Plan: docs/superpowers/plans/2026-03-20-studio-consolidation.md
