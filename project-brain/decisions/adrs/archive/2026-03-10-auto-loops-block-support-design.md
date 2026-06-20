---
title: Auto Loops Block Support — Design Spec
date: 2026-03-10
---

# Auto Loops Block Support — Design Spec

**Date**: 2026-03-10
**Related**: ADR-406 (Block System UI)
**Status**: Approved

## Context

ADR-406 replaces the page-based hub system with a Notion-like block system. Auto loops currently validate pages, page mounts, page routes, and tab ordering — all concepts that shift to blocks, views, and MCP data sources. Loops must support both pages and blocks during the transition period, then drop page support after migration completes.

## Decision

Approach B (minus auto-tabs retirement): Add block validation alongside existing page validation in 5 loops, create 2 new block-specific loops, keep auto-tabs as-is.

## Scope

### Refactored Loops (5)

#### auto-page-mounts (hardening, ~80 LOC)

Add second scan pass for `contributions.blocks[]` in augur.yaml files. For each block, validate:

- `expandTo` route has a corresponding `page.tsx` (if specified)
- Block `type` is one of the 14 canonical types

This loop checks **structural existence** only (does the declared thing exist on disk?). Deep data-pipeline validation (MCP tools, API routes) is handled by `auto-block-wiring`.

Existing `contributions.pages[]` validation unchanged. Report format adds a "Blocks" section.

**File**: `plugins/admin/skills/auto-page-mounts/scripts/page_mounts.py`

#### auto-stale-refs (hardening, ~100 LOC)

Tier 1 scanner: add parallel check for block-scoped actions. If an action references a block (via block ID or block route), validate that block exists in the skill's `contributions.blocks[]`. Tier 3 (generic file path staling) unchanged.

**File**: `plugins/admin/skills/auto-stale-refs/` (SKILL.md-driven, no scanner script yet)

#### auto-dead-ui (hardening, ~150 LOC)

Extend `_find_page_files()` to discover block component files. The block registry (`generated-block-registry.ts`) maps block IDs to manifests with a `type` field; component resolution lives in `block-resolver.ts` which maps the 14 block types to React components at `src/dashboard/components/blocks/types/`. Use the resolver's type-to-component mapping to locate block component files for scanning. Apply d1-d3 checks (empty handlers, broken links, missing action IDs) to block components.

**File**: `plugins/dev/skills/auto-dead-ui/scripts/dead_ui_ops.py`

#### auto-dead-wiring (hardening, ~140 LOC)

- d0: Add block counting alongside page counting
- d1: Validate each declared block has a matching component in block registry
- d4: Add block data chain: block -> dataSource -> API/MCP -> data

**File**: `plugins/dev/skills/auto-dead-wiring/scripts/dead_wiring_ops.py`

#### auto-plugin-lint (hardening, ~40 LOC)

Add block structural check: if a skill declares `contributions.blocks[]`, verify the block type is one of the 14 canonical types from ADR-406: stat-card, stat-grid, data-list, data-table, action-bar, card-grid, chart, markdown, calendar, activity-feed, notes, embed, ops-board, progress.

**File**: `plugins/admin/skills/auto-plugin-lint/scripts/plugin_lint.py`

### New Loops (2)

#### auto-block-wiring (hardening, tier 1 nightly, ~120 LOC)

Validate that every declared block has a working data pipeline.

**Checks**:
- Every `contributions.blocks[]` entry with a data-bearing type has a valid `dataSource` (either `apiRoute` or `mcpTool`, not both missing). Client-only block types (`markdown`, `notes`) are exempt — `dataSource` is optional for these.
- Referenced `apiRoute` resolves to an existing `route.ts` file
- Referenced `mcpTool` exists in the MCP tool registry
- If `expandTo` is set, the target route exists

**Differentiation from auto-page-mounts**: auto-page-mounts checks structural existence (does the declared block type exist, does `expandTo` have a page?). auto-block-wiring checks the **data pipeline** (does the MCP tool exist, does the API route resolve?).

**Output**: `docs/generated/hardening/block-wiring-{date}.md`
**Location**: `plugins/admin/skills/auto-block-wiring/`
**Protocol**: scan-fix

#### auto-view-schema (hardening, tier 2 nightly, ~100 LOC)

Validate user-created view YAML files in `runtime/views/`.

**Checks**:
- Each view YAML has required fields (`title`, `blocks[]`, `layout.columns`, `layout.rowHeight`)
- Each block instance references a block ID that exists in some skill's `contributions.blocks[]`
- Grid positions don't overlap (column/row conflicts)
- No orphaned views referencing blocks from uninstalled skills

**Output**: `docs/generated/hardening/view-schema-{date}.md`
**Location**: `plugins/admin/skills/auto-view-schema/`
**Protocol**: scan-fix

### Unchanged Loops

- **auto-tabs**: Kept as-is (still in use)
- **auto-code-health**: No changes needed (`tsc --noEmit` applies to all TypeScript)

## Budget Impact

Hardening loop budget: 12. Current commands: 9. After adding 2 new: 11. Within budget.

## Effort Summary

| Component | LOC | Type |
|-----------|-----|------|
| auto-page-mounts | ~80 | refactor |
| auto-stale-refs | ~100 | refactor |
| auto-dead-ui | ~150 | refactor |
| auto-dead-wiring | ~140 | refactor |
| auto-plugin-lint | ~40 | refactor |
| auto-block-wiring | ~120 | new skill |
| auto-view-schema | ~100 | new skill |
| **Total** | **~730** | |

## Post-Migration Cleanup (future)

Once all pages are migrated to blocks, remove page-validation branches from the 5 refactored loops (~200 LOC deletion). Not part of this work.
