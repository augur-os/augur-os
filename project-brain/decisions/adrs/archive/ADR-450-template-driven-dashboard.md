---
status: Deprecated
date: 2026-03-19
deprecated: '2026-05-05'
deciders:
  - Gur Sannikov
related:
  - ADR-445
  - ADR-274
  - ADR-406
  - ADR-491
hub: null
tags:
  - dashboard
  - architecture
  - ui
  - templates
superseded_by: null
---

# ADR-450: Template-Driven Dashboard with UI Plugin Extraction

## Deprecation (2026-05-05)

**Dropped.** Phase 0 (`plugins/ui/` directory, manifest, `/api/dashboard/template/[hub]/[id]` route) was never built. The dashboard architecture moved in a different direction that solves the same problems without a central UI plugin:

- The `contributions.pages` field was renamed to `x-augur-dashboard-pages` and remains a first-class skill metadata key, consumed by `mount-plugins.ts`, the generated tab/hub/page-manifest registries, `src/plugins/skill_discovery.py`, and `src/lib/skill_scorer.py`.
- ADR-491 introduced YAML-configured pages under each skill's `augur/pages/*.yaml`, providing the YAML-template authoring path without centralizing it in a UI plugin.
- The block system (ADR-406) shipped end-to-end, providing the cross-hub composition layer through user-composed views at `/view/[id]` instead of templates merged from a UI plugin.
- TSX page code is organized under `apps/dashboard/features/pages/` with `[[...slug]]` catch-all routing per hub, so cross-plugin pages no longer require a "UI plugin" home.

The original problems (cross-plugin page ownership, user customization, sidebar sprawl) are addressed by the combination of ADR-406 + ADR-491 + the features-based dashboard layout. No replacement ADR is needed; this plan is dropped.

## Context

The current dashboard architecture couples UI pages to individual skills. Each skill declares `contributions.pages` in its SKILL.md, and mount-plugins copies TSX files into the Next.js app directory. This creates several problems:

1. **Cross-plugin pages have no natural home.** A "Library" page composing reading-list + books data can't belong to either skill. Whichever skill "owns" the page creates an artificial dependency.

2. **Users can't customize their dashboard.** Pages are code artifacts in the repo — users can't rearrange blocks, hide sections, or add new compositions without editing TSX.

3. **Implementation boundaries leak to users.** The sidebar reflects plugin structure, not user mental models. A "second brain" shouldn't make users think about which plugin provides what.

4. **Section-level mounting doesn't exist.** ADR-445 identified this as "net-new infrastructure" — the mount system copies full pages, with zero support for composing sections from multiple skills into one tab.

5. **Plugin growth creates UI sprawl.** As Augur adds plugins, each contributes its own tabs. Users get an ever-growing sidebar they didn't ask for.

## Decision

### Core Model Change

**Skills contribute only building blocks** (MCP tools, blocks, actions, data sources). **A dedicated UI plugin** owns all dashboard presentation — both YAML templates and custom TSX pages. Users pick templates from a catalog, activate them, and customize via vault-stored overrides.

### Architecture

```
plugins/ui/                          # All dashboard presentation
  templates/                         # YAML templates (composable dashboards)
    brain/
      library.yaml                   # reading-list + books blocks
      memory.yaml                    # knowledge + memory blocks
    career/
      pipeline.yaml                  # job search + interview blocks
    command/
      vault-monitor.yaml             # vault-hygiene blocks
  pages/                             # Custom TSX (rich interactive pages)
    page-builder/                    # depends on: [page-builder]
    skill-scores/                    # depends on: [auto-skill-quality]
    browse/                          # depends on: [] (core)
  manifest.yaml                      # declares all templates + pages + dependencies

~/Vault/Augur/dashboard/             # User-owned vault overrides
  templates/
    brain/
      library.overrides.yaml         # user customizations
    career/
      my-custom-dashboard.yaml       # user-created from scratch
  active.yaml                        # which templates are activated per hub
```

Skills become pure backend:
```
.claude/skills/reading-list/
  SKILL.md                           # blocks, actions, MCP tools only
  scripts/                           # MCP tool implementations
  data/                              # seed data
  # NO augur/dashboard/ directory
  # NO contributions.pages
```

### Template YAML Format

```yaml
# plugins/ui/templates/brain/library.yaml
name: Library
description: Reading queue, book notes, and saved articles in one view
hub: brain
icon: BookOpen
requires:
  - reading-list
  - books

layout: 2-column

blocks:
  - id: reading-queue
    source: reading-list
    block: reading-queue
    span: 6
    order: 1
    config:
      defaultView: list
      showCompleted: false

  - id: book-notes
    source: books
    block: book-notes-list
    span: 6
    order: 2

  - id: recent-highlights
    source: books
    block: highlights-feed
    span: 12
    order: 3
    config:
      limit: 10

actions:
  - id: add-book
    source: books
    action: add-book
  - id: add-to-reading-list
    source: reading-list
    action: quick-add
```

- `source` + `block` reference a skill's declared block by ID
- `config` overrides block's `configSchema` defaults
- `span` uses 12-column grid
- `requires` declares plugin dependencies

### Layered Overrides

Base templates in the UI plugin are read-only. User vault stores only deltas:

```yaml
# ~/Vault/Augur/dashboard/templates/brain/library.overrides.yaml
base: brain/library

blocks:
  reading-queue:
    order: 2                       # swapped
    config:
      showCompleted: true

  book-notes:
    order: 1                       # moved to top

  recent-highlights:
    removed: true                  # hidden

  my-rss-feed:                     # user-added
    source: scraper
    block: saved-articles
    span: 12
    order: 3

actions:
  add-to-reading-list:
    removed: true
```

Merge rules:
- Block in base, not in overrides: rendered from base (auto-upgrades)
- Block in base, customized in overrides: merged, override wins
- Block with `removed: true`: hidden, not deleted from base
- Block only in overrides: user-added, rendered as-is
- Base adds new block in update: appears automatically
- Base removes block user customized: orphaned, user notified

### Custom TSX Pages

Pages that genuinely need custom React (page-builder drag-and-drop, browse split-pane) live in `plugins/ui/pages/` with declared dependencies:

```yaml
# plugins/ui/manifest.yaml
pages:
  browse:
    type: custom
    requires: []
    route: /(views)/browse
  page-builder:
    type: custom
    requires: [page-builder]
    route: /studio/page-builder
```

Custom pages cannot use layered overrides — they're either shown or hidden in `active.yaml`. As the block system grows, custom pages can be "demoted" to YAML templates.

### Template Catalog UX

Hub landing pages become template catalogs. Active templates show as sidebar tabs. Available templates show with "+ add" buttons. "Create from scratch" opens page-builder with empty canvas.

Sidebar shows active templates from `active.yaml` alongside hub navigation from assembled-hubs.json. Full replacement of assembled-hubs.json is deferred until all pages are converted to YAML templates.

### Dependency Resolution

Two-tier resolution when user activates a template:
- **Internal Augur plugins**: auto-enabled silently (already in repo, just not active)
- **Community skills** (`source: skillstore`): prompt user to install via skillstore. If declined, blocks from that skill render a placeholder, everything else works.

### Render Pipeline

1. Hub page reads `active.yaml` from vault
2. For each active template, load YAML from UI plugin
3. Check for override file in vault, merge if exists
4. Resolve dependencies (enable plugins, render placeholders for missing)
5. `TemplateRenderer` component: parse layout, look up each block in BLOCK_REGISTRY, apply config, render via existing `BlockRenderer`
6. One API route `/api/dashboard/template/[hub]/[id]` handles merge + dependency check

Key reuse: `BlockRenderer` already renders all 16 block types with live MCP data. The template renderer is a thin orchestration layer.

### Migration Strategy

Phased — dashboard works at every step:

**Phase 0: Foundation** — Create `plugins/ui/`, template renderer, override merger, vault paths, `resolve-template` MCP tool

**Phase 1: First YAML templates** — Convert 3-5 simple pages to YAML. Ship alongside existing mounted pages. Both systems coexist.

**Phase 2: Move custom TSX** — Move complex pages from skill dirs to `plugins/ui/pages/`. Remove `contributions.pages` from migrated skills. Hub by hub.

**Phase 3: Template catalog + customization** — Hub landing pages become catalogs. Page-builder gains "edit template" mode. Override files written to vault.

**Phase 4: Dependency resolution + onboarding** — Onboarding shows template catalog. User picks templates, plugins auto-enabled. Skillstore integration for community deps.

## Consequences

### Positive

- Users customize their dashboard without touching code
- Cross-plugin pages are natural — templates compose from any skills
- New plugins add building blocks without touching UI
- Sidebar reflects user choices, not plugin structure
- Base templates auto-upgrade while preserving user customizations
- AI agents can compose and modify YAML templates trivially
- Clean separation: skills = capabilities, UI plugin = presentation

### Negative

- Large migration: ~50+ pages to move from skills to UI plugin
- Two rendering paths during migration (mounted pages + templates)
- Template YAML format is a new schema to learn and validate
- Custom TSX pages still exist as exceptions (can't eliminate entirely)
- Override merge logic adds complexity to the render pipeline

### Neutral

- Block system (16 types, BlockRenderer, BLOCK_REGISTRY) is unchanged — templates orchestrate existing blocks
- MCP tools, actions, and data sources in skills are unchanged
- Page-builder skill continues to exist but evolves into a template editor
- Browse page continues to show all skill building blocks

## Alternatives Considered

### Alternative 1: Section-Level Mounting (ADR-445 original spec)

Extend mount-plugins to support section-level composition — multiple skills contribute sections to a shared tab via CSS grid declarations. Rejected because:
- Still couples UI to skills (each skill "contributes" sections)
- No user customization path
- Doesn't solve the cross-plugin ownership problem — just makes it finer-grained

### Alternative 2: UI Plugin as Overlay

Keep existing skill pages working. Add UI plugin as a new layer that overrides/replaces skill pages with templates. Both systems coexist permanently. Rejected because:
- Two rendering systems forever
- Confusing "where does this page come from?" debugging
- No clean migration end state

### Alternative 3: Template-Only (no custom TSX)

UI plugin only has YAML templates. Custom TSX pages stay in skills. Block system made expressive enough that TSX becomes unnecessary. Rejected because:
- Some pages genuinely need custom React (drag-and-drop, split panes)
- Betting on block system sufficiency is risky for complex interactions
- Doesn't solve the cross-plugin page ownership problem for custom pages

## References

- ADR-445: Hub Restructuring (15 to 5 apps) — identified section-level mounting as "net-new infrastructure"
- ADR-274: Block system interactive capabilities (Tier 1/2/3)
- `apps/dashboard/lib/blocks/types.ts` — BlockManifest, 16 block types
- `apps/dashboard/lib/plugin-schema/types.ts` — ContributionBlock, PageDefinition
- `.claude/skills/page-builder/` — existing template types, block discovery, codegen pipeline
- `apps/dashboard/lib/browse/types.ts` — BrowseItem, 16 browse categories showing existing building blocks
- `src/mcp/augur_mcp/infrastructure/browse.py` — browse index with skill enrichment

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: ".claude/skills/*/augur/dashboard/"
      to: "plugins/ui/pages/ or plugins/ui/templates/"
  apis_changed:
    - "/api/dashboard/template/[hub]/[id] (new)"
    - "assembled-hubs.json replaced by active.yaml for sidebar"
  patterns_deprecated:
    - "contributions.pages in SKILL.md x-augur-config"
    - "mount-plugins copying TSX from skill dirs"
  files_affected:
    - "plugins/ui/**"
    - ".claude/skills/*/SKILL.md (remove contributions.pages)"
    - "apps/dashboard/lib/plugin-runtime/**"
    - "apps/dashboard/scripts/mount-plugins.ts"
    - "~/Vault/Augur/dashboard/**"
```

## Testing

| Test Case | Scope |
|-----------|-------|
| Template YAML parses and renders a 2-column grid with 3 blocks | Unit |
| Override file merges correctly: add, remove, reorder, config override | Unit |
| Orphaned override (base removed block) triggers user notification | Unit |
| Dependency resolution auto-enables internal plugin | Integration |
| Dependency resolution prompts for community skill | Integration |
| Missing skill renders placeholder, rest of template works | Integration |
| `active.yaml` drives sidebar tabs correctly | Integration |
| Page-builder can load and edit a YAML template | Integration |
| Custom TSX page renders from `plugins/ui/pages/` | Integration |
| Full migration: skill page removed, template replaces it, no regression | E2E |

## UI Validation Tests

Browser-based tests to run after each phase. Use Chrome MCP or Playwright.

### Phase 0 Validation
| Test | Steps | Expected |
|------|-------|----------|
| Template renders blocks | Navigate to a template page → inspect DOM | Grid layout with `grid-cols-12`, each block in correct `col-span-N` |
| BlockRenderer receives config | Open template page → check block props in React DevTools or console | Block config matches YAML `config:` values |
| API route returns merged template | `curl /api/dashboard/template/brain/library` | JSON with blocks array, layout, resolved dependencies |
| Vault override applied | Create override file, reload page | Overridden block shows new config/order |
| Missing vault graceful | Delete `active.yaml`, navigate to hub | Falls back to empty state or default templates |

### Phase 1 Validation
| Test | Steps | Expected |
|------|-------|----------|
| YAML template matches old page | Open template page and old mounted page side by side | Same blocks, same data, same layout |
| Hub shows both systems | Navigate to hub landing | Active templates + legacy mounted pages both visible as tabs |
| Template activation | Click "+ add" on available template | Template appears in sidebar, page renders |
| Template deactivation | Remove template from active.yaml, reload | Tab disappears from sidebar |

### Phase 2 Validation
| Test | Steps | Expected |
|------|-------|----------|
| Custom TSX from UI plugin | Navigate to browse, page-builder, skill-scores | Pages render correctly from new location |
| No broken imports | `npm run build` after migration | Zero TypeScript errors |
| Old skill pages removed | Navigate to old route (e.g., `/adaptive/auto-skill-quality/skill-scores`) | Redirects or 404, not stale page |
| Sidebar consistency | Check all hub sidebars | No duplicate tabs, no orphan entries |

### Phase 3 Validation
| Test | Steps | Expected |
|------|-------|----------|
| Template catalog renders | Navigate to hub landing page | Active templates as tabs, available templates as cards with "+ add" |
| Page-builder edits template | Open page-builder → load template → move block → save | Override file written to vault, page reflects change |
| "Reset to default" works | Delete override file, reload | Template reverts to base layout |
| "Create from scratch" works | Click create → add blocks → save | New YAML in vault, appears in sidebar |

### Phase 4 Validation
| Test | Steps | Expected |
|------|-------|----------|
| Auto-enable internal plugin | Activate template requiring disabled plugin | Plugin enabled, blocks render with data |
| Community skill prompt | Activate template with `source: skillstore` dep | Modal prompts to install, decline shows placeholder |
| Placeholder rendering | Decline community skill install | Placeholder block with "Install X to see this" message, rest of template works |
| Onboarding template picker | Run `/onboard --full` | Template catalog shown, selections drive active.yaml |

## Cost Estimate

Based on ADR-430 benchmarks (~0.5M tokens/agent at Opus, ~$25/agent full price, ~$12.50 off-peak).

| Phase | Agents | Est. Tokens | Est. Cost (full) | Est. Cost (off-peak 50%) |
|-------|--------|-------------|-------------------|--------------------------|
| Phase 0: Foundation | 5 | ~3M | $75 | $37 |
| Phase 1: First Templates | 3 | ~2M | $50 | $25 |
| Phase 2: TSX Migration | 6 (hub-by-hub) | ~5M | $150 | $75 |
| Phase 3: Catalog + Customization | 4 | ~4M | $125 | $62 |
| Phase 4: Dependencies + Onboarding | 3 | ~2M | $75 | $37 |
| Verification + fixes | 3 | ~2M | $75 | $37 |
| **Total** | **24** | **~18M** | **$550** | **$275** |

**Notes:**
- Off-peak window: 20:00-08:00 IST (per ADR-430 precedent)
- Phase 2 is heaviest — moving ~50 pages across 5 hubs, each hub is a separate agent
- Verification agents run UI tests after each phase
- Budget buffer: add 30% for retries/rework → **~$360 off-peak realistic**
- Can be split across multiple sessions: Phase 0-1 in session 1, Phase 2 in session 2, Phase 3-4 in session 3

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-450-template-dashboard`

### Agent Context (shared by all agents)

Every agent in this team MUST read before starting:
- This ADR (ADR-450) — the full Decision section
- `apps/dashboard/lib/blocks/types.ts` — BlockManifest shape, 16 block types
- `apps/dashboard/lib/plugin-schema/types.ts` — ContributionBlock, PageDefinition
- `apps/dashboard/components/shared/BlockRenderer.tsx` — existing block rendering (reuse, don't recreate)
- `CLAUDE.md` rules 1-5, 10-11, 14 — user experience, decentralization, MCP-first, no backward compat

**Constraints for all agents:**
- YAML templates use `write_frontmatter()` from `src.lib.frontmatter_utils` for any markdown-with-frontmatter files
- API routes follow MCP-first pattern: route calls MCP tool, never Python scripts directly
- All paths resolved via `src.config.paths` (`get_project_root()`, `get_vault_dir()`)
- No centralized registries — template discovery scans `plugins/ui/templates/` at runtime
- `npm run build` must pass after every step (not just at the end)
- Each agent runs Phase N UI Validation tests from the UI Validation Tests section before marking step complete

### Phase 0: Foundation
**Strategy**: PIPELINE
**Session**: 1 of 3
**Gate**: `npm run build` passes, `/api/dashboard/template/brain/test` returns valid JSON

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 0.1 | architect | high | Create `plugins/ui/` directory structure. Define TypeScript types: `TemplateYAML`, `TemplateOverride`, `ResolvedTemplate`, `ManifestEntry`. Create `manifest.yaml` with schema comments. Create one example template `plugins/ui/templates/brain/test.yaml` referencing real blocks from reading-list skill. | `plugins/ui/`, `plugins/ui/manifest.yaml`, `plugins/ui/templates/brain/test.yaml`, `apps/dashboard/lib/templates/types.ts` |
| 0.2 | backend | medium | Create `resolve-template` MCP tool in Python. Reads base YAML from `plugins/ui/templates/`, reads override from vault `~/Vault/Augur/dashboard/templates/`, merges per the Layered Overrides rules, checks `requires` against enabled skills, returns `ResolvedTemplate` JSON. Use `get_project_root()` and `get_vault_dir()` for paths. Register tool in `infrastructure/__init__.py`. | `src/mcp/augur_mcp/tools/internal/template_resolver.py`, `src/mcp/augur_mcp/infrastructure/__init__.py` |
| 0.3 | frontend | medium | Create `TemplateRenderer` React component. Takes `ResolvedTemplate` as prop. Renders 12-column CSS grid (`grid-cols-12`). For each block: look up `BlockManifest` from `BLOCK_REGISTRY` by `source:block` key, apply config overrides, render via existing `BlockRenderer`. Handle missing blocks with placeholder card. Handle empty template with "No blocks configured" state. | `apps/dashboard/components/shared/TemplateRenderer.tsx` |
| 0.4 | frontend | low | Create API route using `createAPIRoute` pattern. `toolName: 'resolve-template'`. Pass `hub` and `id` from URL params. `transformResponse` maps Python output to `ResolvedTemplate` TypeScript type. `gracefulFallback` returns empty template. | `apps/dashboard/app/api/dashboard/template/[hub]/[id]/route.ts` |
| 0.5 | frontend | low | Create `useActiveTemplates(hub)` hook. Reads `~/Vault/Augur/dashboard/active.yaml` via a new MCP tool `read-active-templates` (simple YAML file read). Returns `string[]` of active template IDs for the given hub. Create vault directory `~/Vault/Augur/dashboard/` with a seed `active.yaml` containing the test template. | `apps/dashboard/lib/templates/active.ts`, `src/mcp/augur_mcp/tools/internal/template_resolver.py` (add read-active tool) |

### Phase 1: First Templates
**Strategy**: PARALLEL
**Session**: 1 of 3 (continues)
**Gate**: 5 YAML templates render identically to their old mounted pages, all unit tests pass

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | migrator | medium | Audit existing pages across all hubs. Pick 5 simplest pages (ones that are mostly block grids with no custom logic). For each: read the TSX, identify which blocks it renders, write equivalent YAML template in `plugins/ui/templates/{hub}/{name}.yaml`. Declare `requires` based on which skills provide the blocks. Verify each template renders via `TemplateRenderer` by opening the page. | `plugins/ui/templates/**/*.yaml` |
| 1.2 | frontend | medium | Update `HubLandingPage.tsx`: after loading assembled-hubs.json tabs, also load `active.yaml` templates for this hub via `useActiveTemplates`. Render both as tabs — legacy tabs from assembled-hubs + template tabs from active.yaml. Template tabs route to a new dynamic page `/{hub}/t/[templateId]` that renders `TemplateRenderer`. | `apps/dashboard/components/plugin/HubLandingPage.tsx`, `apps/dashboard/app/[hub]/t/[templateId]/page.tsx` |
| 1.3 | tester | medium | Write tests: (a) `test_template_resolver.py` — parse YAML, merge overrides (add/remove/reorder/config), orphan detection, dependency check. (b) `test_template_renderer.test.tsx` — component renders grid with correct spans, handles missing blocks, applies config. (c) `test_active_templates.test.ts` — reads active.yaml, returns correct list per hub. Run all tests. | `tests/mcp/test_template_resolver.py`, `tests/dashboard/lib/templates/` |

### Phase 2: TSX Page Migration
**Strategy**: PIPELINE (hub by hub)
**Session**: 2 of 3
**Gate**: All pages render from `plugins/ui/pages/`, zero `contributions.pages` remain on migrated skills, `npm run build` passes

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | migrator | high | For each hub (brain, career, life, studio, command): (a) List all skills with `contributions.pages` or `augur/dashboard/` dirs. (b) For each custom TSX page, move source files to `plugins/ui/pages/{page-name}/`. (c) Add entry to `manifest.yaml` with `type: custom`, `requires: [skill-names]`, `route: /path`. (d) Update mount-plugins to also scan `plugins/ui/pages/` for custom pages. (e) Run `npm run build` after each hub. Dispatch one sub-agent per hub for parallelism. | `plugins/ui/pages/**`, `plugins/ui/manifest.yaml`, `apps/dashboard/scripts/mount-plugins.ts` |
| 2.2 | migrator | medium | For each migrated skill: remove `contributions.pages` from `x-augur-config` in SKILL.md. Remove `augur/dashboard/` directory. Keep blocks, actions, MCP tools untouched. Verify no orphan imports in remaining skill files. | `.claude/skills/*/SKILL.md`, `.claude/skills/*/augur/dashboard/` |
| 2.3 | tester | medium | Full regression: (a) `npm run build` — zero errors. (b) For each migrated page, verify it loads at its route. (c) Check no duplicate routes between legacy and new. (d) Run existing dashboard tests. (e) Run Phase 2 UI Validation Tests. | `apps/dashboard/` |

### Phase 3: Catalog + Customization
**Strategy**: PARALLEL
**Session**: 3 of 3
**Gate**: Hub landing shows catalog, page-builder edits templates, sidebar reads active.yaml

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | high | Redesign `HubLandingPage.tsx` as template catalog. Top section: active templates as tab cards (click navigates). Bottom section: available templates as cards with "+ add" button and dependency list. "+ Create from scratch" button at bottom. Activation writes to `active.yaml` via MCP tool. Use shadcn Card, Badge, Button components. | `apps/dashboard/components/plugin/HubLandingPage.tsx` |
| 3.2 | frontend | high | Add "Edit Template" mode to page-builder. When opened with `?template={hub}/{id}` param: load the resolved template YAML, populate page-builder canvas with blocks. On save: write override file to vault (not modify base). Add "Edit" button to template page header that opens page-builder with this param. | `.claude/skills/page-builder/augur/`, `apps/dashboard/components/shared/TemplateRenderer.tsx` |
| 3.3 | frontend | medium | Replace assembled-hubs.json sidebar with active.yaml-driven navigation. Read `active.yaml` per hub. Each active template = one sidebar tab. Custom TSX pages from manifest.yaml also appear. Sort by user-defined order (from active.yaml) or template default order. Keep hub-level navigation (brain, career, life, studio, command) unchanged. | `apps/dashboard/lib/navigation.ts` |
| 3.4 | tester | medium | Run Phase 3 UI Validation Tests. Verify catalog renders, edit mode works, sidebar reflects active.yaml. | `apps/dashboard/` |

### Phase 4: Dependencies + Onboarding
**Strategy**: PARALLEL
**Session**: 3 of 3 (continues)
**Gate**: Auto-enable works, placeholder renders, onboarding shows catalog

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | backend | medium | In `template_resolver.py`: when resolving dependencies, check if each required skill is enabled (has SKILL.md + registered MCP tools). If internal and not enabled, call skill enable logic (set enabled flag in config). Return dependency status per block in resolved template. | `src/mcp/augur_mcp/tools/internal/template_resolver.py` |
| 4.2 | frontend | medium | In `TemplateRenderer`: when a block's dependency is unmet and `source: skillstore`, render a styled placeholder card with skill name, description, and "Install" button that triggers skillstore flow. When internal dep was auto-enabled, render block normally (no user action needed). | `apps/dashboard/components/shared/TemplateRenderer.tsx` |
| 4.3 | frontend | high | Update onboard skill SKILL.md: add new `--templates` flag. When used, show template catalog grouped by hub instead of plugin checklist. User picks templates → derive required plugins → enable them. Write selections to `~/Vault/Augur/dashboard/active.yaml`. Falls back to current plugin-based onboarding if `--templates` not used. | `.claude/skills/onboard/SKILL.md` |
| 4.4 | tester | medium | Run Phase 4 UI Validation Tests. Full E2E: activate template with disabled plugin → auto-enable → blocks render. Run all test suites. | `apps/dashboard/` |

### Completion Criteria
- [ ] All 4 phases executed with UI validation tests passing per phase
- [ ] All unit + integration tests pass (`pytest` + `jest`)
- [ ] At least 5 existing pages converted to YAML templates
- [ ] Custom TSX pages render from `plugins/ui/pages/`
- [ ] Override merge works: add, remove, reorder, config override
- [ ] Orphan override detection works (base removes block user customized)
- [ ] Sidebar driven by `active.yaml`
- [ ] Template catalog shows available/active templates per hub
- [ ] Page-builder can load and save YAML template overrides
- [ ] Dependency auto-enable works for internal plugins
- [ ] Community skill placeholder renders with install prompt
- [ ] `npm run build` passes
- [ ] No `contributions.pages` remain on migrated skills
- [ ] ADR status updated to Implemented

### Dependency Graph

```
                            0.1 types + dir structure
                           /          \
                        0.2            0.3
                     MCP resolver    TemplateRenderer
                    /   |    \          |      \
                 0.4   0.5    \        |       \
              API route active  \      |        \
                        |       \     |         \
                        +--------+----+          |
        +---------------+--------+----+----------+
        v               v        v    v          v
      1.1             1.2       1.3  3.2*       4.2*
   5 YAML tmpl    hub landing  tests p-builder  placeholder
        |               |       |
        +-------+-------+       |
                v               |
              2.1               |
        move TSX pages          |
           /       \           |
        2.2         3.1        |
     rm contrib.   catalog     |
        pages         |        |
          |           |        |
        2.3         3.3       4.1*    4.3*
     regression    sidebar   auto-en  onboard
          |           |        |        |
          |         3.4       4.4      |
          |        catalog   dep       |
          |        tests     tests     |
          +-----+---+--+------+-------+
                v
         DONE - all gates pass
```

`*` = can start early (only needs Phase 0), but touches files that Phase 2 also touches — use worktree isolation.

### Parallel Execution Plan (single session)

All phases in one session at 20:00 IST. 7 waves, maximum parallelism within each.

| Wave | Tasks | Agents | Wait for | Est. Duration |
|------|-------|--------|----------|---------------|
| **Wave 1** | 0.1 (types + dirs) | 1 | — | ~10 min |
| **Wave 2** | 0.2 (MCP resolver), 0.3 (TemplateRenderer) | 2 | Wave 1 | ~20 min |
| **Wave 3** | 0.4 (API route), 0.5 (active.yaml hook) | 2 | Wave 2 | ~15 min |
| **Wave 4** | 1.1 (5 YAML templates), 1.2 (hub landing), 1.3 (tests) | 3 | Wave 3 | ~30 min |
| **Wave 5** | 2.1 (move TSX), 3.2 (page-builder edit), 4.1 (auto-enable), 4.2 (placeholder), 4.3 (onboard) | 5 | Wave 4, each in worktree | ~40 min |
| **Wave 6** | 2.2 (rm contributions.pages), 3.1 (catalog), 3.3 (sidebar) | 3 | 2.1 from Wave 5 | ~25 min |
| **Wave 7** | 2.3 (regression), 3.4 (catalog tests), 4.4 (dep tests) | 3 | Wave 6 | ~20 min |
| **Merge** | Merge all worktrees, resolve conflicts, final `npm run build` | 1 | Wave 7 | ~20 min |

**Total: ~24 agents, ~3-4 hours wall clock, ~$360 off-peak**

### Session Schedule (alternative: multi-session)

If single session is too heavy, split across days:

| Session | Phases | Waves | Est. Duration | Est. Cost (off-peak) |
|---------|--------|-------|---------------|----------------------|
| Session 1 (today 20:00 IST) | Phase 0 + Phase 1 | Waves 1-4 | ~1.5 hours | ~$62 |
| Session 2 (tomorrow 20:00 IST) | Phase 2 + Phase 3 + Phase 4 | Waves 5-7 + merge | ~2.5 hours | ~$210 |
| **Total** | | | **~4 hours** | **~$275 + 30% buffer = ~$360** |
