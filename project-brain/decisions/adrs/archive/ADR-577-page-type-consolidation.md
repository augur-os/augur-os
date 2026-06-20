---
status: Implemented
date: 2026-03-31
deciders:
  - Gur Sannikov
related:
  - ADR-491
  - ADR-274
  - ADR-163
hub: null
tags:
  - dashboard
  - pages
  - architecture
  - tabs
  - widgets
superseded_by: null
---

# ADR-577: Page Type Consolidation — 2 Types, 3 Access Tiers

## Context

The dashboard supported three page types — Custom TSX, Config YAML, and Auto-generated — with overlapping behavior and unclear boundaries. Config YAML and Auto-pages both rendered through `ConfigPage` with blocks (same technology, different inputs). YAML pages appeared as hub tabs alongside Custom TSX so users could not distinguish them. Auto-pages were only accessible via `/browse/[skill]`, inconsistent with other pages. There was no clear promotion path from "skill exists" to "skill has a good dashboard page", and storage was inconsistent (some custom pages in skill dirs, some in the dashboard plugin).

A separate `/view/[id]` widget canvas existed as a standalone user-composed dashboard, disconnected from hubs, with its own sidebar entry, its own storage, and its own editing UI.

## Decision

Consolidate into 2 page types and 3 access tiers, enforce storage rules, and embed the widget canvas inside hub overview pages.

### 2 types, 3 tiers

| Type | Renderer | Tier | Hub Tabs | Block Picker | Browse |
|------|----------|------|----------|--------------|--------|
| Custom TSX | React component | 1 | Yes | No | Yes |
| Config (explicit YAML) | `ConfigPage` block renderer | 2 | No | Yes | Yes |
| Config (implicit auto) | `ConfigPage` from `x-augur-mcp-tools` | 3 | No | No | Yes |

### Storage rules

- Custom TSX: only at `skills/dashboard/pages/{hub}/{skill}/page.tsx`.
- Config YAML: only at `skills/{skill}/augur/pages/*.yaml`.
- Auto-generated: no file — runtime from `SKILL.md` frontmatter.

Enforce via lint/pre-commit: no `page.tsx` in `skills/*/augur/dashboard/` (except `skills/dashboard/`); no YAML page configs in `skills/dashboard/augur/pages/`.

### Hub tabs become TSX-only

- Add a `pageSource: "tsx" | "yaml" | "auto"` field to `TabItem`.
- `generate-tab-registry.ts` infers `pageSource` from import path: `@skill/pages/` → `tsx`, `@/lib/configs/` → `yaml`, otherwise `auto`.
- Split the registry output into `tabs` (TSX only) and a new `configPages` array (YAML metadata for the block picker). `HubTabNav` reads `tabs` and naturally excludes YAML pages from the tab bar.

### Block picker shows YAML pages

The `CustomizePanel` gains a "Skill Pages" section listing YAML configs with their icon, title, and route. Clicking navigates to the page. YAML pages remain routable via direct URL because they stay in the hub `PAGES` map.

### Promotion ladder

Skills start at Tier 3 (auto-generated, browse-only). Authoring a YAML config promotes to Tier 2 (block picker). Building a custom TSX page promotes to Tier 1 (hub tab). Before removing a high-traffic YAML page from hub tabs, promote it to Custom TSX (priority targets: life/wealth, life/health, career/pipeline, life/eisenhower, life/attention, brain/obsidian/vault). Delete simple YAML configs whose smart auto-pages cover them (e.g., scraper, document-extractor, daemon/self-heal, auto-vault-hygiene).

### Widget canvas in hub overviews (Option C)

- Each hub overview gains a user-block section below the default content.
- Per-hub view storage: `views/hub-{hubId}-overview.yaml`. Helper `getHubViewId(hubId)` standardizes the key.
- Block picker "Add" buttons attach blocks to the current hub's overview view via `PUT /api/views/hub-{hubId}-overview`.
- Builder mode renders remove (X) buttons and drag handles on user blocks.
- Delete the standalone `/view/[id]` route, the "Widgets" sidebar entry, and the multi-views tab bar; `ViewCanvas`, `BlockCatalogPanel`, and `view-storage.ts` are reused inside hub overviews.

## Consequences

### Positive
- One page has exactly one source of truth — no duplicate rendering paths.
- Hub tabs become premium navigation real estate occupied only by Custom TSX investments.
- Widgets live where users work (hubs) instead of behind a separate sidebar entry.
- The promotion ladder gives a clear path from auto-page to YAML to TSX.

### Negative
- Removing 26 YAML pages from hub tabs risks breaking user workflows; mitigated by promoting high-traffic pages to TSX first.
- The block picker is less discoverable than hub tabs; mitigated by an existing visible grid icon and an optional count badge.
- Auto-generated page quality varies by skill; YAML override remains for the long tail.

### Neutral
- YAML pages keep `lib/configs/*.tsx` wrappers for URL routing, but those wrappers no longer generate tabs.
- Existing user blocks under `/view/{id}` may need a migration step to per-hub views.

## Alternatives Considered

### Alternative 1: Keep three page types with clearer documentation
Rejected. The overlap between Config YAML and Auto-generated is technological, not nominal; documentation does not change the fact that two paths render through the same code with different inputs.

### Alternative 2: Make hub tabs include YAML pages but mark them differently
Rejected. Tabs are premium navigation; mixing investment levels invites the same confusion the consolidation is trying to fix.

### Alternative 3: Keep `/view/[id]` standalone widget page
Rejected. It is disconnected from the hubs users actually work in, and per-hub views give the same composition power without a separate navigation surface.

## References
- Plan: docs/superpowers/plans/2026-03-31-page-type-consolidation.md
- Spec: docs/superpowers/specs/2026-03-31-page-type-consolidation-design.md
