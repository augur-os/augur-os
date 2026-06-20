---
status: Implemented
date: 2026-03-15
deciders:
  - Gur Sannikov
related:
  - ADR-406
  - ADR-407
  - ADR-274
hub: core
tags:
  - browse
  - dashboard
  - navigation
  - hub-elimination
  - page-builder
superseded_by: null
---

# ADR-422: Browse as Single Surface — Hub Elimination, Detail Panel, and Page-Builder Home

## Context

After dashboard content reduction work, the dashboard has three redundant surfaces showing the same data (blocks from augur.yaml) in different ways: hub overviews, auto-page routes, and browse. Additionally, the sidebar shows 16 hub links as primary navigation, but hubs are an organizational concept, not a user task.

## Decision

Consolidate to a single surface:

### Browse Layout

Two-panel layout:
- **Left panel**: existing browse directory (categories, hub filters, search, card grid)
- **Right panel**: `BrowseDetailPanel` — opens when a skill card is clicked, showing header, stats, action bar, blocks via BlockRenderer, vault notes, and documents

### Sidebar Restructure

Replace 16 hub links with 28 agentic app links + Browse. Each app links directly to `/app/{skill-id}`.

### Page-Builder Home Dashboard

When browse opens with no query params (`/browse`), it shows a user-customizable page-builder canvas. Users can pin blocks from any skill, rearrange layout, and save compositions.

### What Gets Deleted

- ~83 auto-page route directories
- 16 hub overview pages and layouts
- `SkillAutoPage.tsx` and auto-page section renderers
- Tab registry generation for hub tabs
- `assembled-hubs.json` generation

### What Stays

- 28 custom page routes (agentic apps), migrated to `/app/{skill-id}`
- All augur.yaml declarations, block system, page-builder, browse page

## Consequences

### Positive

- One surface instead of three — eliminates redundant navigation
- Users get a customizable home dashboard
- Sidebar shows direct access to tools, not intermediate hub navigation

### Negative

- Breaking change: old auto-page URLs return 404 (per CLAUDE.md rule 14)
- Route migration for 28 custom pages with sub-routes is non-trivial

### Neutral

- Hub metadata preserved for browse filtering, just not as navigation items

## Alternatives Considered

### Alternative 1: Keep Hub Overviews as Curated Dashboards

Maintain hub pages as manually curated views. Rejected because they duplicate browse capability and add maintenance burden.

## References

- Design doc: `docs/superpowers/specs/2026-03-15-browse-single-surface-design.md`
- ADR-406: Block System UI
- ADR-407: Custom Page Consolidation
