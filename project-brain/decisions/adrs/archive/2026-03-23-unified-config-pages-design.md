# Unified Config-Driven Pages

> **Status:** Draft
> **Date:** 2026-03-23
> **Scope:** Dashboard page rendering, block system, skill page config

## Problem

The dashboard has three overlapping systems for rendering skill content:

1. **SkillAutoPage** — 12 hard-coded sections, metadata API, generic skill overview
2. **Blocks** — 16 types, MCP-backed, config-driven with search/filter/actions
3. **DashboardWidget** — legacy glass panels, limited customization

This creates duplication (multiple renderers, multiple data-fetching patterns, multiple grid systems) and makes adding new pages unnecessarily complex. Creating a page currently requires writing TSX code even when the page is just stats + table + actions.

Additionally, the UI exposes blocks and auto pages via separate dropdown buttons (BlocksDropdown, AutoPagesDropdown) that overlap in purpose.

## Solution

One rendering path: a page is an ordered list of blocks declared in YAML. No separate autopage/widget concepts.

### Page Sources

| Source | Location | Purpose |
|---|---|---|
| YAML page | `skills/{skill}/augur/pages/*.yaml` | Config-driven, rendered by `ConfigPage` |
| Custom TSX page | `skills/dashboard/pages/{hub}/{slug}/page.tsx` | Complex interactions (quiz, terminal, file-manager) |
| Auto-generated | Built from skill metadata at browse-time | Every skill gets a detail page via Browse |

YAML and TSX pages coexist as first-class hub tabs. Both are registered by the scanner — a hub shows all its pages as tabs regardless of source. Migration from TSX to YAML is incremental: converting a page means writing the YAML file and deleting the TSX file.

### Page YAML Schema

Each file in `skills/{skill}/augur/pages/` defines one page:

```yaml
title: Daemon Monitor
icon: Activity
hub: command
route: daemon
order: 10                    # per-hub, alphabetical tie-break on collision
blocks:
  - type: stat-grid
    mcp_tool: get-daemon-status
  - type: chart
    mcp_tool: get-daemon-metrics
    size: half
  - type: data-table
    mcp_tool: list-jobs
    size: half
  - type: custom
    component: daemon/TerminalView
  - type: action-bar
    mcp_tool: get-daemon-actions
```

**Field mapping:** The YAML `mcp_tool` field maps directly to `DataSource.mcpTool` in the existing block data pipeline. `ConfigPage` constructs the `DataSource` object: `{ mcpTool: block.mcp_tool }`. No renaming — the field name matches the existing convention.

**Inline block config:** Page YAML blocks can declare `search`, `filters`, `row_actions`, and other ADR-274 fields inline. These are merged with the block manifest from the skill's `contributions.blocks[]` declaration (if one exists). Page YAML values take precedence over manifest defaults. If no manifest exists for the `mcp_tool`, the inline config is the sole source.

**Layout:** Blocks render top-to-bottom in declaration order. Each block has an optional `size` field:

| Size | Behavior |
|---|---|
| `full` (default) | Spans full width |
| `half` | Shares row with next half-sized block |
| `third` | Shares row with next third-sized blocks |

**Auto-flow rules:**
- Framework fills rows left-to-right based on size fractions (half = 1/2, third = 1/3)
- When a block doesn't fit in the remaining row space, it wraps to the next row
- Orphan blocks (e.g., a single `half` at the end) render at their declared size, not stretched
- Mixed sizes in one row are valid: `third` + `third` + `third` = full row, `third` + `half` wraps the half to the next row (5/6 > 1)
- No grid coordinates — only declaration order + size

**Icon validation:** Icon names reference Lucide icons. Invalid names silently fall back to `LayoutDashboard` (same as current `renderIcon` behavior in HubTabBar). No build-time validation.

### Block Types

Existing 16 types (stat-card, stat-grid, data-list, data-table, action-bar, card-grid, chart, markdown, calendar, activity-feed, notes, embed, ops-board, progress, kanban, tabbed) plus:

| New Type | Purpose | Replaces |
|---|---|---|
| `health` | Status badge with health indicators | SkillAutoPage HealthSection |
| `vault-notes` | Markdown files from vault data dir | SkillAutoPage VaultNotesSection |
| `custom-sources` | Data tables/cards from custom data sources | SkillAutoPage CustomSourceSection |
| `file-list` | File/document listing | SkillAutoPage DocumentsSection |
| `data-preview` | YAML/JSON data file viewer | SkillAutoPage DataPreviewSection |
| `custom` | Renders a registered React component | Hybrid escape hatch for complex TSX |

**All SkillAutoPage sections now have block type equivalents:**

| SkillAutoPage Section | Block Type |
|---|---|
| HealthSection | `health` |
| StatsSection | `stat-grid` |
| BlocksSection | absorbed — blocks ARE the page |
| CustomSourceSection | `custom-sources` |
| ActionsSection | `action-bar` |
| HubNotes | `notes` (with `scope: hub`) |
| VaultNotesSection | `vault-notes` |
| DocumentsSection | `file-list` |
| DataPreviewSection | `data-preview` |
| AssetsSection | dev-only block |
| ConfigSection | dev-only block |
| McpToolsSection | dev-only block |
| LogsSection | dev-only block |
| DocsSection | `markdown` |

**Dev-only blocks** (assets, config, tools, logs) are auto-appended by the framework when dev mode is active. Each has a corresponding MCP tool:

| Dev Block | MCP Tool | Data |
|---|---|---|
| assets | `file-list` with `path: {skill}/assets/` | Skill asset files |
| config | `data-preview` with `path: {skill}/config.yaml` | Skill config |
| tools | `list-mcp-tools` with `filter: {skill}` | MCP tools registered by skill |
| logs | `file-list` with `path: logs/{skill}/` | Skill log files |

### Notes Block Scope

The `notes` block type accepts a `scope` field:

```yaml
- type: notes
  scope: hub          # hub-level shared notes (default)
- type: notes
  scope: skill        # skill-specific notes
  skill_id: daemon
```

Browse detail pages use `scope: skill`. Hub pages default to `scope: hub`.

### Custom Block Type

For pages that mix config blocks with complex interactions:

```yaml
blocks:
  - type: stat-grid
    mcp_tool: get-quiz-stats
  - type: custom
    component: quiz/QuizEngine
  - type: action-bar
    mcp_tool: get-quiz-actions
```

**Resolution protocol:** Custom blocks use a build-time component registry, not runtime string resolution. The scanner collects all `type: custom` references at build time and generates a map in `apps/dashboard/lib/blocks/custom-block-registry.ts`:

```typescript
// AUTO-GENERATED
export const CUSTOM_BLOCK_COMPONENTS: Record<string, () => Promise<{ default: ComponentType }>> = {
  "quiz/QuizEngine": () => import("@skill/components/quiz/QuizEngine"),
  "daemon/TerminalView": () => import("@skill/components/daemon/TerminalView"),
};
```

`BlockRenderer` looks up the component key in this registry and uses `next/dynamic` with the factory function. If the key is not in the registry (deleted component, typo), the block renders an error state: "Component {key} not found."

**Props contract:** Custom block components receive:

```typescript
interface CustomBlockProps {
  skillId: string;
  config: Record<string, unknown>;  // from YAML block config
}
```

Custom components fetch their own data — they don't receive `data`/`loading`/`error` from `useBlockData`. This is intentional: custom blocks exist for complex cases where the standard data pipeline doesn't fit.

### Page Discovery

**Build time — scanner reads both sources:**

1. `skills/{skill}/augur/pages/*.yaml` — registered as YAML pages, rendered by ConfigPage
2. `skills/dashboard/pages/{hub}/{slug}/page.tsx` — registered as custom TSX pages, rendered directly

Both produce tab entries in the hub registry. A hub shows all its pages as tabs regardless of source.

**Browse detail pages:**

When a user clicks a skill in Browse, an auto-generated block layout renders from skill metadata:
- `health` (status badge)
- `action-bar` (skill actions)
- `notes` with `scope: skill` (skill-specific notes)
- `markdown` (SKILL.md documentation)

Same `ConfigPage` renderer — no separate SkillAutoPage component.

### ConfigPage Component

**Interface:**

```typescript
interface ConfigPageProps {
  config: PageConfig;  // parsed YAML, validated at build time
}

interface PageConfig {
  title: string;
  icon: string;
  hub: string;
  route: string;
  order?: number;
  blocks: BlockConfig[];
}

interface BlockConfig {
  type: BlockType | "custom";
  mcp_tool?: string;
  component?: string;        // only for type: custom
  size?: "full" | "half" | "third";
  scope?: "hub" | "skill";
  skill_id?: string;
  // ADR-274 inline config
  search?: BlockSearch;
  filters?: BlockFilter[];
  row_actions?: RowAction[];
  config_schema?: ConfigSchema;
  [key: string]: unknown;    // extensible for block-specific fields
}
```

**Rendering pipeline:**

1. `ConfigPage` is a **client component** (`'use client'`)
2. Page YAML is parsed at build time by the scanner and emitted as a per-route dynamic import in the hub registry (e.g., `() => import('./configs/career-pipeline.json')`). Each page config is a separate chunk — not a monolithic bundle. This keeps client JS size proportional to the pages the user actually visits.
3. `ConfigPage` receives the parsed config as a prop — no runtime YAML parsing, no API fetch for config
4. For each block in `config.blocks`:
   - Pass `BlockConfig` directly to `FlowBlockRenderer` — **not** through `BlockInstance`. The existing `BlockInstance` type carries grid coordinates (`position: { x, y, w, h }`) incompatible with flow layout. `FlowBlockRenderer` is a thin wrapper around `BlockRenderer` that constructs the `dataSource` and delegates rendering without requiring a `BlockInstance`.
   - If `type: custom`, resolve via `CUSTOM_BLOCK_COMPONENTS` registry
   - Otherwise, delegate to existing `BlockRenderer` with constructed `BlockInstance` (position set to `{ x: 0, y: 0, w: 1, h: 1 }` — ignored by flow layout)
5. Wrap in `FlowLayout` component that applies size-based auto-flow
6. If dev mode, append dev-only blocks for the page's skill
7. Error boundary per block — one block failing doesn't crash the page

**Manifest merge:** When a block in page YAML has `mcp_tool`, ConfigPage looks up the block manifest by matching `BlockManifest.id` against `{skill}:{block_type}` or `{skill}:{mcp_tool}`. If no manifest is found, the inline YAML config is the sole source (no error). If found, inline YAML fields override manifest defaults (shallow merge per field). Ambiguity (two manifests with the same tool) is resolved by requiring manifest lookup by `id`, not by tool name — the YAML block can optionally declare `manifest_id` to force a specific manifest.

**Loading/error states:** Same as current BlockRenderer — skeleton shimmer while loading, error card with retry on failure. Page-level error boundary catches component-level crashes.

### Customize Button

Replaces both BlocksDropdown and AutoPagesDropdown:

- Available on every hub page (both YAML and TSX pages)
- Opens a panel showing available blocks from all skills in the hub
- User can add blocks to the current page, reorder, resize, remove
- "Reset to default" restores the source config (YAML default for config pages, empty for TSX pages)

**Persistence:** User overrides are stored in `localStorage` keyed by page route (e.g., `augur:page-layout:/career/pipeline`). This is intentional: layout customization is client-only UI state, not user data. It follows the same pattern as the existing `augur:sidebar-visibility`, `augur:favorites`, and `augur:sidebar-order` keys already in localStorage.

**Flow layout persistence model:** Overrides store an ordered array of `{ blockId, size, added? }` entries — same data model as the YAML blocks list. No grid coordinates. The `added` flag distinguishes user-added blocks from source blocks, so "Reset to default" can remove only user additions.

### What Gets Removed

| Component | Replaced By |
|---|---|
| `SkillAutoPage.tsx` | `ConfigPage` renderer |
| `DashboardWidget.tsx` | Blocks (`stat-card`, `stat-grid`) |
| `AutoPagesDropdown.tsx` | Eliminated — pages are hub tabs or browse detail |
| `BlocksDropdown.tsx` | "Customize" button |
| `WidgetVisibilityWrapper.tsx` | Customize panel (add/remove blocks) |
| `/api/skill-meta/[skillId]` | Individual MCP tool calls per block |

### Migration Path

1. Build `ConfigPage` renderer, `FlowLayout`, YAML scanner, custom block registry
2. Convert simplest existing TSX pages first (pages that are just stats + table)
3. Complex pages stay as TSX — optionally get `custom` block escape hatch
4. Each conversion: write YAML, delete TSX, verify
5. Remove SkillAutoPage, DashboardWidget, dropdown components after all consumers migrated

### Example: Career Pipeline (before/after)

**Before** — `skills/dashboard/pages/career/pipeline/page.tsx` (291 lines of TSX):
- Fetches career status and jobs via useMcpQuery
- Renders stat cards, pipeline table, filters

**After** — `skills/career/augur/pages/pipeline.yaml` (~25 lines):
```yaml
title: Job Pipeline
icon: Briefcase
hub: career
route: pipeline
order: 30
blocks:
  - type: stat-grid
    mcp_tool: get-career-status
  - type: data-table
    mcp_tool: get-career-jobs
    search:
      enabled: true
      fields: [title, company, status]
    filters:
      - field: status
        type: pills
        values: [inbox, active, offer, rejected, archive]
    row_actions:
      - id: analyze
        icon: Search
        label: Analyze
        dispatch: ide
```

291 lines of TSX → 25 lines of YAML. Same visual result.
