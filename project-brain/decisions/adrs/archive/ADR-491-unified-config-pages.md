---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related: [ADR-490, ADR-483, ADR-274]
hub: null
tags: [dashboard, blocks, config-driven, yaml]
superseded_by: null
---

# ADR-491: Unified Config-Driven Pages

## Context

The dashboard had three overlapping systems for rendering skill content: SkillAutoPage (12 hard-coded sections), Blocks (16 types, MCP-backed), and DashboardWidget (legacy glass panels). Creating a page required writing TSX even for simple stat+table layouts. The UI exposed blocks and auto pages via separate dropdown buttons that overlapped in purpose.

## Decision

Unify page rendering: a page is an ordered list of blocks declared in YAML. Skills declare pages in `augur/pages/*.yaml` with block type, MCP tool, size, and inline config. A single `ConfigPage` component renders them via the existing `BlockRenderer` pipeline with a new `FlowLayout` for size-based auto-flow (`full`/`half`/`third`).

**Key components built:**
- `FlowLayout` — size-based auto-flow component
- `ConfigPage` + `FlowBlockRenderer` — renders YAML config as blocks
- YAML page scanner in `discoverPagesFromFilesystem()`
- Custom block registry (build-time generated for `type: custom` escape hatch)
- Customize button replacing BlocksDropdown + AutoPagesDropdown
- Browse detail auto-generated via `buildDefaultPageConfig()`
- 5 new block types: health, vault-notes, custom-sources, file-list, data-preview (21 total)

**YAML and TSX pages coexist** as first-class hub tabs. Migration is incremental — convert a page by writing YAML and deleting TSX.

**Pilot migration:** career/pipeline converted from 291 TSX lines to 42 YAML lines.

## Consequences

### Positive

- New skill pages require zero TSX — just YAML config
- Single rendering path for config-driven pages
- Customize button lets users add/remove/reorder blocks at runtime
- Browse skill detail auto-generates from metadata
- 21 block types cover most SkillAutoPage sections

### Negative

- Only 1 of 56 pages migrated — most pages have mutations/custom state that YAML blocks can't express yet
- SkillAutoPage and DashboardWidget can't be removed until block types support mutations/forms
- Custom block type requires build-time registry (not fully dynamic)

## Alternatives Considered

1. **Migrate all pages at once** — Rejected: most pages have complex interactions requiring TSX
2. **Extend SkillAutoPage with config** — Rejected: adds complexity to an already complex 12-section component instead of replacing it

## References

- Spec: `docs/superpowers/specs/2026-03-23-unified-config-pages-design.md`
- Plan: `docs/superpowers/plans/2026-03-23-unified-config-pages.md`
- Depends on: ADR-490 (Framework Migration), ADR-483 (UI Skill Architecture), ADR-274 (Block capabilities)
