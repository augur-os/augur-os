---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- auto
- page
- capability
- enhancements
superseded_by: null
---

# ADR-274: Auto-Page Capability Enhancements

**Related ADRs**: ADR-272 (Enhanced Auto-Pages), ADR-406 (Block System UI), ADR-273 (Page Cleanup — Auto-Page Consolidation and Stub Removal)

## Context

ADR-273 removed 111 stub/low-quality pages, leaving ~142 genuine custom pages. A follow-up analysis (see `docs/superpowers/specs/2026-03-12-pages-cleanup-design.md`) identified that 76 of these can be converted to auto-pages — but only if `<SkillAutoPage>` gains capabilities that the custom pages currently provide.

Today, SkillAutoPage renders 12 section types (stats, actions, health, vault notes, documents, data files, config, MCP tools, logs, docs, assets, custom sources). This covers read-only dashboards well. But the 76 conversion candidates need interactive patterns: search, filtering, inline editing, grouped lists, progress indicators, and more.

Without these enhancements, the pages cleanup migration (planned as a separate ADR) cannot proceed beyond Wave 1 (empty wrappers and mocks).

### Current Auto-Page Capability Matrix

| Capability | Status | Component |
|-----------|--------|-----------|
| Stat grids | Full | StatsSection, MetricsGridRenderer |
| Data tables (sort, paginate, row actions) | Full | DataTableRenderer |
| Actions/buttons | Full | ActionsSection |
| Health/status badges | Full | HealthSection |
| Documents (file listing) | Full | DocumentsSection |
| Data files preview | Full | DataPreviewSection |
| Logs/activity feed | Full | LogsSection |
| Markdown docs | Full | DocsSection |
| Timeline | Full | TimelineRenderer |
| Vault notes | Partial | VaultNotesSection (no search/expand) |
| Charts | Stub | ChartRenderer (placeholder bar only) |
| Config | Partial | ConfigSection (read-only) |
| Custom data sources | Stub | CustomSourceSection (no renderers wired) |

## Decision

Enhance SkillAutoPage with 13 capabilities across 3 tiers, implemented as ADR-406 block-type renderers wired through the existing `dataSources` mechanism in augur.yaml.

### Tier 1: Core Interactive Patterns

Required for converting ~50 pages (stats-grid and data-table pages).

#### D1: Search & Filtering

Add a search input and filter pill bar as composable features on any section.

**Search**: A text input above any data section that filters rows/items client-side by matching against configurable fields.

```yaml
contributions:
  data_sources:
    - id: job-pipeline
      type: api_route
      source: /api/career/career/jobs
      display: data-table
      search:
        enabled: true
        fields: [title, company, status]
        placeholder: "Search jobs..."
```

**Filters**: Pill-style toggle buttons for discrete values (status, category, tag). Derived from data or declared statically.

```yaml
      filters:
        - field: status
          type: pills        # pills | dropdown | toggle
          values: [inbox, active, offer, rejected]
          colors:
            inbox: blue
            active: amber
            offer: emerald
            rejected: rose
```

**Implementation**: New `SearchBar` and `FilterBar` components composed into section wrappers. Client-side filtering via `useMemo` over fetched data. No backend changes needed.

#### D2: Inline Quick-Add

A collapsible form row at the top of data sections for creating new items without navigating away.

```yaml
      quick_add:
        enabled: true
        fields:
          - name: title
            type: text
            required: true
            placeholder: "New task..."
          - name: priority
            type: select
            options: [high, medium, low]
        action: create-task    # references an action ID in augur.yaml
```

**Implementation**: New `QuickAddRow` component renders a compact inline form. On submit, dispatches the referenced action via `useActionRunner`. Form resets after success. Validates required fields client-side.

#### D3: Grouping & Collapsible Lists

Group data items by a field value with collapsible headers showing count badges.

```yaml
      display: grouped-list
      group_by:
        field: category
        collapsed_default: false
        show_count: true
        sort: alphabetical    # alphabetical | count-desc | custom
```

**Implementation**: New `GroupedListRenderer` that wraps existing `DataTableRenderer` rows into collapsible `<details>` groups. Group headers show field value + count badge. Expand/collapse all button in section toolbar.

#### D4: Computed Stats

Allow stat values to be computed from data source responses via declarative expressions.

```yaml
contributions:
  data_sources:
    - id: budget-summary
      type: api_route
      source: /api/finance/finance/budget
      display: stat-grid
      stats:
        - label: "Total Budget"
          value: "sum(items, 'budget')"
          format: currency
        - label: "Spent"
          value: "sum(items, 'spent')"
          format: currency
        - label: "Remaining"
          value: "sum(items, 'budget') - sum(items, 'spent')"
          format: currency
          color_rule: "value < 0 ? 'rose' : 'emerald'"
```

**Supported functions**: `sum(array, field)`, `count(array)`, `count(array, field, value)`, `avg(array, field)`, `min(array, field)`, `max(array, field)`, `percent(part, total)`.

**Expression grammar**: Supports arithmetic (`+`, `-`, `*`, `/`), comparisons (`<`, `>`, `<=`, `>=`, `==`, `!=`), ternary conditionals (`condition ? value_a : value_b`), and the whitelisted aggregate functions above. String literals must be single-quoted. No variable access beyond `value`, `percent`, `items`, and function arguments.

**Implementation**: New `computeStatValue` utility using the `expr-eval` library (lightweight, sandboxed expression parser with no access to `window`/`document`/`globalThis`). The parser is configured with a restricted operator set — only arithmetic, comparison, and ternary operators are enabled. All function names are whitelisted; unrecognized function calls throw a parse error. Dynamic code execution is explicitly prohibited — no JS runtime evaluation of any kind. Integrated into `StatsSection` when `stats[].value` is a string expression rather than a static value.

### Tier 2: Rich Display Patterns

Required for converting ~30 pages (markdown browsers, complex data views).

#### D5: View Mode Toggles

Toggle between list, grid, and card views for the same data source.

```yaml
      view_modes:
        - list        # table rows
        - grid        # card grid (2-3 columns)
        - card        # single-column detail cards
      default_view: grid
```

**Implementation**: New `ViewModeToggle` component (icon buttons in section toolbar). Each mode delegates to existing renderers: list → `DataTableRenderer`, grid → new `CardGridRenderer`, card → new `DetailCardRenderer`. View state persisted in `localStorage` per section ID.

**Note**: `DetailCardRenderer` is a new component alongside `CardGridRenderer` — both are listed in the Impact Manifest.

#### D6: Progress Bars

Visual progress indicators for goal/budget tracking.

```yaml
      display: progress-list
      progress:
        value_field: spent
        max_field: budget
        label_field: category
        format: currency
        color_rule: "percent > 100 ? 'rose' : percent > 80 ? 'amber' : 'emerald'"
```

**Implementation**: New `ProgressListRenderer` renders rows with label, progress bar (Tailwind `bg-*` width percentage), and value/max text. Color rules evaluated per row. Reuses the safe expression evaluator from D4.

#### D7: Image Gallery

Media grid with category grouping and lightbox preview.

```yaml
      display: image-gallery
      gallery:
        columns: 3
        group_by: category    # optional
        lightbox: true
        show_caption: true
```

**Implementation**: New `ImageGalleryRenderer` renders a responsive CSS grid of image thumbnails. Click opens a lightbox modal (new `Lightbox` component with Escape-to-close, arrow navigation). Images loaded lazily via `loading="lazy"`. Supports grouping via D3's collapsible headers.

#### D8: Modal Detail Views

Click a row/card to open a detail modal with full item data.

```yaml
      row_action:
        type: modal
        title_field: name
        sections:
          - field: description
            render: markdown
          - field: metadata
            render: key-value
          - field: notes
            render: text
```

**Implementation**: New `DetailModal` component triggered by row click or card click. Renders configured field sections using existing renderers (markdown, key-value, text). Modal state managed via URL search params namespaced by section ID (`?{sectionId}_detail=item-id`) to avoid collisions when multiple sections on the same page use modals or tabs (see D13).

#### D9: Production Charts

Replace placeholder chart renderer with real charting library.

```yaml
      display: chart
      chart:
        type: bar          # bar | line | area | pie | donut
        x_field: month
        y_field: amount
        color: blue
        height: 200
```

**Implementation**: Integrate Recharts (already in Next.js ecosystem, tree-shakeable). New `RechartsRenderer` replaces stub `ChartRenderer`. Supports bar, line, area, pie, donut. Responsive container. Tooltip on hover. Legend for multi-series.

### Tier 3: Extended Patterns

Nice-to-have capabilities that improve polish.

#### D10: CSV Export

Export button on data sections that downloads current view as CSV.

```yaml
      export:
        enabled: true
        format: csv          # csv | json
        filename: "transactions-{date}"
```

**Implementation**: New `ExportButton` in section toolbar. Uses `papaparse` to serialize current (filtered) data to CSV. Triggers browser download via Blob URL. Filename supports `{date}` and `{skill}` template tokens.

#### D11: Vault Notes Search & Expand

Enhance existing VaultNotesSection with search input and expand-to-read.

**Note**: Unlike D1-D10 and D12-D13 which configure behavior under `contributions.data_sources[]`, D11 enhances a first-class auto-page section (`VaultNotesSection`) that already renders automatically for any skill with vault notes. The config lives under `contributions.pages[]` because it modifies section behavior rather than declaring a new data source.

```yaml
contributions:
  pages:
    - path: /finance/knowledge
      vault_notes:
        search: true
        expandable: true
```

**Implementation**: Add `SearchBar` (from D1) above vault notes list. Add expand/collapse toggle per note that lazy-fetches full content via API and renders with `ReactMarkdown`. Reuses patterns from D1 and D3.

#### D12: Kanban Board

Drag-and-drop board layout with swim lanes by status field.

```yaml
      display: kanban
      kanban:
        column_field: status
        columns: [todo, in-progress, done]
        card_title_field: title
        card_subtitle_field: assignee
        on_move:
          action: update-task-status    # references action ID in augur.yaml
          payload:
            id_field: id
            status_field: status
```

**Implementation**: New `KanbanRenderer` using `@dnd-kit/core` for drag-and-drop. Columns rendered from configured field values. Cards show title + subtitle. Drop handler dispatches the `on_move.action` via `useActionRunner` with payload mapping (`id_field` → item ID, `status_field` → new column value). Column headers show count badges.

#### D13: Tabbed Sections

Group multiple data sources into tabs within a single section.

```yaml
      display: tabs
      tabs:
        - id: overview
          label: Overview
          source: overview-stats
        - id: details
          label: Details
          source: detail-table
        - id: history
          label: History
          source: history-timeline
```

**Implementation**: New `TabbedSectionRenderer` wraps existing section renderers in a tab bar. Active tab persisted in URL search params namespaced by section ID (`?{sectionId}_tab=details`) to avoid collisions with D8 modals and other tabbed sections on the same page. Lazy-loads tab content on first activation.

## Consequences

### Positive

- **Unblocks 76-page migration** — all conversion waves can proceed after implementation
- **Reduces custom page maintenance** by ~74% (103 → 27 custom pages)
- **Composable architecture** — capabilities are reusable across any skill's auto-page via augur.yaml config
- **No breaking changes** — enhancements are additive to existing SkillAutoPage sections
- **Declarative over imperative** — page behavior configured in YAML, not TSX

### Negative

- **New dependencies** — Recharts (D9), @dnd-kit/core (D12), papaparse (D10) add bundle size
- **Expression evaluator complexity** — D4's safe expression parser needs careful security review (whitelist-only, no dynamic code execution)
- **13 new components** — increases component surface area in the design system
- **YAML schema expansion** — augur.yaml grows more complex; needs validation tooling

### Neutral

- Existing auto-page sections remain unchanged — enhancements are new renderers alongside existing ones
- Custom pages are unaffected — the 27 KEEP pages continue using hand-written TSX

## Alternatives Considered

### Alternative 1: Enhance Custom Pages Instead of Auto-Pages

Extract shared components from the 76 pages into a component library, keeping custom page.tsx files but reducing duplication.

Rejected. This preserves 76 page.tsx files that still need individual maintenance. The declarative augur.yaml approach means skills can gain capabilities without writing TSX, which aligns with the plugin decentralization principle (CLAUDE.md rule 1).

### Alternative 2: Build a Visual Page Builder Instead

Extend ADR-190's page builder to let users compose auto-pages visually rather than via YAML.

Rejected for now. The YAML-first approach is faster to implement and easier to validate. A visual builder can be layered on top of the YAML schema later without architectural changes.

### Alternative 3: Implement Only Tier 1, Defer Tier 2-3

Ship search/filtering/grouping/computed stats, then reassess whether Tier 2-3 are needed.

Rejected. The wave analysis shows Tier 2 is required for Waves 3-4 (30+ pages need progress bars, charts, or modal detail views). Deferring would leave the migration permanently incomplete.

## Testing

### T1: Search & Filtering (D1)
- Verify search input filters data table rows by configured fields
- Verify filter pills toggle and combine correctly (multi-select)
- Verify empty state when no results match

### T2: Quick-Add (D2)
- Verify form renders with configured fields
- Verify required field validation
- Verify action dispatch on submit and form reset on success

### T3: Grouping (D3)
- Verify items grouped by field value with correct counts
- Verify expand/collapse per group and expand-all toggle
- Verify sort order (alphabetical, count-desc)

### T4: Computed Stats (D4)
- Verify sum, count, avg, min, max, percent functions
- Verify color rules evaluate correctly
- Verify format options (currency, percentage, number)
- Verify no code injection via expression parser (whitelist-only functions, no access to window/document/globalThis)

### T5: View Mode Toggles (D5)
- Verify toggle between list/grid/card views
- Verify localStorage persistence of view preference
- Verify data consistency across view modes

### T6: Progress Bars (D6)
- Verify bar width calculation (value/max as percentage)
- Verify color rule thresholds
- Verify edge cases (0%, >100%, missing data)

### T7: Image Gallery (D7)
- Verify grid layout with configured columns
- Verify lightbox open/close and keyboard navigation
- Verify lazy loading of images

### T8: Modal Detail Views (D8)
- Verify modal opens on row/card click
- Verify URL deep-link (?detail=id) works on page load
- Verify field sections render correctly (markdown, key-value, text)

### T9: Production Charts (D9)
- Verify bar, line, area, pie, donut chart types render
- Verify responsive container sizing
- Verify tooltip and legend display

### T10: CSV Export (D10)
- Verify CSV download with correct data (respects current filters)
- Verify filename template tokens resolve

### T11: Vault Notes Search (D11)
- Verify search filters notes by content/title
- Verify expand/collapse loads full note content

### T12: Kanban Board (D12)
- Verify columns render from configured field values
- Verify drag-and-drop moves items between columns
- Verify update action dispatches on drop

### T13: Tabbed Sections (D13)
- Verify tabs render with labels
- Verify tab switching loads correct data source
- Verify active tab persists in URL

### T14: Accessibility
- Verify Lightbox (D7) closes on Escape key
- Verify GroupedListRenderer (D3) uses `aria-expanded` on collapsible headers
- Verify KanbanRenderer (D12) columns are keyboard-navigable
- Verify DetailModal (D8) traps focus and closes on Escape
- Verify D8 and D13 URL params coexist on the same page without collision

### T15: Build and Regression
- `npm run build` passes after all enhancements
- All pre-existing auto-page tests pass
- No performance regression (LCP < 500ms on simulated Fast 3G via lighthouse-ci)

## Impact Manifest

```yaml
impact:
  new_components:
    - path: "src/components/plugin/auto-page/SearchBar.tsx"
      tier: 1
    - path: "src/components/plugin/auto-page/FilterBar.tsx"
      tier: 1
    - path: "src/components/plugin/auto-page/QuickAddRow.tsx"
      tier: 1
    - path: "src/components/plugin/auto-page/GroupedListRenderer.tsx"
      tier: 1
    - path: "src/components/plugin/auto-page/computeStatValue.ts"
      tier: 1
    - path: "src/components/plugin/auto-page/ViewModeToggle.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/CardGridRenderer.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/DetailCardRenderer.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/ProgressListRenderer.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/ImageGalleryRenderer.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/Lightbox.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/DetailModal.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/RechartsRenderer.tsx"
      tier: 2
    - path: "src/components/plugin/auto-page/ExportButton.tsx"
      tier: 3
    - path: "src/components/plugin/auto-page/KanbanRenderer.tsx"
      tier: 3
    - path: "src/components/plugin/auto-page/TabbedSectionRenderer.tsx"
      tier: 3
  modified_components:
    - path: "src/components/plugin/SkillAutoPage.tsx"
      change: "Wire new renderers into dataSources dispatch"
    - path: "src/components/plugin/auto-page/VaultNotesSection.tsx"
      change: "Add search and expand/collapse (D11)"
    - path: "src/components/plugin/auto-page/StatsSection.tsx"
      change: "Support computed stat expressions (D4)"
  new_dependencies:
    - package: "expr-eval"
      tier: 1
      reason: "Safe expression evaluation for computed stats and color rules (D4, D6)"
    - package: "recharts"
      tier: 2
      reason: "Production chart rendering (D9)"
    - package: "@dnd-kit/core"
      tier: 3
      reason: "Kanban drag-and-drop (D12)"
    - package: "papaparse"
      tier: 3
      reason: "CSV export (D10)"
  schema_changes:
    - file: "augur.yaml"
      additions: "search, filters, quick_add, group_by, view_modes, progress, gallery, row_action, chart, export, kanban, tabs fields in data_sources"
    - file: "augur.yaml"
      additions: "vault_notes.search, vault_notes.expandable fields in contributions.pages[] (D11)"
```

## Implementation Prompt

**Team name**: `adr-274-auto-page-enhancements`

### Phase 1: Tier 1 — Core Interactive Patterns
**Strategy**: PIPELINE (D4 computeStatValue needed by D6 color rules)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | implementer | medium | D1: Build SearchBar + FilterBar components, integrate into section wrapper | `src/components/plugin/auto-page/SearchBar.tsx`, `FilterBar.tsx` |
| 1.2 | implementer | medium | D2: Build QuickAddRow with field rendering and action dispatch | `src/components/plugin/auto-page/QuickAddRow.tsx` |
| 1.3 | implementer | medium | D3: Build GroupedListRenderer with collapsible headers and count badges | `src/components/plugin/auto-page/GroupedListRenderer.tsx` |
| 1.4 | implementer | medium | D4: Build computeStatValue safe expression evaluator, integrate into StatsSection | `src/components/plugin/auto-page/computeStatValue.ts`, `StatsSection.tsx` |
| 1.5 | validator | low | Wire D1-D4 into SkillAutoPage dataSources dispatch, verify with test skill | `SkillAutoPage.tsx` |

### Phase 2: Tier 2 — Rich Display Patterns
**Strategy**: PARALLEL (independent renderers, after Phase 1 completes — Step 2.2 depends on D4's computeStatValue from Phase 1 Step 1.4)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | implementer | medium | D5: Build ViewModeToggle + CardGridRenderer + DetailCardRenderer | `ViewModeToggle.tsx`, `CardGridRenderer.tsx`, `DetailCardRenderer.tsx` |
| 2.2 | implementer | medium | D6: Build ProgressListRenderer using D4 expression evaluator | `ProgressListRenderer.tsx` |
| 2.3 | implementer | medium | D7: Build ImageGalleryRenderer + Lightbox | `ImageGalleryRenderer.tsx`, `Lightbox.tsx` |
| 2.4 | implementer | medium | D8: Build DetailModal with URL deep-linking | `DetailModal.tsx` |
| 2.5 | implementer | medium | D9: Integrate Recharts, build RechartsRenderer replacing stub | `RechartsRenderer.tsx`, `ChartRenderer.tsx` |
| 2.6 | validator | low | Wire D5-D9 into SkillAutoPage, verify with test skills | `SkillAutoPage.tsx` |

### Phase 3: Tier 3 — Extended Patterns
**Strategy**: PARALLEL (independent features)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | implementer | low | D10: Build ExportButton with papaparse CSV serialization | `ExportButton.tsx` |
| 3.2 | implementer | low | D11: Enhance VaultNotesSection with search + expand/collapse | `VaultNotesSection.tsx` |
| 3.3 | implementer | medium | D12: Build KanbanRenderer with @dnd-kit drag-and-drop | `KanbanRenderer.tsx` |
| 3.4 | implementer | low | D13: Build TabbedSectionRenderer with URL-persisted active tab | `TabbedSectionRenderer.tsx` |
| 3.5 | validator | low | Wire D10-D13 into SkillAutoPage, verify with test skills | `SkillAutoPage.tsx` |

### Phase 4: Schema Validation & Documentation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | implementer | low | Add augur.yaml schema validation for new data_sources fields | `src/config/schema/` |
| 4.2 | implementer | low | Update auto-yaml-lint to validate new fields | `plugins/admin/skills/auto-yaml-lint/` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | low | `npm run build` passes |
| V.3 | architect | medium | Create 3 test skills (one per tier) that exercise all 13 capabilities via augur.yaml |

### Completion Criteria
- [ ] All 13 capabilities implemented and wired into SkillAutoPage
- [ ] augur.yaml schema validates new data_sources fields
- [ ] Test skills demonstrate each capability via YAML config (no custom TSX)
- [ ] All tests pass, build passes
- [ ] No performance regression (auto-page load time <500ms)
- [ ] New dependencies (recharts, @dnd-kit, papaparse) tree-shake correctly
