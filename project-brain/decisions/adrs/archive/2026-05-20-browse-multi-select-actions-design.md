---
title: "Browse Multi-Select Actions: Pick Items, Hand the Set to Chat"
date: 2026-05-20
status: accepted
scope: design
authors:
  - gsannikov
related:
  - ADR-748
  - docs/superpowers/specs/2026-05-13-browse-sweep-design.md
  - apps/dashboard/app/(views)/browse/page.tsx
  - apps/dashboard/app/(views)/browse/useBrowseState.ts
  - apps/dashboard/app/(views)/browse/BrowseToolbar.tsx
  - apps/dashboard/app/(views)/browse/BrowseDisplayRenderer.tsx
  - apps/dashboard/components/shared/BrowseCardShell.tsx
  - apps/dashboard/components/shared/BrowseListRowCard.tsx
  - apps/dashboard/lib/stores/chatStore.ts
  - apps/dashboard/lib/browse/sweepCandidates.ts
  - apps/dashboard/lib/browse/sweepPrompt.ts
tags:
  - browse
  - multi-select
  - chat-handoff
  - dashboard
---

# Browse Multi-Select Actions: Pick Items, Hand the Set to Chat

## 1. Problem

Browse is a discovery surface. Today every interaction is single-item: click a card to
open its detail panel, run its primary action, pin it, or trigger a prompt. The one bulk
operation that exists — **Sweep visible** — operates on the *entire* filtered set, not on a
user-picked subset, and dispatches headlessly.

The user wants the natural middle ground: **select a few specific items, then act on the
set as a unit**. The canonical flow:

> Select a few notes → click an action ("swap" was the placeholder) → the list of selected
> items is passed into the chat with a command pre-filled → the user continues the
> conversation from that point.

"swap" is not a real command anywhere in the repo; it is the user's stand-in for "some
action button."

## 2. Goals / Non-Goals

**Goals**

- Multi-select items on **every** Browse tab via a **select-mode toggle** (cards stay clean
  by default; checkboxes appear only in select mode).
- A contextual **selection action bar** that appears once ≥1 item is selected.
- Two classes of action: a few **curated presets** plus a **generic "Send to chat"**.
- All actions hand the selected set to the **interactive floating chat** so the user
  continues from that point (not headless).
- Stay inside the existing card-grid mechanism (Rule 32): selection is a *layer over the
  same cards*, the bar is a *contextual toolbar* — no bespoke per-tab panel or new view mode.

**Non-Goals**

- No change to the existing **Sweep visible** entry point (the all-filtered, headless flow
  stays; multi-select Sweep is a separate entry point sharing its builders).
- No cross-tab selection (selection is scoped to the current tab; switching tabs clears it).
- No new persistent storage for the generic/summarize presets (they ride `openChat`).
- No drag-to-select / rubber-band selection in v1.

## 3. Background: the mechanisms we build on

Two existing mechanisms make this small:

1. **Prompt → interactive chat (ADR-748).** `useBrowseState.handleTriggerPrompt` calls
   `openChat({ mode: "auto", initialPrompt })` (`apps/dashboard/lib/stores/chatStore.ts`),
   which opens the floating CLI chat pre-filled with a prompt the user can edit and send.
   This *is* "pass to chat and continue."

2. **Bulk-over-items (Sweep).** `page.tsx → handleSweepVisible` builds candidates from the
   filtered items (`lib/browse/sweepCandidates.ts`), persists them via
   `hygiene-create-selection`, builds a prompt (`lib/browse/sweepPrompt.ts`), and dispatches.
   Multi-select Sweep reuses `buildSweepCandidates` + `hygiene-create-selection` +
   `buildSweepPrompt` on the *picked subset*, but routes through `openChat` instead of the
   headless `runCliExecPrompt` so the Tier 2/3 Q&A becomes interactive.

The render path we extend:
`BrowseContentGrid → BrowseDisplayRenderer → BrowseCardShell | BrowseListRowCard`.

> **Naming hazard:** `sharedProps.selected` / `onSelect` in `BrowseDisplayRenderer` already
> mean *single-select detail-panel highlight*. Multi-select MUST use new prop names
> (`selectionMode`, `isMultiSelected`, `onToggleMultiSelect`) so the two never collide.

## 4. Architecture

Five focused units, each independently testable:

### 4.1 Selection state — `apps/dashboard/lib/browse/useBrowseSelection.ts`

A small hook (or slim zustand store) — **not** added to the already ~1700-line
`useBrowseState`. Holds:

- `selectionMode: boolean`
- `selectedIds: Set<string>` (item IDs)

API: `enter()`, `exit()`, `toggle(id)`, `selectAllVisible(ids: string[])`, `clear()`,
`isSelected(id)`, plus derived `selectedCount`.

Lifecycle rules:

- **Resets on tab (viewMode) change** and on `exit()`.
- **Survives** "load more", filter changes, and search within the same tab. Selection is by
  ID, so an item that scrolls out of the filtered set stays selected; `selectedCount`
  reflects the true total and `Clear` resets it. (Accepted trade-off: a selected item can be
  off-screen; the count keeps the user honest, `Clear` is always one click.)

### 4.2 Toolbar toggle — `BrowseToolbar.tsx`

A `Select` button next to the existing display-mode / filters controls. Reads `selectionMode`
from the page; label flips to `Done` while active. New props:
`selectionMode`, `onToggleSelectionMode`.

### 4.3 Card selectability — `BrowseDisplayRenderer.tsx` + shell components

`BrowseDisplayRenderer` threads three new props down to `BrowseCardShell` and
`BrowseListRowCard`:

- `selectionMode: boolean`
- `isMultiSelected: boolean`
- `onToggleMultiSelect: () => void`

Behavior:

- When `selectionMode` is **off** → unchanged (primary click opens detail / runs action).
- When `selectionMode` is **on** → a checkbox renders in the card corner (list row: leading
  checkbox), and the card's **primary click toggles selection** instead of opening the detail
  panel. A selected card gets a visible selected state (ring/tint reusing existing tokens).

The checkbox markup lives in the shell components (small overlay), **not** in the 909-line
`BrowseCard.tsx` (which already carries a `TODO_CLEANUP` for size).

### 4.4 Selection action bar — `apps/dashboard/components/shared/SelectionActionBar.tsx`

A sticky bar (bottom of the browse list column) shown when `selectedCount > 0`:

```
┌──────────────────────────────────────────────────────────┐
│ 2 selected   [Send to chat ▾] [Summarize] [Sweep]  ·  [Select all visible] [Clear] │
└──────────────────────────────────────────────────────────┘
```

It renders only the actions whose `appliesTo(viewMode)` is true for the current tab. Each
button calls the action's `build()` and dispatches.

### 4.5 Action registry — `apps/dashboard/lib/browse/selectionActions.ts`

```ts
interface SelectionDispatch {
  initialPrompt: string;
  mode: ChatMode;                     // "auto"
  dropped?: number;                   // items the action couldn't handle
}

interface SelectionAction {
  id: string;
  label: string;
  icon: string;                       // icon-map key
  appliesTo: (viewMode: ViewMode) => boolean;
  // sync for generic/summarize; async for Sweep (awaits hygiene-create-selection)
  build: (items: BrowseItem[]) => SelectionDispatch | Promise<SelectionDispatch>;
}
```

Dispatch contract: the page maps `build()` output to
`openChat({ mode, initialPrompt })`. Async actions (Sweep) await the selection-creation MCP
call first, then open chat.

**v1 actions (confirmed):**

| Action | `appliesTo` | Behavior |
|---|---|---|
| **Send to chat** (generic) | all tabs | Bundles selected items into the chat input with a blank intent line; user types the instruction and continues. |
| **Summarize / synthesize** | content tabs: `notes`, `documents`, `wiki`, `pages` | Pre-fills a synthesis instruction over the selection. |
| **Sweep / Archive** | `notes`, `pages` (matches today's `handleSweepVisible` gate; extending to `documents` requires confirming the `buildSweepCandidates` "sources"/docs mapping) | Runs `buildSweepCandidates` on the subset → `hygiene-create-selection` → `buildSweepPrompt` → `openChat` (interactive). Non-archivable items dropped and reported. |

Adding **Compare**, **Tag**, **Add to RAG**, etc. later is a single registry entry.

### 4.6 Prompt format — `apps/dashboard/lib/browse/selectionPrompt.ts`

Generic "Send to chat":

```
Selected 3 items from Browse · Notes:
1. "Title A" — notes/foo.md
2. "Title B" — notes/bar.md
3. "Title C" — notes/baz.md

<describe what you'd like to do with these>
```

- Line format: `N. "<title>" — <path or id>`. Path resolved from item metadata
  (`source_path` / `filePath` / `path`), falling back to the item `id` when no path exists
  (so non-file tabs still produce a usable reference).
- Titles sanitized (collapse newlines, trim) to keep one item per line.
- Summarize replaces the trailing intent line with the instruction.

## 5. Data flow

```
[Select toggle] ─► useBrowseSelection.enter()
   │
   ▼
[card click in select mode] ─► onToggleMultiSelect ─► toggle(id)
   │
   ▼
SelectionActionBar (selectedCount > 0)
   │  click action
   ▼
selectionActions[id].build(selectedItems)
   │  (Sweep: await hygiene-create-selection)
   ▼
openChat({ mode: "auto", initialPrompt })  ──►  floating chat, user continues
```

No hidden dashboard LLM calls; no `fs`/`spawn`/`exec`; AI work flows through `openChat`
(Rule 11). Sweep's only backend touch is the existing `hygiene-create-selection` MCP tool.

## 6. Edge cases

- **Empty selection** → bar hidden; actions unreachable.
- **Items with no path** → still referenced by `id` in the prompt (generic/summarize).
- **Sweep on mixed selection** → archivable items become targets; the rest are dropped and
  the dropped count is surfaced in the prompt and bar.
- **Tab change with active selection** → selection cleared (scoped to tab).
- **Selected item scrolled out by filter/search** → stays selected; count reflects it;
  `Clear` resets.
- **List vs card display mode** → both render the checkbox; selection state is shared.

## 7. Testing

- **Unit:** `useBrowseSelection` (toggle, select-all-visible, clear, tab-change reset,
  survive-load-more); `selectionActions` (`appliesTo` filtering per tab, dropped-count for
  Sweep); `selectionPrompt` (format, title sanitization, path-vs-id fallback).
- **Component/integration:** select-mode toggle reveals checkboxes → selecting shows the bar
  → clicking an action calls `openChat` with the expected `initialPrompt` (mock the store).
- **Real-data / client load (Rules 28, 34):** on the worktree dashboard port, enter select
  mode on a real Notes tab, select real notes, click Send to chat, and confirm the floating
  chat opens pre-filled with the real selected titles/paths — verified in a real browser
  (local browser auto-selected per Rule 35), not a curl smoke.

## 8. ADR

This establishes a reusable Browse interaction pattern (multi-select + selection actions
dispatching to chat), extending ADR-748 and the Sweep pattern. Record a short ADR alongside
implementation so the pattern is canonical and future selection actions have a home.

## 9. File touch list

**New**

- `apps/dashboard/lib/browse/useBrowseSelection.ts`
- `apps/dashboard/lib/browse/selectionActions.ts`
- `apps/dashboard/lib/browse/selectionPrompt.ts`
- `apps/dashboard/components/shared/SelectionActionBar.tsx`
- tests under `tests/dashboard/browse/`

**Modified**

- `apps/dashboard/app/(views)/browse/page.tsx` (wire selection state + bar + dispatch)
- `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx` (Select toggle)
- `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx` (thread props)
- `apps/dashboard/app/(views)/browse/BrowseDisplayRenderer.tsx` (thread props)
- `apps/dashboard/components/shared/BrowseCardShell.tsx` (checkbox + select-mode click)
- `apps/dashboard/components/shared/BrowseListRowCard.tsx` (checkbox + select-mode click)
- a short ADR in `docs/adrs/`
