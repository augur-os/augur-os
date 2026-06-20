---
status: Implemented
date: 2026-05-11
deciders:
  - gsannikov
related:
  - ADR-727
hub: command
tags:
  - dashboard
  - browse
  - information-architecture
  - ui
superseded_by: null
spec_file: 2026-05-11-browse-page-lifecycle-ordering-design.md
plan_file: null
---

# ADR-728: Browse Page Lifecycle Ordering and Journey-Group Delimiters

> **ADR-728 is an index file.** The substantive design lives in the linked spec. No separate plan — the implementation is small enough (~2 files, <100 lines) that the three checkpoints in the spec are sufficient direct guidance.

## Decision summary

Reorder the Browse page's 24 category tabs into a lifecycle journey (raw → processed → reusable → operational → archived), add five visible group labels above the visible tabs (INCOMING · KNOWLEDGE · REUSE · SYSTEM · STATE) and four above the dev tabs (INTENT · WIRING · ORCHESTRATION · DIAGNOSTICS), and decouple the existing `group` field (visibility gate) from a new `journey_group` + `journey_order` schema (lifecycle bucket + within-group rank) so the user can see at a glance what problem each tab answers and where it sits in their workflow.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-11-browse-page-lifecycle-ordering-design.md`](../superpowers/specs/2026-05-11-browse-page-lifecycle-ordering-design.md)

## Plan (canonical, drives `/adr implement`)

- No separate plan — scope is too small for `/superpowers:writing-plans`. The three checkpoints in the spec (§6 — schema additions, tab bar render update, browser verification) are sufficient direct guidance.

## Status notes

Spec written 2026-05-11 in same session as ADR-727 (Background Routines Unified Discovery). Three ADRs touch `BROWSE_CATEGORIES`:
  - **ADR-727** renames `scheduled-executions` → `background-routines`
  - **ADR-723** adds a new `pages` ViewMode (Augur Pages HTML Artifacts)
  - **ADR-728 (this)** adds `journey_group` + `journey_order` schema and lifecycle reordering to every entry

ADR-728's spec §10 documents coordination — including the **reserved placement** for ADR-723's new `pages` category: `journey_group: knowledge, journey_order: 3` (positioned after wiki). ADR-723 implementation MUST honor this when adding the entry to `BROWSE_CATEGORIES`, regardless of which ADR ships first.

User insight that motivated this ADR: "I want to rearrange the browse page tabs so it will make sense in user journey from left to right and see what problem each tab is answering, and also add delimiters in groups." The Browse page exposes 24 categories (25 after ADR-723) with the existing 3-value `group` field doing double duty (visibility + grouping), and no visual delimiters. This ADR fixes both concerns with a two-axis schema.

## Related

- ADR-727 — Background Routines Unified Discovery (renames `scheduled-executions` → `background-routines`; coordinate `BROWSE_CATEGORIES` edits)
- ADR-723 — Augur Pages HTML Artifacts (adds new `pages` ViewMode; ADR-728 reserves its placement at `journey_group: knowledge, journey_order: 3`)
- ADR-722 — Setup Completeness Widget (parallel dashboard discoverability work — sidebar widget, not Browse category; no coordination needed)

## Impact manifest

```yaml
paths_renamed: []
apis_changed:
  - "BrowseCategory interface: adds journey_group (JourneyGroup enum) + journey_order (int) fields; existing group field unchanged"
  - "New exports from apps/dashboard/lib/browse/types.ts: JourneyGroup type, JOURNEY_GROUP_LABELS, JOURNEY_GROUP_ORDER"
patterns_deprecated:
  - "Using the 3-value `group` field for visual grouping (it remains the visibility gate only)"
files_affected:
  - "apps/dashboard/lib/browse/types.ts (schema additions + 24 BROWSE_CATEGORIES entries updated)"
  - "apps/dashboard/app/(views)/browse/BrowseToolbar.tsx (or wherever the tab bar renders — group-by + label-above rendering)"
```
