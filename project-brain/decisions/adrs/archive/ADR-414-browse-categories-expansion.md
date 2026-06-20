---
status: Implemented
date: 2026-03-14
deciders:
  - Gur Sannikov
related:
  - ADR-163
  - ADR-266
  - ADR-270
  - ADR-404
hub: core
tags:
  - dashboard
  - browse
  - mcp
  - discovery
superseded_by: null
---

# ADR-414: Browse Categories Expansion

## Context

The browse page at `/browse` offered only 4 categories (Skills, Blocks, Pages, Documents), covering a fraction of the browsable entities in Augur. Users had no unified way to discover MCP tools, vault notes, actions, integrations, prompts, CLI commands, agents, ADRs, tests, API routes, or scripts. Each entity type had its own scattered discovery path or no discovery UI at all.

Additionally, the category and hub filter bars used hardcoded button strips that wrapped to multiple rows on narrow screens, degrading the layout.

## Decision

Expand the browse page from 4 to 15 categories with a responsive overflow bar, universal card design, and dev-mode gating.

### Categories

**Normal mode (11):** Skills (+ workflow sub-filter), Blocks, Pages, Documents, MCP Tools, Actions, Vault/Notes, Integrations, Prompts, CLI Commands, Agents

**Dev mode additions (4):** ADRs, Tests, API Routes, Scripts

### Architecture

- **OverflowBar** — Shared responsive component (ResizeObserver-based) replaces hardcoded button strips for both category and hub filter bars. Items render left-to-right; overflow collapses into "More" dropdown.
- **BrowseCard** — Universal card component with icon, title, description, hub badge, type badge, primary action button, and Reveal in Finder secondary action. All 15 categories use the same card layout.
- **BrowseItem normalization** — Each category's API response is normalized into `BrowseItem[]` by per-category transform functions, enabling uniform rendering, search, and hub filtering.
- **11 new MCP tools** — Discovery tools for each new category (`list-vault-items`, `list-prompts`, `list-scripts`, `list-cli-commands`, `list-integrations`, `list-agents`, `list-adrs`, `list-tests`, `list-api-routes`, `reveal-in-finder`, `open-file`).
- **MCP-first API routes** — 13 new `/api/browse/*` routes, each a thin wrapper around an MCP tool via `createAPIRoute()`.
- **Lazy loading** — Only the active category's data is fetched (via `enabled` gating on `useCachedFetch`).
- **Dev mode gating** — `useModeStore` controls visibility of dev-only categories. Falls back to "skills" when exiting dev mode from a dev-only category.
- **"System" pseudo-hub** — Hubless items (system MCP tools, global agents, cross-cutting ADRs) are assigned to the "system" hub for uniform hub filtering.

### Card Actions

Every card has a consistent layout:
- **Primary action** (left) — varies by category: Open Docs, Configure, Open Page, Open File, Test Tool, Run Action, Open Note, Copy Command, Open Config, Open ADR, Run Test, Test Route, Run Script
- **Secondary action** (right) — Reveal in Finder, universal across all categories
- **run-mcp** dispatch — Uses `useActionRunner` with `dispatch: "ide"` to send to connected IDE

## Consequences

### Positive

- Browse page is the complete inventory of every browsable entity in Augur
- Responsive overflow bar eliminates multi-row wrapping on narrow screens
- Uniform card design reduces cognitive load across 15 categories
- Lazy loading keeps initial page load fast regardless of category count
- Dev-mode gating keeps the default UI clean for non-developer usage

### Negative

- 11 new MCP tools add to the tool count (mitigated by `browse` category in mcp_tools.yaml)
- browse.py is a large file with 11 tool implementations (acceptable — all are simple filesystem scans)

### Neutral

- Existing 4 categories (Skills, Blocks, Pages, Documents) render identically to before but use the new universal card instead of custom inline rendering
- The skill detail page at `/browse/[skill]` and block detail at `/browse/blocks/[blockId]` are unchanged

## Alternatives Considered

### Alternative 1: Separate pages per category

Each category gets its own route (e.g., `/browse/mcp-tools`, `/browse/vault`). Rejected because it fragments discovery — users want to switch between categories quickly without full page navigation.

### Alternative 2: Fixed two-row button layout

Show all 15 categories as two rows of buttons. Rejected because it doesn't adapt to screen width and wastes vertical space on wide screens where all buttons fit in one row.

### Alternative 3: Sidebar filter panel

Replace the top bar with a left sidebar. Rejected as over-engineered for a simple category selector and inconsistent with the rest of the dashboard layout.

## References

- Design spec: `docs/superpowers/specs/2026-03-14-browse-categories-expansion-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-14-browse-categories-expansion.md`
- ADR-163: Plugin decentralization
- ADR-266: MCP-first API pattern
- ADR-270: External data paths (vault, documents, logs)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - /api/browse/* (13 new routes)
  patterns_deprecated: []
  files_affected:
    - apps/dashboard/app/(views)/browse/page.tsx
    - apps/dashboard/components/shared/OverflowBar.tsx
    - apps/dashboard/components/shared/BrowseCard.tsx
    - apps/dashboard/lib/browse/types.ts
    - apps/dashboard/lib/browse/transforms.ts
    - src/mcp/augur_mcp/infrastructure/browse.py
    - src/config/mcp_tools.yaml
```

## Implementation Prompt

> Already implemented. See commits on main from 2026-03-14.

**Team name**: `adr-414-browse-expansion`

### Phase 1: Shared Foundation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | implementer | low | Create types module | `apps/dashboard/lib/browse/types.ts` |
| 1.2 | implementer | medium | Create OverflowBar component + tests | `apps/dashboard/components/shared/OverflowBar.tsx` |
| 1.3 | implementer | medium | Create BrowseCard component + tests | `apps/dashboard/components/shared/BrowseCard.tsx` |

### Phase 2: MCP Tools
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | implementer | medium | File action tools (reveal, open) | `src/mcp/augur_mcp/infrastructure/browse.py` |
| 2.2 | implementer | low | Listing tools batch 1 (vault, prompts, scripts, CLI) | `src/mcp/augur_mcp/infrastructure/browse.py` |
| 2.3 | implementer | low | Listing tools batch 2 (integrations, agents, ADRs, tests, API routes) | `src/mcp/augur_mcp/infrastructure/browse.py` |

### Phase 3: Dashboard Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | implementer | low | API routes for all categories | `apps/dashboard/app/api/browse/*/route.ts` |
| 3.2 | implementer | medium | Transform functions | `apps/dashboard/lib/browse/transforms.ts` |
| 3.3 | implementer | high | Browse page rewrite | `apps/dashboard/app/(views)/browse/page.tsx` |
| 3.4 | implementer | low | Register tools in mcp_tools.yaml | `src/config/mcp_tools.yaml` |

### Completion Criteria
- [x] All phases executed
- [x] All tests pass (17 Python, 98 dashboard)
- [x] TypeScript compilation clean
- [x] ADR status updated to Implemented
