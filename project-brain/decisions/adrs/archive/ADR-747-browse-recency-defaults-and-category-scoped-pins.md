---
status: Implemented
date: 2026-05-14
deciders:
  - gsannikov
related:
  - ADR-734
  - ADR-728
hub: command
tags:
  - browse
  - dashboard
  - pins
  - recency
  - ux
  - mcp
superseded_by: null
spec_file: 2026-05-14-browse-recency-pins-design.md
plan_file: 2026-05-14-browse-recency-pins.md
---

# ADR-747: Browse Recency Defaults and Category-Scoped Pins

> **ADR-747 is an index file.** The substantive design and implementation steps live in the linked spec and plan. This file carries pointers, status, lifecycle notes, and the implementation prompt for a fresh session.

## Decision summary

Browse cards should default to category-scoped pinned cards first, then newest-created or recently changed cards, then name, while search, filters, and explicit sorts remain authoritative.

## Context

Browse currently defaults to alphabetical ordering. That is stable, but it makes newly created skills, wiki pages, ADRs, notes, sources, actions, commands, prompts, and system surfaces disappear into dense category grids.

The user wants Browse to behave like an operating surface: recently created items should be visible at the top of each tab until the user narrows the view, and important cards should be pinnable so they remain at the top of their relevant category. Augur already has MCP-backed page/artifact pins, so the dashboard should extend that persistence model instead of introducing dashboard-local storage.

Constraints:

- Search and filters must remain trustworthy. Pinned cards that do not match the current query or filters stay hidden.
- Pins must be scoped by Browse category. A pinned Skill must not reorder ADRs, Wiki, Pages, or Sources.
- Existing page/artifact pin behavior must continue to work.
- Dashboard persistence must stay MCP-backed through `pin-list`, `pin-add`, and `pin-remove`.
- Browser verification is required because this changes user-visible Browse behavior.

## Decision

Adopt a unified Browse priority order:

1. Matching pinned cards in the active category.
2. Matching unpinned cards by best available recency timestamp, newest first.
3. Matching unpinned cards by title, ascending.

Add a reusable dashboard ordering helper that owns stable Browse item keys, timestamp fallback parsing, legacy page-pin matching, and default sorting. The timestamp fallback order starts with creation fields and then falls back to promoted, modified, updated, timestamp, and date fields when creation time is absent.

Extend the MCP pin contract with optional `category` and `itemKey` fields while preserving legacy `url`-only page pins. Browse pin mutations will send category-scoped targets; existing page/artifact pin call sites remain valid.

Render pin controls on Browse cards as a compact header icon and an overflow menu action. Pin and unpin failures must leave the previous visual state intact and surface the existing toast/error behavior.

Add a visible `Default` sort option so the toolbar describes the real default behavior. When the user applies search, filters, or an explicit sort, pins still rank above matching unpinned cards, but non-matching pinned cards remain hidden and the narrowed set respects the selected sort semantics.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-14-browse-recency-pins-design.md`](../superpowers/specs/2026-05-14-browse-recency-pins-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-14-browse-recency-pins.md`](../superpowers/plans/2026-05-14-browse-recency-pins.md) - 6 implementation tasks: tested ordering helper; MCP pin contract; `useBrowseState` ordering and mutations; card pin controls; toolbar default sort option; final auto-loop and browser verification.

## Consequences

Positive:

- Newly created Browse items become discoverable without requiring manual sorting.
- Users can keep important cards at the top without losing trust in search or filters.
- Pin persistence stays inside the existing MCP/vault-backed contract.
- The ordering logic becomes independently testable instead of being spread across card rendering.

Negative:

- Browse sorting becomes more complex because default ordering, explicit sort ordering, narrowed results, and legacy pins all need to compose.
- Pin mutations add a new failure path to card interactions.
- MCP pin tools gain optional shape, so tests must protect existing page/artifact behavior.

Neutral:

- Some items will lack creation timestamps at first and will fall back to modified or updated timestamps until their scanners emit better metadata.
- This ADR does not add drag-and-drop manual ordering or a separate pinned Browse tab.

## Implementation Order

1. Add `apps/dashboard/lib/browse/pinOrdering.ts` and `tests/dashboard/browse/pinOrdering.test.ts`.
2. Extend `src/mcp/augur_framework/tools/infrastructure/pins.py` and `tests/test_pins_tool.py` for optional `category` and `itemKey` support.
3. Wire `apps/dashboard/app/(views)/browse/useBrowseState.ts` to fetch pins, derive pin state, toggle pins through MCP, and use the ordering helper.
4. Add shared card pin controls across `BrowseCard`, `SkillBrowseCard`, and `BrowseContentGrid`.
5. Add the toolbar `Default` sort option and align tests with the new sort contract.
6. Run required auto-loops and perform real browser verification on `/browse`.

The implementation plan is the detailed execution source of truth and should be followed checkbox by checkbox.

## Alternatives Considered

- Keep alphabetical default and only add a manual sort option. Rejected because it does not solve the default Browse discoverability problem.
- Add a separate pinned strip above the grid. Rejected because it duplicates cards, complicates search/filter semantics, and creates a second scanning path.
- Store Browse pins in dashboard local storage. Rejected because dashboard persistence must remain MCP-backed and portable across sessions.
- Make pins global across all Browse categories. Rejected because category context is load-bearing; the same identifier or URL can have different meaning across Skills, Pages, ADRs, Sources, and Wiki.

## References

- ADR-734 - Capability Surface Phase 3 and Browse Control Hub.
- ADR-728 - Browse Page Lifecycle Ordering and Journey-Group Delimiters.
- `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- `apps/dashboard/components/shared/BrowseCard.tsx`
- `apps/dashboard/components/shared/SkillBrowseCard.tsx`
- `src/mcp/augur_framework/tools/infrastructure/pins.py`

## Status notes

Accepted after focused UX brainstorming and implementation planning on 2026-05-14. The companion spec records the user-approved UX decisions; the companion plan records the TDD execution sequence for a fresh implementation session.

Load-bearing claims:

- Pins are priority within the current matching result set, not a bypass around search and filters.
- Category-scoped `itemKey` is required to prevent one Browse category from reordering another.
- Legacy page/artifact pins remain valid and must be covered by tests.
- Dashboard writes no pin files directly; persistence goes through MCP tools.

## Related

- ADR-734 - Capability Surface Phase 3.
- ADR-728 - Browse lifecycle ordering.

## Impact Manifest

```yaml
paths_renamed: []
apis_changed:
  - pin-add accepts optional category and itemKey fields for Browse card pins
  - pin-remove accepts optional category and itemKey fields for Browse card pins
patterns_deprecated:
  - Browse name-asc as the hidden default priority for all unnarrowed categories
  - page-only assumptions in the pin persistence model
files_affected:
  - apps/dashboard/lib/browse/pinOrdering.ts
  - apps/dashboard/app/(views)/browse/useBrowseState.ts
  - apps/dashboard/app/(views)/browse/BrowseToolbar.tsx
  - apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx
  - apps/dashboard/components/shared/BrowseCard.tsx
  - apps/dashboard/components/shared/SkillBrowseCard.tsx
  - apps/dashboard/components/shared/BrowsePinButton.tsx
  - src/mcp/augur_framework/tools/infrastructure/pins.py
  - tests/dashboard/browse/
  - tests/test_pins_tool.py
```

## Implementation Prompt

Use this prompt in a fresh Codex session:

```text
Implement ADR-747 in ~/Projects/Augur.

Read these files first:
- docs/adrs/ADR-747-browse-recency-defaults-and-category-scoped-pins.md
- docs/superpowers/specs/2026-05-14-browse-recency-pins-design.md
- docs/superpowers/plans/2026-05-14-browse-recency-pins.md
- AGENTS.md
- docs/agent-topics/DASHBOARD.md if dashboard ownership or MCP boundaries are unclear
- docs/agent-topics/WORKFLOWS.md if command or verification routing is unclear

Required workflow:
- Use superpowers:using-git-worktrees before implementation if the current checkout is not already an isolated feature worktree.
- Use superpowers:subagent-driven-development or superpowers:executing-plans to execute the plan task by task.
- Use superpowers:test-driven-development for every code-changing task.
- Use superpowers:verification-before-completion before reporting completion.
- Do not push or merge without explicit user approval.

TeamCreate:
- Objective: implement Browse recency defaults and category-scoped pins from ADR-747.
- Review cadence: one plan task at a time, with local review after each task before starting the next.
- Safety: preserve unrelated local changes; dashboard persistence must remain MCP-backed; do not run raw pnpm, raw pytest, or pnpm dev.

TaskCreate:
- Task 1, developer, medium: add failing tests and implementation for apps/dashboard/lib/browse/pinOrdering.ts.
- Task 2, developer, medium: extend src/mcp/augur_framework/tools/infrastructure/pins.py and tests/test_pins_tool.py for optional category/itemKey pins while preserving legacy URL pins.
- Task 3, developer, high: wire apps/dashboard/app/(views)/browse/useBrowseState.ts to load pins, expose pin state, call pin mutations, and apply default priority ordering.
- Task 4, frontend developer, medium: add BrowsePinButton plus card and grid pin props across BrowseCard, SkillBrowseCard, and BrowseContentGrid.
- Task 5, frontend developer, low: add the toolbar Default sort option and update related tests.
- Task 6, validator, high: run the required auto-loops and browser verification on /browse.

Execution gates:
- Follow the checkbox plan in docs/superpowers/plans/2026-05-14-browse-recency-pins.md exactly.
- After each code task, run the narrowest relevant auto-loop or test command allowed by AGENTS.md, then commit only the focused checkpoint if it is verified.
- Final verification must include /auto-test-dashboard, /auto-test-pytest, /auto-lint, /dev-build, and a real browser check of /browse against the correct checkout/port.
- The browser closeout must name the URL, the real categories inspected, the pin/search/filter behavior observed, and any remaining empty/error/stale states.
```
