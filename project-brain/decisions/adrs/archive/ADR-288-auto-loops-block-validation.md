---
status: Implemented
date: '2026-03-10'
deciders: []
related:
- ADR-406 (Block System UI)
- ADR-176 (Adaptive Loop Engine)
- ADR-200 (Ops Protocol)
hub: null
tags:
- auto
- loops
- block
- validation
- adr
superseded_by: null
---

# ADR-288: Auto Loops Block Validation (ADR-406 Support)

## Context

ADR-406 replaces the page-based hub system with a Notion-like block system. The adaptive loop engine (ADR-176) currently runs 33 auto-commands across 8 categories. Seven of these commands validate page-centric concepts — page mounts, page routes, tab ordering, UI wiring, and stale references — that shift to blocks, views, and MCP data sources under ADR-406.

During the transition period, both pages and blocks will coexist. The loops must validate both. After migration completes, page validation branches can be removed.

## Decision

Add block validation alongside existing page validation in 5 loops and create 2 new block-specific loops. Keep auto-tabs as-is (still in use).

### Refactored Loops (5)

| Loop | Change | Coupling |
|------|--------|----------|
| **auto-page-mounts** | Add `contributions.blocks[]` scan — validate `expandTo` routes exist, block types are canonical | High (100%) |
| **auto-stale-refs** | Add block-scoped action validation — if action references a `block:` field, verify block ID exists | Medium (50%) |
| **auto-dead-ui** | Extend `_find_page_files()` to discover block component files at `src/dashboard/components/blocks/types/*.tsx` | High (90%) |
| **auto-dead-wiring** | Add block counting (d0), block registry validation (d1), block data chain (d4) | High (85%) |
| **auto-plugin-lint** | Validate `contributions.blocks[].type` against 14 canonical block types | Low (15%) |

### New Loops (2)

**auto-block-wiring** (hardening, tier 1, nightly): Validates block data pipelines — every data-bearing block has a `dataSource` with a valid `apiRoute` or `mcpTool`. Client-only types (`markdown`, `notes`) are exempt.

**auto-view-schema** (hardening, tier 2, nightly): Validates `runtime/views/*.yaml` files — required fields (`title`, `blocks`, `layout.columns`, `layout.rowHeight`), block reference integrity, grid overlap detection.

### Differentiation

- **auto-page-mounts** checks *structural existence* (does the declared thing exist on disk?)
- **auto-block-wiring** checks the *data pipeline* (does the MCP tool exist? does the API route resolve?)
- No overlap between them.

### Unchanged

- **auto-tabs**: Kept as-is (still in use)
- **auto-code-health**: No changes needed (`tsc --noEmit` applies to all TypeScript)

## Budget Impact

Hardening loop budget: 12. Current commands: 9. After adding 2 new: 11. Within budget.

## Effort

~730 LOC total: 510 LOC refactoring across 5 existing loops, 220 LOC for 2 new skills.

## Post-Migration Cleanup

Once all pages are migrated to blocks (separate effort), remove page-validation branches from the 5 refactored loops (~200 LOC deletion). Not part of this ADR.

## Consequences

### Positive

- Block system artifacts are validated by the nightly adaptive engine from day one
- Migration safety net — stale block refs, broken data pipelines, and view schema errors caught automatically
- Dual-support approach means existing page validation continues working during transition

### Negative

- ~150 LOC of temporary dual-support branching that will be deleted post-migration
- Two new skills to maintain (auto-block-wiring, auto-view-schema)

### Risks

- Block component file location (`src/dashboard/components/blocks/types/`) may change if ADR-406 evolves — would require updating auto-dead-ui scanner
- View YAML schema is new and may evolve — auto-view-schema checks will need to track schema changes
