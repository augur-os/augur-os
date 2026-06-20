---
status: Implemented
date: 2026-05-16
deciders:
  - gsannikov
related: []
hub: dev
tags:
  - dashboard
  - browse
  - ui
  - ux
  - accessibility
  - information-density
superseded_by: null
spec_file: 2026-05-16-browse-page-ux-cleanup-design.md
plan_file: 2026-05-16-browse-page-ux-cleanup.md
---

# ADR-760: Browse Page UX Cleanup

> **ADR-760 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Reduce above-the-fold chrome on `/browse`, fix screen-reader heading hierarchy and touch-target sizing, collapse the two read-only inventory summary strips behind a `Show stats ▾` disclosure, and make the stale-index freshness pill the trigger for `handleReindex` — preserving all existing browse mechanics (OverflowBar, BrowseToolbar, sweep/reindex, detail panel, FAB).

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-16-browse-page-ux-cleanup-design.md`](../superpowers/specs/2026-05-16-browse-page-ux-cleanup-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-16-browse-page-ux-cleanup.md`](../superpowers/plans/2026-05-16-browse-page-ux-cleanup.md)

## Status notes

**Implemented** (2026-05-16). Findings sourced from a verified-in-browser UI/UX review at the worktree dashboard (1440×900 + 375×812, real content, 0 console errors).

Headline desktop target met after a two-pass increment:
  - cards above fold at 1440×900: **9** (target ≥ 9)
  - cards fully visible: **6** (2 complete rows)
  - first card top: **349px** (was 416px baseline)
  - headings in main: **31** (1 H1 + 30 card H3s; was 1)

Mobile target closed in the 2026-05-17 follow-up:
  - first card top at 375×812: **339px** (target ≤ 350)
  - mobile cards above fold: **2**
  - mobile cards fully visible: **1**
  - desktop regression check still passes: **9** cards above fold, **6** fully visible, first card top **349px**
  - console errors: **0**

The mobile fix replaces the grouped category OverflowBar with a native category menu below `md`, keeps the desktop grouped OverflowBar intact, and keeps search mode + sort available through the mobile filter panel.

## Related

None directly. Implements CLAUDE.md rules #1 (user-visible correctness), #27 (UI/UX review before shipping), #28 (client-side verification), #31 (dashboard verification proves useful data), and #32 (Browse signals ride existing file cards — this ADR does not introduce a new view mode).

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated:
    - "Unconditional render of inventory summary strips above the card grid"
    - "Card titles rendered as styled <div> instead of <h3>"
    - "Welcome-banner tip chips at sub-12px font size"
  files_affected:
    - apps/dashboard/app/(views)/browse/page.tsx
    - apps/dashboard/app/(views)/browse/BrowseToolbar.tsx
    - apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx
    - apps/dashboard/components/shared/BrowseCard.tsx
    - apps/dashboard/components/shared/SkillBrowseCard.tsx
    - apps/dashboard/components/shared/BrowseCategoryActions.tsx
    - apps/dashboard/components/shared/OverflowBar.tsx
    - apps/dashboard/features/browse/NoteQueueItem.tsx
    - apps/dashboard/__tests__/browse/                          # new a11y + interaction tests
```
