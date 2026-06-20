---
status: Implemented
date: '2026-03-01'
deciders:
- Project team
related:
- ADR-126 (plugin template)
- ADR-128 (hub assembly)
- ADR-130 (action dispatch)
- ADR-162 (dispatch modes)
- ADR-177 (build validation)
- ADR-201 (dissolve core bundle)
hub: null
tags:
- block
- based
- page
- builder
superseded_by: null
---

# ADR-190: Block-Based Page Builder

> **Note (ADR-201)**: page-builder was moved from `plugins/core/skills/page-builder/` to `plugins/ai/skills/page-builder/` per ADR-201. Path references below reflect the original location at time of writing.

## Context

Creating new dashboard pages requires manually writing plugin files (augur.yaml, page.tsx, API routes), running mount-plugins, and understanding the full plugin lifecycle. This is a multi-step, developer-only workflow that takes 10-15 minutes for a simple page.

Users want to compose pages visually from reusable blocks — similar to Notion's block-based editor — where blocks map to MCP tools and plugin components. The block ecosystem should scale with the MCP ecosystem: any MCP server can contribute blocks without Augur defining them individually.

Currently:
- `SectionDefinition` types exist in `plugin-schema/types.ts` (metrics-grid, data-table, chart, timeline, form, markdown, custom) but are not used as composable blocks
- `EditableMasonryGrid` handles resizable block layout with localStorage persistence
- `PageActionButtons` discovers buttons via `GET /api/registry` — extensible without hardcoding
- `/api/plugins/rebuild/route.ts` already invokes mount-plugins programmatically via SSE pipeline
- `contributions.blocks` does not exist in the `ContributionBlock` interface — needs to be added

## Decision

Build a page builder as a plugin skill at `plugins/core/skills/page-builder/` with four layers: builder canvas UI, block registry, block renderers, and page codegen.

### 1. Block Manifest Standard

Define a universal block descriptor used by both MCP tools and plugin contributions:

```yaml
id: string              # unique identifier
name: string            # display name
icon: string            # Lucide icon name
category: string        # content | data | communication | automation | custom
render: string          # form | table | card | chart | markdown | timeline | custom
source: string          # mcp | plugin

# MCP-backed:
mcp_tool: string
mcp_server: string

# Plugin-backed:
component: string       # relative path to React component

# Props schema (JSON Schema subset):
props:
  - name: string
    type: string        # string | number | boolean | file-path | select
    default: any
    required: boolean
    options: string[]
```

**Action**: Add `blocks?: BlockDefinition[]` to `ContributionBlock` in `src/dashboard/lib/plugin-schema/types.ts`

### 2. Block Discovery API

`GET /api/ai/page-builder/blocks` scans two sources:

1. **MCP tools** — query the MCP tool registry for tools with `block` metadata in their registration, map to block manifest shape
2. **Plugin augur.yaml** — scan all `augur.yaml` files for `contributions.blocks[]` entries, resolve component paths relative to plugin

Merge, deduplicate by `id`, return catalog grouped by `category`.

**Files created**:
- `plugins/core/skills/page-builder/augur/api/page-builder/blocks/route.ts`

### 3. Block Renderers

`BlockRenderer` component dispatches based on block source and render type:

- **Plugin blocks**: dynamic import component from path in manifest, pass props
- **MCP `render: "form"`**: `AutoForm` generates inputs from MCP tool's JSON Schema (`{ type: "string" }` → `<Input />`, `{ enum }` → `<Select />`, etc.), submit calls invoke API
- **MCP `render: "table"`**: call tool on mount, render response as sortable DataTable
- **MCP `render: "card"`**: call tool on mount, render as StatCard grid
- **MCP `render: "custom"`**: fallback to tool description + raw JSON output

All blocks wrap in `GlassCard` with consistent header (title + icon).

**Starter blocks** (6 shipped with v1):

| Block | Source | Render |
|-------|--------|--------|
| `quick-notes` | plugin | markdown |
| `data-table` | plugin | table |
| `stat-cards` | plugin | card |
| `chart` | plugin | chart |
| `action-buttons` | plugin | card |
| `mcp-tool-form` | mcp | form |

**Files created**:
- `plugins/core/skills/page-builder/augur/blocks/BlockRenderer.tsx`
- `plugins/core/skills/page-builder/augur/blocks/AutoForm.tsx`
- `plugins/core/skills/page-builder/augur/blocks/QuickNotes.tsx`
- `plugins/core/skills/page-builder/augur/blocks/DataTable.tsx`
- `plugins/core/skills/page-builder/augur/blocks/StatCards.tsx`
- `plugins/core/skills/page-builder/augur/blocks/ChartBlock.tsx`
- `plugins/core/skills/page-builder/augur/blocks/ActionButtons.tsx`

### 4. Builder Canvas UI

Full-screen page at `/{hub}/builder` (dev mode only):

- **Left sidebar**: Block palette grouped by category, click to add
- **Right canvas**: `EditableMasonryGrid` with live block previews using real components and sample data
- **Top bar**: Page metadata (name, hub selector, icon picker), back button, save button
- **Block config**: Gear icon on each block opens inline props panel using props schema
- **Block actions**: Drag handle to reorder, X to remove
- **Status bar**: Block count, target hub, save state

Entry point: "+" button added to `PageActionButtons` via a new action in the page-builder skill's actions YAML. Only visible in dev mode (action bar itself is dev-mode-only).

**Files created**:
- `plugins/core/skills/page-builder/augur/dashboard/layout.tsx` (passthrough)
- `plugins/core/skills/page-builder/augur/dashboard/page.tsx` (recent pages list)
- `plugins/core/skills/page-builder/augur/dashboard/builder/page.tsx` (canvas)

### 5. Page Codegen Pipeline

`POST /api/ai/page-builder/save` with `PageBuilderState` body:

```typescript
interface PageBuilderState {
  name: string;
  slug: string;
  hub: string;
  icon: string;
  targetSkill: string;
  blocks: BlockInstance[];
}

interface BlockInstance {
  id: string;
  blockType: string;
  props: Record<string, any>;
  layout: { col: number; row: number; w: number; h: number };
}
```

Pipeline steps:
1. **Validate** — name unique within hub, at least 1 block, dev mode check
2. **Generate page.tsx** — string template imports BlockRenderer per block, wraps in EditableMasonryGrid, bakes props into component tree
3. **Generate API route** (if MCP blocks present) — POST handler proxying MCP tool calls via augur_mcp
4. **Update augur.yaml** — append `contributions.pages[]` entry with next available order value
5. **Run mount-plugins** — invoke `node scripts/dist/mount-plugins.mjs` (same pattern as `/api/plugins/rebuild`)
6. **Return success** — `{ success, pageUrl, filesCreated[] }`, HMR picks up changes

**Files created**:
- `plugins/core/skills/page-builder/augur/api/page-builder/save/route.ts`
- `plugins/core/skills/page-builder/augur/api/page-builder/pages/route.ts`
- `plugins/core/skills/page-builder/augur/lib/page-builder/types.ts`
- `plugins/core/skills/page-builder/augur/lib/page-builder/registry.ts`
- `plugins/core/skills/page-builder/augur/lib/page-builder/codegen.ts`
- `plugins/core/skills/page-builder/augur/lib/page-builder/templates/page-template.ts`
- `plugins/core/skills/page-builder/augur/lib/page-builder/templates/route-template.ts`

### 6. Skill Manifest

```yaml
# plugins/core/skills/page-builder/augur.yaml
name: page-builder
bundle: core
hub:
  id: ai
  owner: false
contributions:
  pages:
    - id: page-builder
      order: 920          # overflow tab in AI hub
      title: Page Builder
      icon: LayoutDashboard
      purpose: Visual page builder for composing dashboard pages from blocks
      keywords: [builder, blocks, pages, compose]
      state: dev
```

## Consequences

**Positive**:
- Page creation drops from 10-15 minutes to under 1 minute
- Any MCP tool becomes a block automatically via AutoForm
- Plugin authors can contribute custom blocks via `contributions.blocks`
- Generated pages are real plugin files — fully editable, versionable, mountable
- Extensible without Augur core changes (new blocks = new MCP tools or plugins)

**Negative**:
- Codegen templates need maintenance as component APIs evolve
- `ContributionBlock` interface gains a new field (`blocks`) — all augur.yaml consumers must handle it gracefully
- Generated pages may drift from templates if hand-edited after generation

**Neutral**:
- Existing pages are unaffected — builder creates new pages alongside them
- Builder is dev-mode-only — operation mode users never see it

## Implementation Order

```
Phase 1: Foundation (types + schema)
├── Step 1: Add BlockDefinition to ContributionBlock in types.ts
├── Step 2: Create page-builder skill scaffold (augur.yaml, SKILL.md, layout.tsx)
└── Step 3: Create TypeScript types (PageBuilderState, BlockInstance, BlockManifest)

Phase 2: Block System (renderers + discovery) — depends on Phase 1
├── Step 4: Build 6 starter block components (QuickNotes, DataTable, StatCards, ChartBlock, ActionButtons, AutoForm)
├── Step 5: Build BlockRenderer dispatcher component
└── Step 6: Build block discovery API route (GET /api/ai/page-builder/blocks)

Phase 3: Builder UI — depends on Phase 2
├── Step 7: Build BlockPalette sidebar component
├── Step 8: Build BlockConfigPanel inline props editor
├── Step 9: Build BuilderCanvas full-screen page
└── Step 10: Build PageMetadataForm (name, hub, icon)

Phase 4: Codegen Pipeline — depends on Phase 2
├── Step 11: Build page.tsx string template
├── Step 12: Build API route string template
├── Step 13: Build codegen engine (validate, generate, update augur.yaml, mount)
└── Step 14: Build save API route (POST /api/ai/page-builder/save)

Phase 5: Integration — depends on Phases 3 + 4
├── Step 15: Add "+" button entry point to PageActionButtons
├── Step 16: Build pages list API route (GET/DELETE /api/ai/page-builder/pages)
└── Step 17: Build landing page (recent pages list with edit/delete)

Phase 6: Verification — depends on Phase 5
├── Step 18: Mount plugins and verify builder page loads
├── Step 19: End-to-end test: create page via builder, verify generated files, verify page renders
└── Step 20: TypeScript compilation check (tsc --noEmit)
```

## Alternatives Considered

### Runtime YAML pages (no codegen)

A single `DynamicPage` component reads a YAML spec and renders blocks at runtime. No code generation.

**Rejected** because: generated files are less flexible, users can't customize beyond what the YAML schema allows, breaks the "real plugin files" design principle, and adds a runtime interpretation layer that must stay in sync with all block types.

### AI-assisted builder (LLM generates layout)

User describes what they want in natural language, AI generates the block layout.

**Rejected for v1** because: dashboard cannot call LLM APIs directly (rule #8), would require IDE dispatch adding significant complexity. Better as a v2 enhancement once the manual builder is proven.

### JSON Schema blocks (web standard)

Blocks defined by JSON Schema, framework-agnostic spec portable outside Augur.

**Rejected** because: less integrated with the existing plugin system, requires a translation layer between JSON Schema and React components, and portability outside Augur is not a near-term need.

## References

- Design doc: `docs/plans/2026-03-01-page-builder-design.md`
- ADR-126: Generic plugin template (augur.yaml + contributions)
- ADR-128: Hub assembly pipeline
- ADR-130: Action dispatch modes
- ADR-177: Build validation and page validation
- `src/dashboard/components/EditableMasonryGrid.tsx` — block layout primitive
- `src/dashboard/components/PageActionButtons.tsx` — dev-mode action bar
- `src/dashboard/lib/plugin-schema/types.ts` — SectionDefinition, ContributionBlock
- `src/dashboard/app/api/plugins/rebuild/route.ts` — programmatic mount-plugins invocation

## Impact Manifest

```yaml
impact:
  apis_changed:
    - function: ContributionBlock
      module: src/dashboard/lib/plugin-schema/types.ts
      breaking: false  # additive — new optional blocks? field
  files_affected:
    - glob: "src/dashboard/lib/plugin-schema/types.ts"
    - glob: "src/dashboard/components/PageActionButtons.tsx"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-190: Block-Based Page Builder**.

Read the full ADR: `docs/decisions/ADR-190-page-builder.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-190-page-builder", description="Implementing ADR-190: Block-Based Page Builder")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Agent(subagent_type="general-purpose", team_name="adr-190-page-builder", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-190 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-190-page-builder`

#### Phase 1: Foundation
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Add `blocks?: BlockDefinition[]` to `ContributionBlock` interface and define `BlockDefinition` type | `src/dashboard/lib/plugin-schema/types.ts` |
| 1.2 | developer | low | Create page-builder skill scaffold: augur.yaml (hub: ai, owner: false, order: 920), SKILL.md, passthrough layout.tsx | `plugins/core/skills/page-builder/augur.yaml`, `plugins/core/skills/page-builder/SKILL.md`, `plugins/core/skills/page-builder/augur/dashboard/layout.tsx` |
| 1.3 | developer | medium | Create TypeScript types: PageBuilderState, BlockInstance, BlockManifest interfaces | `plugins/core/skills/page-builder/augur/lib/page-builder/types.ts` |

#### Phase 2: Block System
**Strategy**: PARALLEL (steps 2.1 and 2.2 parallel, 2.3 after both)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Build 6 starter block components: QuickNotes (markdown textarea with localStorage), DataTable (sortable from YAML/JSON), StatCards (metrics grid), ChartBlock (line/bar/pie), ActionButtons (action grid from augur.yaml), AutoForm (generates form from MCP tool JSON Schema) | `plugins/core/skills/page-builder/augur/blocks/QuickNotes.tsx`, `DataTable.tsx`, `StatCards.tsx`, `ChartBlock.tsx`, `ActionButtons.tsx`, `AutoForm.tsx` |
| 2.2 | developer | medium | Build block discovery API: scan MCP tool registrations for block metadata + scan augur.yaml contributions.blocks, merge and deduplicate, return grouped by category | `plugins/core/skills/page-builder/augur/api/page-builder/blocks/route.ts`, `plugins/core/skills/page-builder/augur/lib/page-builder/registry.ts` |
| 2.3 | developer | medium | Build BlockRenderer dispatcher: dynamic import for plugin blocks, AutoForm/DataTable/StatCard dispatch for MCP blocks based on render type, GlassCard wrapper | `plugins/core/skills/page-builder/augur/blocks/BlockRenderer.tsx` |

#### Phase 3: Builder UI
**Strategy**: PARALLEL (steps 3.1-3.3 parallel, 3.4 after all)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Build BlockPalette sidebar: grouped by category, click-to-add, search/filter, block preview on hover | `plugins/core/skills/page-builder/augur/dashboard/builder/components/BlockPalette.tsx` |
| 3.2 | frontend | medium | Build BlockConfigPanel: inline props editor using props schema, renders Input/Select/Checkbox based on prop type | `plugins/core/skills/page-builder/augur/dashboard/builder/components/BlockConfigPanel.tsx` |
| 3.3 | frontend | medium | Build PageMetadataForm: name input (auto-generates slug), hub selector dropdown, icon picker | `plugins/core/skills/page-builder/augur/dashboard/builder/components/PageMetadataForm.tsx` |
| 3.4 | frontend | high | Build BuilderCanvas page: full-screen layout with PageMetadataForm top, BlockPalette left, EditableMasonryGrid right with BlockRenderer children, save button triggering codegen API, status bar | `plugins/core/skills/page-builder/augur/dashboard/builder/page.tsx` |

#### Phase 4: Codegen Pipeline
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Build page.tsx string template: imports BlockRenderer per block, wraps in EditableMasonryGrid, bakes props | `plugins/core/skills/page-builder/augur/lib/page-builder/templates/page-template.ts` |
| 4.2 | developer | medium | Build API route string template: POST handler proxying MCP tool calls, routes by block type | `plugins/core/skills/page-builder/augur/lib/page-builder/templates/route-template.ts` |
| 4.3 | developer | high | Build codegen engine: validate (name unique, 1+ blocks, dev mode), generate page.tsx + route.ts, update augur.yaml contributions.pages, invoke mount-plugins via spawn | `plugins/core/skills/page-builder/augur/lib/page-builder/codegen.ts` |
| 4.4 | developer | medium | Build save API route: POST handler calling codegen, returns { success, pageUrl, filesCreated } | `plugins/core/skills/page-builder/augur/api/page-builder/save/route.ts` |

#### Phase 5: Integration
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Add "+" button entry point: create action YAML for page-builder that renders in PageActionButtons, navigates to /{hub}/builder | `plugins/core/skills/page-builder/augur/data/actions/new-page.yaml` |
| 5.2 | developer | medium | Build pages list API route: GET returns created pages with metadata, DELETE removes page files and re-mounts | `plugins/core/skills/page-builder/augur/api/page-builder/pages/route.ts` |
| 5.3 | developer | medium | Build landing page: list of created pages with edit/delete actions, empty state with "Create your first page" CTA | `plugins/core/skills/page-builder/augur/dashboard/page.tsx` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 6.1 | validator | low | Run mount-plugins and verify builder page loads at /ai/page-builder |
| 6.2 | validator | medium | End-to-end: create a page via builder save API, verify generated files exist, verify page renders |
| 6.3 | validator | low | TypeScript compilation check: `npx tsc --noEmit` |
| 6.4 | architect | low | Verify ADR intent matches implementation: block discovery works, codegen produces valid files, builder UI loads |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`npm run build`)
- [ ] No orphaned files or broken references
- [ ] TypeScript compiles cleanly
- [ ] Builder page accessible at /ai/page-builder in dev mode
- [ ] Block discovery returns starter blocks
- [ ] Page creation produces valid plugin files that mount successfully
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-190-page-builder.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
