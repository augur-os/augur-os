# Form Blocks, Custom Blocks, and Conditional Visibility

**Date:** 2026-03-23
**Status:** Approved
**Context:** ADR-491 introduced YAML-driven config pages with 21 block types. ~53 TSX pages remain unmigrated because blocks lack form/mutation support and an escape hatch for complex state machines.

## Problem

The block system handles data display, filtering, search, and simple row actions. But most unmigrated TSX pages need:

1. **Modal forms** — actions that collect user input before dispatching (edit dialogs, import modals, confirmation dialogs)
2. **Custom components** — pages with complex state machines (multi-step workflows, real-time device control, quiz engines) that can't be expressed declaratively
3. **Quick-add dispatch** — the existing quick-add UI renders but doesn't dispatch to MCP (TODO_BUG)
4. **Conditional visibility** — blocks that should only appear when another block has data

## Decisions

### D1: No standalone form block

Forms in this codebase are never standalone — they're always attached to an action on an existing block (row action opens edit modal, action-bar button opens import modal, data-table has quick-add). Instead of a new `form` block type, we extend existing blocks with declarative field configs and add a generic modal wrapper.

### D2: Modal fields are inline in action config

Field definitions live directly on the action that triggers them (in `row_actions` or action-bar `actions`), not in a separate modal definition section. Most modals are page-specific and tightly coupled to their triggering action.

### D3: Custom blocks are registry-based

Skills register custom components in SKILL.md frontmatter. The generate-tab-registry script builds a lookup map. This is consistent with how standard blocks are already discovered.

### D4: Auto-refetch with optional override

On successful modal form dispatch, the triggering block auto-refetches its data. An optional `refetch` array on the action targets additional blocks by ID.

## Design

### 1. Modal Form System

Extend `RowAction` and action-bar actions with an optional `fields` array. When an action has `fields`, clicking it opens a modal form instead of dispatching immediately.

**YAML syntax in data-table row_actions:**

```yaml
row_actions:
  - id: edit-job
    icon: Pencil
    label: Edit
    dispatch: fire
    mcp_tool: update-career-job
    payload_fields: [id]
    fields:
      - name: title
        type: text
        label: Job Title
        required: true
      - name: status
        type: select
        label: Status
        options: [inbox, active, offer, rejected, archive]
      - name: notes
        type: textarea
        label: Notes
```

**YAML syntax in action-bar actions:**

```yaml
actions:
  - id: import-data
    label: Import CSV
    icon: Upload
    dispatch: fire
    mcp_tool: import-finance-data
    fields:
      - name: file
        type: file
        label: Select File
        accept: [.csv, .xlsx]
        required: true
      - name: import_type
        type: radio
        label: Import Type
        options: [transactions, accounts]
        defaultValue: transactions
```

**Options shorthand:** YAML bare string arrays (e.g., `options: [inbox, active]`) are normalized to `SelectOption[]` at parse time — `"inbox"` becomes `{ value: "inbox", label: "inbox" }`. Full `{value, label}` objects are also supported for display labels that differ from values.

**ActionBarBlock data flow fix:** Currently `ActionBarBlock` reads actions exclusively from MCP data (`useBlockData` response), ignoring config-declared actions. This must be changed: the component reads actions from `config.actions` first (YAML-declared), with MCP-fetched data as a secondary source merged in. When both exist, config actions take precedence (allows YAML pages to override or extend MCP-provided actions). When neither exists, the block renders empty.

**Field type:** Reuses and extends the existing `FormField` interface from `lib/plugin-schema/types.ts`. Supported types: `text`, `textarea`, `number`, `date`, `datetime`, `select`, `multiselect`, `checkbox`, `radio`, `file`, `toggle`. The `file` and `toggle` types are new additions; `date`, `datetime`, and `multiselect` are inherited from the existing interface.

**Validation:** Nested under `validation` to match the existing `FormField` structure:
- `required` — field-level (not nested), field must have a value
- `validation.min` / `validation.max` — number bounds
- `validation.minLength` / `validation.maxLength` — text length bounds
- `validation.pattern` — regex validation
- `validation.message` — custom error message
- `accept` — file-level (not nested), file type filter (array of extensions)
- `confirmText` — action-level (not field-level), dangerous action guard; user must type exact string to enable submit. Implemented in `ActionFormModal.tsx` as a separate input below the form fields that disables the submit button until the string matches.

**Refetch:** On successful dispatch, auto-refetch the triggering block's data. Optional `refetch: [block-id]` array on the action to also invalidate other blocks on the page. Blocks targeted by `refetch` must have an explicit `id` field (see Section 4).

**Component:** A single generic `ActionFormModal.tsx` in `apps/dashboard/components/blocks/`. Receives field definitions + action config, renders the form with shadcn/ui components, validates inputs, dispatches via `useActionRunner`, shows loading state, closes and triggers refetch on success.

### 2. Custom Block Type

A new `custom` block type that loads a skill-provided TSX component by registered ID. This is the escape hatch for Tier C pages (System Cleanup, Home Automation, Quiz) that have complex state machines.

**Registration in SKILL.md:**

```yaml
x-augur-config:
  contributions:
    custom_blocks:
      - id: cleanup-workflow
        component: CleanupWorkflow
        description: Multi-step system cleanup with scan, preview, and execute
      - id: light-control
        component: LightControlPanel
        description: Smart home light toggle and brightness control
```

**File convention:** Component must exist at `skills/dashboard/components/{Component}.tsx` (the `@skill/` alias maps to `skills/dashboard/`, so all custom block components must live in the shared dashboard skill directory).

**Registry generation:** `generate-tab-registry.ts` scans SKILL.md `custom_blocks` entries, validates the component file exists at the convention path, and emits `generated-custom-block-registry.ts` mapping IDs to `dynamic(() => import('@skill/{skill}/components/{Component}'))`.

**YAML page usage:** Uses the existing `component` field on `BlockConfig` (already typed), not a new `custom_block` field. The `component` value references a registered custom block ID.

```yaml
blocks:
  - type: custom
    component: cleanup-workflow
    size: full
    title: System Cleanup
    icon: Trash2
    show_dangerous: true
    max_categories: 10
```

**Component contract:** Custom block components receive the existing `CustomBlockProps` interface (`skillId`, `config: BlockConfig`). The `config` object contains all YAML fields after destructuring known keys — extra fields like `show_dangerous` and `max_categories` flow through via the `[key: string]: unknown` index signature. Components can use all dashboard hooks (`useActionRunner`, `useMcpQuery`, `useBlockData`) freely. If the registered component file doesn't exist at runtime, the block resolver renders an error card with the missing component path.

**Boundary:** Custom blocks are the escape hatch, not the default. If a page can be expressed with standard blocks + modal forms, it should be.

### 3. Quick-Add Dispatch Fix

Wire the existing `handleQuickAddSubmit` callback in `DataTableBlock.tsx` to `useActionRunner`. The `quick_add.action` field already exists in the `BlockQuickAdd` type — it just needs the dispatch call.

```typescript
const handleQuickAddSubmit = useCallback(async (values: Record<string, string>) => {
  if (!quickAdd?.action) return;
  await runAction({
    id: quickAdd.action,
    label: "Add item",
    dispatch: "fire",
    page: window.location.pathname,
    args: values,
  });
  // Auto-refetch block data on success
}, [quickAdd?.action, runAction]);
```

### 4. Conditional Block Visibility

Add optional `id` and `showIf` fields to `BlockConfig`. The `id` field is also used by the `refetch` system (Section 1). `showIf` is evaluated client-side against page-level data context.

```yaml
blocks:
  - type: stat-grid
    id: rebuild-stats
    mcp_tool: get-index-stats
    size: half

  - type: data-table
    title: Search Results
    mcp_tool: search-index
    size: full
    showIf: { blockHasData: rebuild-stats }
```

**Expression types:**
- `blockHasData: block-id` — show when referenced block returned non-empty data. "Has data" means the MCP tool returned successfully AND the result is non-empty (non-null, non-empty array, non-empty object). An empty array `[]` counts as no data.
- `configFlag: flag-name` — show when a page-level YAML field is truthy. The flag name references a top-level field in the page YAML (e.g., `dev_mode: true` at page root).

Two expression types cover the real use cases. No general-purpose expression engine.

**Implementation:** `ConfigPage.tsx` provides a `BlockDataMap` context. `FlowBlockRenderer` reports data status via the context when a block has an `id`, and evaluates `showIf` against the context map (for `blockHasData`) or page-level flags passed as a prop (for `configFlag`). When `showIf` fails, `FlowBlockRenderer` returns `null`. The `sizes` and `children` arrays in `ConfigPage` are filtered together so `FlowLayout` never sees gaps from hidden blocks. The `showIf` and `id` fields are destructured out in `FlowBlockRenderer` so they don't leak into block component config.

## File Changes

| File | Change |
|------|--------|
| `apps/dashboard/lib/blocks/flow-types.ts` | Extend `FormField` from `plugin-schema/types.ts` with `file` and `toggle` types; add `ActionFormConfig` type; extend `RowAction` and action-bar action types with `fields`, `refetch`; add `id`, `showIf` to `BlockConfig`; add `CustomBlockManifest` type |
| `apps/dashboard/components/blocks/ActionFormModal.tsx` | **New.** Generic modal form renderer — field rendering, validation, dispatch via useActionRunner, loading state, refetch |
| `apps/dashboard/components/blocks/types/ActionBarBlock.tsx` | Detect `fields` on action, open `ActionFormModal` instead of direct dispatch |
| `apps/dashboard/components/blocks/types/DataTableBlock.tsx` | Wire `handleQuickAddSubmit` to `useActionRunner`; detect `fields` on row action, open `ActionFormModal` |
| `apps/dashboard/components/blocks/RowActionsCell.tsx` | Pass `fields` through; open modal when action has fields |
| `apps/dashboard/components/plugin/ConfigPage.tsx` | Track `blockDataMap` for conditional visibility; pass to `FlowBlockRenderer` |
| `apps/dashboard/lib/blocks/block-resolver.ts` | Add `custom` to block type map, resolve from generated custom block registry |
| `apps/dashboard/scripts/generate-tab-registry.ts` | Scan SKILL.md `custom_blocks`, validate file paths, emit `generated-custom-block-registry.ts` |
| `apps/dashboard/lib/blocks/generated-custom-block-registry.ts` | **New (generated).** Custom block ID to dynamic import map |

**Not changed:** No new API routes (forms dispatch through existing `useActionRunner` -> `/api/actions/run`). No Python changes. No MCP tool changes.

## Migration Impact

| Tier | Pages | Unblocked By |
|------|-------|-------------|
| A (easy) | ~20 | Modal form system + quick-add fix |
| B (medium) | ~20 | Modal forms + conditional visibility |
| C (hard) | ~13 | Custom block type |

Total: all 53 remaining TSX pages become migratable.
