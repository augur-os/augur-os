---
title: "Browse Recency Defaults and Category-Scoped Pins"
date: 2026-05-14
status: draft
scope: design
authors:
  - gsannikov
related:
  - ADR-734
  - apps/dashboard/app/(views)/browse/page.tsx
  - apps/dashboard/app/(views)/browse/useBrowseState.ts
  - apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx
  - apps/dashboard/components/shared/BrowseCard.tsx
  - src/mcp/augur_framework/tools/infrastructure/pins.py
tags:
  - browse
  - dashboard
  - pins
  - recency
  - ux
---

# Browse Recency Defaults and Category-Scoped Pins

## 1. Problem

Browse currently defaults to alphabetical ordering (`name-asc`). That is stable, but it makes newly created material disappear into the middle of dense tabs such as Skills, Wiki, ADRs, Sources, Notes, Pages, Actions, Prompts, Commands, and development surfaces.

The user wants Browse to behave more like a practical operating surface:

- newly created items should appear at the top of each Browse tab by default;
- once the user applies search or filters, the narrowed result set should stay trustworthy;
- users should be able to pin important cards so they stay on top in their relevant tab.

There is already a page/artifact pin system backed by MCP tools (`pin-list`, `pin-add`, `pin-remove`), but it is effectively page-focused and does not provide a general card-level Browse pin UX.

## 2. Goals

- Make Browse default ordering more useful: pinned cards first, then recent cards, then name.
- Apply the behavior across Browse categories where card data is available.
- Treat user search, filters, and explicit sort controls as user intent.
- Let users pin and unpin cards directly from the card UI.
- Keep pins scoped to the active Browse category so a pinned Skill does not affect ADRs, Wiki, or Pages.
- Reuse MCP-backed pin persistence instead of dashboard-local storage.
- Preserve existing page/artifact pins.
- Verify the behavior through unit tests and real browser checks because this touches Browse UI.

## 3. Non-Goals

- Do not create a separate "Pinned" Browse tab.
- Do not show pinned cards that fail the active search or filters.
- Do not duplicate pinned cards in a separate strip and again in the normal result grid.
- Do not add dashboard-owned file writes, local storage persistence, or hidden direct filesystem access.
- Do not require every scanner to emit a perfect creation timestamp before the feature can ship.
- Do not change Browse category taxonomy or hub grouping.
- Do not build drag-and-drop manual ordering.

## 4. User-Approved Decisions

| Question | Decision |
|---|---|
| Default ordering | Use pins first, then newest-created items, then name. |
| Missing `created_at` | Fall back through useful timestamp fields rather than ignoring the item. |
| Pin scope | Category-scoped pins. |
| Pin control placement | Small icon toggle in the card header, mirrored in the card overflow menu. |
| Filters/search behavior | Pinned cards stay on top only inside the current matching result set. |
| Approach | Use a unified priority sort rather than a separate pinned strip or manual-only sort mode. |

## 5. UX Behavior

### 5.1 Default Ordering

When a user opens a Browse category with no active search, no active filters, and no explicit non-default sort choice, cards are ordered by:

1. pinned state in the current category;
2. recency timestamp, newest first;
3. title, ascending.

The recency timestamp resolves by the first valid field in this order:

1. `created_at`
2. `createdAt`
3. `created`
4. `promoted_at`
5. `promotedAt`
6. `modified`
7. `modified_at`
8. `modifiedAt`
9. `updated_at`
10. `updatedAt`
11. `timestamp`
12. `date`

Items with no usable timestamp sort after timestamped items and then by title.

### 5.2 Search, Filters, and Explicit Sorts

Search and filters remain authoritative. A pinned item that does not match the active search or filters is hidden like any other non-matching item.

Inside a narrowed result set, pinned matching cards still rank above unpinned matching cards. The remaining matching cards use the active sort dropdown value. If the user has not changed the dropdown, that means the existing `Name (A-Z)` order. This keeps pins useful without making filters feel dishonest or making search results jump around by hidden recency rules.

If the user selects an explicit sort option, Browse respects that sort while still keeping matching pinned cards at the top. The first implementation does not need a "disable pins" sort mode.

### 5.3 Pin Controls

Each card renders:

- a compact pin icon toggle in the card header;
- a `Pin` or `Unpin` action in the existing overflow menu.

Pinned cards show an active visual state on the icon. The pin control must not crowd the existing primary action, badges, or overflow menu.

Pin and unpin failures should keep the previous visual state and show a toast. The UI must not leave an optimistic pinned state after a failed MCP call.

## 6. Data Model

Pins are category-scoped and keyed by a stable Browse identity.

Recommended pin record shape:

```yaml
pins:
  - url: "/browse/knowledge"
    title: "Knowledge"
    kind: "browse-card"
    hub: "brain"
    category: "skills"
    itemKey: "skills::knowledge"
    pinnedAt: "2026-05-14T00:00:00Z"
```

Field meanings:

| Field | Meaning |
|---|---|
| `url` | Existing compatibility field; canonical target or browse URL. |
| `title` | Display title captured at pin time. |
| `kind` | Existing compatibility field; use `browse-card` for general Browse cards unless a legacy page/artifact kind already applies. |
| `hub` | Card hub at pin time. |
| `category` | Browse category where the pin applies. |
| `itemKey` | Stable category-scoped identity, such as `${category}::${item.id}` or `${category}::${canonicalUrl}`. |
| `pinnedAt` | UTC timestamp from MCP. |

Existing pins without `category` and `itemKey` remain valid for Pages. The implementation should map old page/artifact pins into the Pages category using their existing `url`.

## 7. Architecture

### 7.1 Ownership

`useBrowseState` owns Browse ordering and pin state. It should:

- fetch pins through `pin-list`;
- normalize pin records into a category-scoped lookup;
- derive a sort profile for each `BrowseItem`;
- return the ordered list to `BrowseContentGrid`;
- expose pin state and toggle handlers to card rendering.

`BrowseCard` owns only presentation and user interaction. It should receive enough props to render the pin state and call an `onTogglePin` handler. It must not know how Browse orders cards or where pins are stored.

The MCP pin tools own persistence in the vault. Dashboard code should not write pin files directly.

### 7.2 Ordering Helper

Create a small Browse sorting helper that can be tested independently. It should expose behavior equivalent to:

```typescript
type BrowseSortProfile = {
  itemKey: string;
  pinned: boolean;
  timestampMs: number | null;
  title: string;
};
```

The helper should parse timestamp candidates defensively. Invalid timestamps are treated as absent.

### 7.3 Pin Mutations

Pin and unpin actions should call existing MCP tools, extended as needed:

- `pin-add`
- `pin-remove`
- `pin-list`

The first implementation may add optional `category` and `itemKey` parameters to `pin-add` / `pin-remove` while keeping current calls valid. Existing page/artifact call sites must continue to work.

## 8. Error Handling

- If `pin-list` fails, Browse should still render normally with no pinned priority and should surface the error only if the existing MCP query pattern would show it.
- If `pin-add` fails, leave the card unpinned and show a toast.
- If `pin-remove` fails, leave the card pinned and show a toast.
- If a pin references an item that no longer exists, ignore it for rendering and ordering.
- Duplicate pins for the same category/item key should resolve to one pin. Prefer the earliest existing pin order unless a later migration explicitly rewrites the file.

## 9. Testing

Minimum unit coverage:

- timestamp fallback order: `created_at` before `promoted_at` before `modified` / `updated_at`;
- timestamp-less items sort after timestamped items by title;
- category-scoped pins do not affect other categories;
- existing page/artifact pins still rank Pages items correctly;
- active search and filters hide non-matching pinned items;
- pin/unpin calls pass category and item key;
- failed pin/unpin mutation keeps previous UI state.

Minimum browser verification:

- open `/browse` in a real browser against the correct checkout/port;
- verify at least one operational category and one development/system category load to interactive state;
- verify pinned matching cards appear above unpinned cards;
- verify search or a filter hides pinned cards that do not match;
- verify no fatal overlay, chunk-load error, or empty placeholder hides useful data.

## 10. Implementation Boundary

The next implementation plan should work in small checkpoints:

1. add tested sort-key and timestamp normalization helpers;
2. extend pin MCP helpers for category and item keys while preserving legacy pins;
3. wire `useBrowseState` to category-scoped pin lookup and default recency ordering;
4. add card pin controls and overflow actions;
5. add dashboard tests for ordering, filtering, and mutation behavior;
6. run dashboard/browser verification.

Do not mix this work with Browse taxonomy changes, sweep behavior, capability policy actions, or unrelated ADR/index cleanup.
