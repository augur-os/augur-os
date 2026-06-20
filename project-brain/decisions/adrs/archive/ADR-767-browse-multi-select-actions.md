---
status: Implemented
date: 2026-05-20
deciders:
  - gsannikov
  - Claude (Augur agent)
related:
  - ADR-748
  - ADR-736
  - ADR-760
hub: null
tags:
  - dashboard
  - browse
  - multi-select
  - chat-handoff
superseded_by: null
spec_file: 2026-05-20-browse-multi-select-actions-design.md
plan_file: 2026-05-20-browse-multi-select-actions.md
---

# ADR-767: Browse Multi-Select Actions — Pick Items, Hand the Set to Chat

## Decision summary

Browse gains a **select mode**: a toolbar `Select` toggle turns every card on the active tab
into a selectable target, a sticky **selection action bar** appears once one or more items are
picked, and the chosen set is handed to the interactive floating chat. Two action classes are
offered — a generic **Send to chat** (all tabs) plus curated presets (**Summarize** on content
tabs, **Sweep** on `notes`/`pages`). Selection is a layer over the existing card grid, not a
bespoke panel, preserving the Browse cards-only contract.

## Context

Browse interactions were single-item: open a card's detail panel, run its primary action, pin
it, or trigger one prompt. The only bulk operation, **Sweep visible** (ADR-736 lineage),
operates on the *entire* filtered set and dispatches headlessly. There was no way to pick a few
specific items and act on them as a unit.

Two existing mechanisms made the gap cheap to close:

- **ADR-748** established prompt → interactive chat: `openChat({ mode: "auto", initialPrompt })`
  opens the floating CLI chat pre-filled, and the user continues from there.
- The **Sweep** pipeline already turns Browse items into a persisted selection
  (`hygiene-create-selection`) and a guided prompt (`buildSweepPrompt`).

The Browse cards-only rule (every tab renders the same `BrowseItem` card grid; signals ride
cards, not bespoke panels) constrained the shape: multi-select had to be a selection *layer*
over the cards plus a contextual toolbar, not a new view mode.

## Decision

1. **Select mode** is a per-tab UI state held in a small dedicated zustand store
   (`useBrowseSelection`) that stores the full selected `BrowseItem` objects (so a dispatch
   survives filter/search changes). Selection resets on tab change.
2. **Cards** gain optional `selectionMode` / `isMultiSelected` / `onToggleMultiSelect` props —
   distinct from the existing `selected`/`onSelect` (which drive the single-select detail
   panel). In select mode a transparent full-card overlay toggles selection and a checkbox
   shows state; out of select mode behavior is unchanged. The renderer reads the store and
   threads per-card state.
3. **Selection action bar** is a sticky contextual toolbar (not a panel/view) shown when the
   count is positive; it renders only the actions whose `appliesTo(viewMode)` is true.
4. **Action registry** (`selectionActions`): each action declares `appliesTo` and an async-safe
   `build(items, viewMode) → { initialPrompt, dropped? }`. v1 actions: `send-to-chat` (all
   tabs), `summarize` (`notes`/`documents`/`wiki`/`pages`), `sweep` (`notes`/`pages`, reusing
   `buildSweepCandidates` + `hygiene-create-selection` + `buildSweepPrompt`).
5. **Dispatch** flows through a pure helper (`dispatchSelectionAction`) into the existing
   `handleTriggerPrompt` → `openChat` path. No hidden dashboard LLM calls; the only backend
   touch is the existing `hygiene-create-selection` MCP tool (Rule 11 preserved).

## Consequences

- The action registry makes future bulk actions (Compare, Tag, Add-to-RAG) a one-entry change.
- Selection is scoped per tab and ephemeral for the generic/summarize presets — no new
  persistent storage; Sweep continues to persist its selection because the cleanup workflow
  needs it.
- A selected item can scroll out of the filtered set; the count stays truthful and `Clear`
  resets. Storing full objects keeps dispatch correct in that case.
- The Browse cards-only contract (ADR-760 / Rule 32) is preserved: the bar is a contextual
  toolbar and the checkbox is an overlay on the same cards.

## Implementation Notes

- New: `useBrowseSelection.ts`, `selectionPrompt.ts`, `selectionActions.ts`,
  `dispatchSelectionAction.ts`, `SelectionActionBar.tsx` (+ unit tests).
- Modified: `BrowseCardShell.tsx`, `BrowseListRowCard.tsx`, `BrowseDisplayRenderer.tsx`,
  `BrowseToolbar.tsx`, `browse/page.tsx`.
- Real-browser verification (Rules 28/31/34) is required because the change touches the
  dashboard UI; intermediate component commits used `Skip-Verify` trailers because the feature
  is only user-surfaced once wired in `page.tsx`.

## Alternatives Considered

- **Route every action through the persisted Sweep selection.** Rejected as the default — it
  writes a selection file to disk even for a throwaway "ask about these"; persistence is kept
  only for Sweep.
- **Hold selection inside `useBrowseState`.** Rejected — that hook is already ~1700 lines; a
  focused store keeps the unit small and independently testable.
- **Always-visible checkboxes / hover checkboxes.** Rejected in favor of an explicit select-mode
  toggle to keep the default browse view clean.

## References

- ADR-748 (prompt → interactive chat), ADR-736 (tiered sweep classification), ADR-760
  (Browse cards-only UX), Rule 11 (dashboard via MCP), Rule 32 (Browse cards-only).
- Spec: `docs/superpowers/specs/2026-05-20-browse-multi-select-actions-design.md`
- Plan: `docs/superpowers/plans/2026-05-20-browse-multi-select-actions.md`
