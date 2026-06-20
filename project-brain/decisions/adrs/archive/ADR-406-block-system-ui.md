---
status: Implemented
date: '2026-03-09'
accepted: '2026-03-22'
implemented: '2026-05-05'
deciders:
- Gur Sannikov
related:
- ADR-274 (Block Interactivity Tiers)
hub: null
tags:
- block
- system
- composable
- view
- dashboard
superseded_by: null
---

# ADR-406: Block System UI — Composable Block Views Alongside Hub Pages

## Context

Augur's dashboard is organized as 6 hubs (adaptive, brain, career, command, life, studio), each exposing multiple pages via plugin `contributions.pages[]`. This architecture has accumulated pain points:

1. **Rigid composition** — Users cannot customize their dashboard. Every hub overview shows a fixed arrangement of sections. Placing a finance summary next to a calendar requires navigating different hubs.
2. **No cross-hub composition** — Seeing recipes next to calendar next to portfolio requires navigating three different hubs.
3. **Duplication** — The same UI patterns (stat cards, data lists, card grids) are re-implemented across plugins with inconsistent APIs.

### Current State (2026-03-22)

The block system is **substantially implemented** as infrastructure. The hub page system remains the primary navigation.

| Layer | Status | Detail |
|-------|--------|--------|
| Block type system | Complete | 16 canonical types defined in `apps/dashboard/lib/blocks/types.ts` |
| Block components | Complete | 16 components in `apps/dashboard/components/blocks/types/` |
| Block registry | Complete | 140 blocks auto-generated from SKILL.md frontmatter (3,383 lines) |
| Registry generator | Complete | `apps/dashboard/scripts/generate-block-registry.ts` |
| ViewCanvas | Complete | `react-grid-layout` 12-column drag/drop grid with responsive breakpoints |
| BlockRenderer | Complete | ErrorBoundary, WebMCP reporting, manifest resolution, data lifting |
| useBlockData hook | Complete | React Query with stale-while-revalidate, envelope unwrapping, deduplication |
| Block resolver | Complete | Dynamic imports for all 16 types, manifest lookup from registry |
| View storage | Complete | YAML-based CRUD in `AUGUR_STATE_DIR/views/` |
| BlockCatalogPanel | Complete | Panel for browsing and adding blocks to views |
| BlockConfigPanel | Complete | Per-instance block configuration panel |
| View page (`/view/[id]`) | Complete | Full editing UI with ViewCanvas, catalog panel, config panel |
| Browse page (`/browse`) | Complete | Skill catalog with block detail pages |
| WebMCP block tools | Complete | `blocks.discover`, `blocks.read`, `blocks.configure`, `blocks.act` |
| WebMCP view tools | Complete | `views.manage` (list, create, update, delete), `views.compose` |
| `/api/blocks/data` route | Complete | `apps/dashboard/app/api/blocks/data/route.ts` |
| `/api/views` routes | Complete | `apps/dashboard/app/api/views/route.ts` plus `[id]/route.ts`, `[id]/blocks/route.ts`, `[id]/blocks/[instanceId]/route.ts` |
| `/api/blocks/catalog` route | Complete | `apps/dashboard/app/api/blocks/catalog/route.ts` |
| Hub overview deletion | **Intentionally retained** | Hub pages remain — blocks coexist alongside, not replace (per Decision below) |

## Decision

Accept the block system as a **parallel composition layer** alongside hub pages, not a replacement. Hub pages remain the primary navigation. Blocks provide cross-hub composition for users who want custom dashboards.

### Architecture

```
Hub pages (existing, primary)     Block views (new, optional)
/career/pipeline                  /view/abc123 (user-composed canvas)
/life/recipes                     /view/def456 (cross-hub dashboard)
/command/daemon                   /browse (block & skill catalog)
```

### What's Built

#### 16 Block Types

| Type | Component | Purpose |
|------|-----------|---------|
| `stat-card` | `StatCardBlock.tsx` | Single stat display |
| `stat-grid` | `StatGridBlock.tsx` | Multiple stat cards |
| `data-list` | `DataListBlock.tsx` | Searchable/filterable list |
| `data-table` | `DataTableBlock.tsx` | Sortable table with row actions |
| `card-grid` | `CardGridBlock.tsx` | Grid or card layout |
| `chart` | `ChartBlock.tsx` | Line, bar, area, pie, donut |
| `action-bar` | `ActionBarBlock.tsx` | Action button groups |
| `calendar` | `CalendarBlock.tsx` | Calendar/scheduling |
| `activity-feed` | `ActivityFeedBlock.tsx` | Event timeline |
| `notes` | `NotesBlock.tsx` | Note-taking |
| `embed` | `EmbedBlock.tsx` | Embedded content (iframe) |
| `ops-board` | `OpsBoardBlock.tsx` | Operations dashboard |
| `progress` | `ProgressBlock.tsx` | Progress bars |
| `kanban` | `KanbanBlock.tsx` | Kanban boards |
| `tabbed` | `TabbedBlock.tsx` | Tabbed views |
| `markdown` | `MarkdownBlock.tsx` | Markdown content |

#### Block Component Contract

```typescript
interface BlockProps<TConfig = Record<string, unknown>> {
  instanceId: string;
  config: TConfig;
  dataSource?: DataSource;
  mode: 'compact' | 'full';
  onExpand?: () => void;
  onConfigure?: () => void;
  data?: unknown;              // Lifted from useBlockData by BlockRenderer
  loading?: boolean;
  error?: string | null;
  rowActions?: RowAction[];
  editableFields?: EditableField[];
  // ADR-274 Tier 1
  search?: BlockSearch;
  filters?: BlockFilter[];
  quickAdd?: BlockQuickAdd;
  groupBy?: BlockGroupBy;
  // ADR-274 Tier 2
  viewModes?: string[];
  defaultView?: string;
  exportEnabled?: boolean;
}
```

#### View Data Model

```typescript
interface View {
  id: string;
  title: string;
  icon?: string;
  pinned: boolean;
  createdAt: string;
  updatedAt: string;
  layout: { columns: number; rowHeight: number };
  blocks: BlockInstance[];
}

interface BlockInstance {
  instanceId: string;
  blockId: string;        // "skill:blockId"
  config: Record<string, unknown>;
  position: { x: number; y: number; w: number; h: number };
}
```

#### Data Source Contract

All blocks fetch data via a single mechanism — `useBlockData` POSTs to `/api/blocks/data`:

```typescript
interface DataSource {
  mcpTool?: string;    // MCP tool name (only mechanism — no apiRoute, no fs)
}
```

The `useBlockData` hook:
- Deduplicates identical MCP tool + params across blocks
- Per-block-type stale times (calendar: 60s, activity-feed: 30s, notes: Infinity)
- Stale-while-revalidate via React Query with 3x exponential backoff retry
- Unwraps nested MCP response envelopes automatically

#### Block Manifest in SKILL.md

Plugins declare blocks in SKILL.md YAML frontmatter under `x-augur-contributions.blocks[]`:

```yaml
x-augur-contributions:
  blocks:
    - id: recipes
      type: data-list
      title: "Recipes"
      icon: ChefHat
      expandTo: /lifestyle/recipes
      configSchema:
        filter: { type: enum, options: [all, favorites, recent], default: recent }
        limit: { type: number, default: 5 }
      dataSource: { mcpTool: list-recipes }
```

140 blocks are currently registered across all hubs.

#### Navigation

Blocks live under the `(views)` route group:
- `/` — redirects to `/browse`
- `/browse` — skill and block catalog
- `/browse/blocks/[blockId]` — single block detail page
- `/browse/[skill]` — skill detail page
- `/view/[id]` — user-composed view canvas (editing, catalog panel, config panel)

Hub tab navigation (`/career`, `/life`, etc.) remains unchanged.

### Completion (2026-05-05)

All three previously missing API routes are now wired:

1. **`POST /api/blocks/data`** — `apps/dashboard/app/api/blocks/data/route.ts`
2. **`/api/views` CRUD** — `apps/dashboard/app/api/views/route.ts` + `[id]/route.ts`, `[id]/blocks/route.ts`, `[id]/blocks/[instanceId]/route.ts`
3. **`GET /api/blocks/catalog`** — `apps/dashboard/app/api/blocks/catalog/route.ts`

The block system is fully operational alongside hub pages. Hub overview deletion was intentionally not pursued (parallel composition layer model preserved).

## Consequences

### Positive

- Users can compose custom dashboards from any plugin's blocks
- Cross-hub composition (finance + calendar + notes on one canvas)
- 16 block types cover all common dashboard patterns
- 140 blocks discoverable from plugin metadata
- Grid-based layout with drag/resize via `react-grid-layout`
- Per-instance config (same block type, different settings per view)
- ErrorBoundary per block — one crash doesn't break the view
- WebMCP integration allows agents to discover and interact with blocks
- Hub pages unaffected — zero migration risk

### Negative

- `react-grid-layout` dependency added
- Three missing API routes mean blocks don't fetch real data yet
- Parallel systems (hub pages + views) add surface area
- Plugin authors must add `x-augur-contributions.blocks[]` to SKILL.md frontmatter

### Neutral

- Hub pages (`/career/pipeline`, `/life/recipes`, etc.) keep their routes unchanged
- Blocks expand to hub pages via `expandTo` — the two systems link naturally
- Plugin file structure unchanged — blocks are declared in SKILL.md frontmatter
- Existing API routes unchanged — blocks use them indirectly via MCP tools

## Alternatives Considered

### Alternative 1: Full Hub Replacement

Delete all hub overview pages, replace with block views only. Force users to compose everything.

**Rejected**: Too disruptive. Hub pages work well for structured navigation. Blocks add flexibility without removing structure.

### Alternative 2: Overlay System

Build block views on top of existing pages with a toggle switch.

**Rejected**: Dual navigation toggle adds confusion. Better to have blocks as a separate route group (`/view/[id]`) that coexists naturally.

## Implementation Order

### Phase 1: Wire Missing API Routes (Critical — unlocks all block data)

| Step | Task | Files |
|------|------|-------|
| 1.1 | Create `POST /api/blocks/data` — accepts `{tool, args}`, calls MCP tool via MCPBridge, returns result | Proxy route config |
| 1.2 | Create `/api/views` CRUD — wire `ViewStorage` to REST endpoints (list, get, create, update, delete) | Proxy route config or standalone routes |
| 1.3 | Create `GET /api/blocks/catalog` — return `BLOCK_REGISTRY` as JSON array | Proxy route config |

### Phase 2: Verification

| Step | Task |
|------|------|
| 2.1 | Verify blocks render real data (not loading shimmer) on `/view/[id]` |
| 2.2 | Verify view CRUD works (create view, add blocks, save, reload) |
| 2.3 | Verify block catalog panel shows all 140 blocks |
| 2.4 | `npm run build` passes |

### Completion Criteria

- [x] 16 block type components implemented
- [x] Block registry generates from all plugins (140 blocks)
- [x] ViewCanvas drag/resize works
- [x] BlockRenderer with ErrorBoundary and data lifting
- [x] useBlockData hook with deduplication and caching
- [x] View storage CRUD logic (ViewStorage class)
- [x] BlockCatalogPanel and BlockConfigPanel
- [x] View page (`/view/[id]`) with editing UI
- [x] Browse page (`/browse`) with skill catalog
- [x] WebMCP block and view tools
- [x] `/api/blocks/data` route exists and calls MCP tools
- [x] `/api/views` CRUD routes exist
- [x] `/api/blocks/catalog` route exists
- [x] Blocks display real data (not loading state)
- [x] Full build passes with routes wired

## References

- ADR-274: Block Interactivity Tiers (search, filters, quick-add, group-by, charts, kanban, tabs)
- `apps/dashboard/lib/blocks/types.ts` — Type system
- `apps/dashboard/lib/blocks/generated-block-registry.ts` — 140-block registry
- `apps/dashboard/components/blocks/ViewCanvas.tsx` — Grid layout engine
- `apps/dashboard/components/blocks/BlockRenderer.tsx` — Block rendering with data lifting
- `apps/dashboard/lib/blocks/useBlockData.ts` — Data fetching hook
- `apps/dashboard/lib/blocks/view-storage.ts` — View persistence
- `apps/dashboard/scripts/generate-block-registry.ts` — Registry generator
- `apps/dashboard/lib/webmcp/tools/blocks.ts` — WebMCP block tools
- `apps/dashboard/lib/webmcp/tools/views.ts` — WebMCP view tools
