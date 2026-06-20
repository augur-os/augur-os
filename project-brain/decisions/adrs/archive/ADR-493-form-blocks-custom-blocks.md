---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related: [ADR-491, ADR-490, ADR-274]
hub: null
tags: [dashboard, blocks, forms, modal, custom-blocks, conditional-visibility]
superseded_by: null
---

# ADR-493: Form Blocks, Custom Blocks, and Conditional Visibility

## Context

ADR-491 introduced YAML-driven config pages with 21 block types. ~53 TSX pages remained unmigrated because blocks lacked form/mutation support and an escape hatch for complex state machines. The block system handled data display, filtering, search, and simple row actions, but most unmigrated pages needed modal forms (edit dialogs, import modals, confirmation dialogs), custom components for complex state machines, working quick-add dispatch (existing TODO_BUG), and conditional block visibility.

## Decision

Extend existing blocks with declarative form capabilities rather than creating standalone form block types. Four changes:

### D1: Modal Form System via Inline Fields

Extend `RowAction` and action-bar actions with an optional `fields` array (reusing `FormField` from `lib/plugin-schema/types.ts`, extended with `file` and `toggle` types). When an action has `fields`, clicking it opens a generic `ActionFormModal` instead of dispatching immediately. Field definitions live inline on the triggering action — no separate modal registry. `ActionBarBlock` refactored to read `config.actions` first (YAML-declared), with MCP-fetched data as fallback.

### D2: Custom Block Type with SKILL.md Registry

A `custom` block type loads skill-provided TSX components by registered ID. Skills register components in SKILL.md frontmatter (`x-augur-config.contributions.custom_blocks`). `generate-tab-registry.ts` builds the lookup map. Components must live in `skills/dashboard/components/` (the `@skill/` alias target). This is the escape hatch for pages with complex state machines (system cleanup, home automation, quiz).

### D3: Quick-Add Dispatch Fix

Wired the existing `handleQuickAddSubmit` in `DataTableBlock.tsx` to `useActionRunner`. The `quick_add.action` field already existed — just needed the dispatch call.

### D4: Conditional Block Visibility (showIf)

Added `id` and `showIf` fields to `BlockConfig`. `showIf` expressions: `blockHasData` (show when referenced block has non-empty data) and `configFlag` (show when page-level YAML flag is truthy). Implemented via `BlockDataMap` React context — blocks report data status, and blocks with `showIf` return null when condition fails. `FlowLayout` modified to skip null children.

## Consequences

**Positive:**
- All 53 remaining TSX pages are now migratable to YAML (Tier A: ~20 via modal forms, Tier B: ~20 via forms + showIf, Tier C: ~13 via custom blocks)
- No new API routes — forms dispatch through existing `useActionRunner` → `/api/actions/run`
- Quick-add actually works now (TODO_BUG resolved)
- Custom blocks provide a clean escape hatch without undermining YAML page goals

**Negative:**
- Custom blocks in `skills/dashboard/components/` are a shared location — could become a dumping ground if not bounded
- `showIf` context causes a re-render cycle (blocks appear after data loads, not simultaneously)

**Neutral:**
- No Python or MCP tool changes required

## Alternatives Considered

1. **Standalone `form` block type** — Rejected: forms in this codebase are never standalone; they're always action-triggered
2. **Page-level modal definitions** — Rejected: most modals are tightly coupled to their triggering action; indirection adds complexity without reuse benefit
3. **Convention-based custom block resolution** (no registry) — Rejected: explicit SKILL.md registration is consistent with existing block discovery and prevents phantom imports

## References

- Design spec: `docs/superpowers/specs/2026-03-23-form-blocks-custom-blocks-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-23-form-blocks-custom-blocks.md`
- ADR-491: Unified Config-Driven Pages
- ADR-490: Framework Migration (@/ vs @skill/)
- ADR-274: Block System Feature Tiers
