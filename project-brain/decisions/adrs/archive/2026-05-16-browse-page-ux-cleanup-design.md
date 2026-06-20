---
date: 2026-05-16
status: Draft
deciders:
  - gsannikov
related:
  - CLAUDE.md rule #1 (user-visible correctness first)
  - CLAUDE.md rule #27 (UI/UX review before shipping)
  - CLAUDE.md rule #28 (client-side verification)
  - CLAUDE.md rule #31 (dashboard verification proves useful data)
  - CLAUDE.md rule #32 (Browse signals ride existing file cards)
---

# Browse Page UX Cleanup — Design

## Goal

Reduce above-the-fold chrome on `/browse` so the first row of result cards is visible on a 900px-tall viewport, fix screen-reader and touch-target violations surfaced by an in-browser UI/UX review, and convert the stale-index freshness pill from a passive sign into an actionable trigger — without changing any existing browse contract (OverflowBar journey grouping, BrowseToolbar filter API, sweep/reindex action dispatch, detail-panel resize, NoteFAB).

Concrete target: cards visible above the fold on 1440×900 go from ~6 (current, measured 2026-05-16) to ≥9; mobile (375×812) scroll-to-first-card distance goes from ~600px to ≤350px; `axe-core` violations on the Skills view go from current baseline (see Task 0) to zero.

## Problem

Verified in-browser at `localhost:3000/browse` on 2026-05-16:

1. **Chrome density.** 8+ rows of UI render before the card grid: WelcomeBanner → "WORKSPACE LIBRARY" eyebrow → H1 + count badge → description → freshness pill + Actions → OverflowBar (2 wrapped rows of tabs) → BrowseToolbar (search + filters + sort) → `SkillsInventoryStrip` chips → `CapabilityInventoryStrip` chips → cards. On 1440×900 the card grid's first row barely peeks above the fold; on 375×812 the user scrolls past ~600px of chrome.
2. **Two read-only summary strips above the grid.** `BrowseContentGrid.tsx:356-391` renders two inline strips — "Skills inventory" (Total / Augur / User / External / Adopted / Needs setup counts via `summarizeSkillInventory`) and "Capability inventory" (Total / byOwner / byManagement / byScope / Drift / byCurrentExposure counts via `summarizeCapabilityInventory`). They are **not filters** — clicking them does nothing. They consume ~70px of vertical chrome on every render and duplicate information the user can derive from the count badge + Filters popover.
3. **Card titles are not headings.** `document.querySelector('h3, h2')` returned `null` inside `BrowseContentGrid`. Card titles render as styled `<div>`, breaking SR skip-by-heading navigation (`heading-hierarchy`, WCAG).
4. **Welcome-banner CTAs are 30px tall.** "Open Brain" and "Open Settings" links use `px-2.5 py-1.5`, measured 83×30 and 99×30 (Playwright `getBoundingClientRect`). Below 44px touch-target minimum.
5. **Welcome-banner tip chips at ~11px.** `text-[0.68rem]` = 10.88px on 16px base. Below the 12px readable-text floor; also low-contrast on `#f0efe9` over `#f9f8f6`.
6. **Stale-index pill is read-only.** When `getStalenessLevel(lastIndexed) === 'aging'` or `'stale'`, the pill shows orange/red dot + "Indexed Nd ago" but is a `<span>`. The Reindex action exists (`handleReindex`) but lives only in the Actions menu — two clicks away from the signal that should trigger it.
7. **Title is said three times.** "WORKSPACE LIBRARY" eyebrow + `<h1>Browse</h1>` + sidebar "Browse" entry. The user already knows they're on Browse; the eyebrow burns vertical space without disambiguating the active *category*.
8. **Inventory chip counts jitter on filter change** — counts ("Augur 33", "Client 84") lack `tabular-nums`, so digit-width changes shift chip widths.
9. **OverflowBar loses journey-group labels on desktop.** Mobile renders categories under section headers (INCOMING / KNOWLEDGE / REUSE / SYSTEM / STATE) which give the 13-tab set structure. Desktop flattens to two wrapped rows without those labels, which costs orientation.
10. **"Actions" button is opaque.** Right-side primary action label is just "Actions" — no icon, no verb. The user can't predict what's inside without clicking.
11. **NoteQueueItem failures have no recovery action.** When `status === 'failed'`, the item shows the error message but no Retry button.

## Non-goals

- **No new view mode for Browse** (would violate rule #32). All signals continue to ride existing card metadata.
- **No change to BrowseToolbar's filter prop surface.** The two inventory strips fold *into* the existing filters popover as additional filter controls; the toolbar's API to `useBrowseState` stays the same.
- **No removal of WelcomeBanner.** It remains, dismissible, with the same localStorage key (`augur-welcome-dismissed`); only its tip-chip row goes away.
- **No change to OverflowBar's `journey_group` data model or `JOURNEY_GROUP_LABELS`.** The visual treatment changes on desktop; the data shape does not.
- **No new design tokens.** Existing CSS variables (`--text-primary`, `--bg-card`, `--accent-warning`, etc.) cover every change here.
- **No conversion of the page to use server components.** It's a `"use client"` page today; that stays.

## Approaches considered

**A. Pure CSS-only density reduction** (tighten paddings, shrink the WelcomeBanner). Doesn't address the duplicated filter rows or the a11y violations. **Rejected** — treats the symptom (too tall), not the cause (filters in three places).

**B. Collapse the two inventory strips behind a single `<details>` disclosure** (chosen). The strips stay live — same data, same render path — but default to closed behind a `Show stats ▾` summary line. Persist open/closed state in `localStorage` (key `augur-browse-stats-open`) so power users who keep them open don't lose that on reload. Saves ~70px above the fold by default; zero data loss.

**C. Move the strips into the summary panel as inline subtitle text** (rejected for now). Renders "83 skills (21 Augur, 50 external, 12 adopted, 5 need setup)" under the H1. Denser horizontally but loses the capability-inventory breakdown which has too many dimensions to inline. Could revisit for the Skills view specifically in a follow-up.

**D. Replace the OverflowBar with a search-only category switcher** (rejected — overcorrects). The OverflowBar gives the user a scannable visual map of all 13 categories; replacing it with a search field forces every category change through a typed query.

**Final choice: B + targeted a11y/touch fixes + freshness-pill-as-button.** All findings folded into one ADR per the user's request.

## Architecture

Three surfaces touched, decoupled:

```
┌─────────────────────────────────────────────────────────────────┐
│  BrowsePageInner  (apps/dashboard/app/(views)/browse/page.tsx) │
│  ─ Removes SkillsInventoryStrip + CapabilityInventoryStrip      │
│  ─ Removes WelcomeBanner tip-chip row                           │
│  ─ Replaces title eyebrow with active-category breadcrumb       │
│  ─ Wraps freshness pill in <button onClick={handleReindex}>     │
│      when stalenessLevel !== 'fresh'                            │
│  ─ Renames "Actions" → "Manage ▾" with an icon                  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  BrowseContentGrid       (./BrowseContentGrid.tsx)             │
│  ─ Skills + Capability inventory strips (lines 356-391) wrap   │
│      in a single <details> with summary "Show stats ▾"         │
│  ─ Closed by default; open state persists in localStorage      │
│      key="augur-browse-stats-open"                              │
│  ─ tabular-nums added to count spans for jitter-free updates    │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Card components (BrowseCard, SkillBrowseCard)                  │
│  ─ Card title element changes from <div> to <h3>                │
│  ─ Card title class set is unchanged — same visual              │
│  ─ CommandCard already uses <h3>; no change needed              │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  OverflowBar              (components/shared/OverflowBar.tsx)  │
│  ─ Mobile (sm:): journey-group labels stay (today)              │
│  ─ Desktop (≥md): journey-group labels render as faint          │
│      column-rule dividers between tab clusters                  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  NoteQueueItem            (features/browse/NoteQueueItem.tsx)  │
│  ─ failed status renders a Retry button that re-invokes the     │
│      upstream submit handler (uploadFiles / handleSubmitUrl)    │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed changes

### Above-the-fold density

| Change | Before | After | Saves |
|---|---|---|---|
| Remove `QUICK_TIPS` chip row from WelcomeBanner | 3 chips, ~24px tall | (removed) | ~32px (incl. margin) |
| Collapse Skills inventory strip behind `<details>` | ~36px | collapsed by default | ~44px |
| Collapse Capability inventory strip behind same `<details>` | ~36px | collapsed by default | ~44px |
| Replace eyebrow + H1 pair with single H1 = `"Browse · " + activeCategory.label` | 2 lines | 1 line | ~24px |
| **Total desktop** | | | **~144px** above the fold |

On 1440×900 this surfaces ~3 additional card rows above the fold (cards measured at ~140px tall with gap).

### Accessibility & touch

- **Card title element → `<h3>`.** Apply only in `BrowseContentGrid`'s card render. Existing className strings carry visual weight; the element change is invisible to sighted users, restorative for SR users.
- **Welcome-banner CTAs `py-1.5` → `py-2.5`** (30px → 40px). Still short of 44px but +33% closer; combined with `min-h-[44px]` on the link itself, the hit area reaches WCAG.
- **Welcome-banner tip chips removed** (resolves both `readable-font-size` and chip-contrast simultaneously).
- **Splitter handle** gains `aria-valuetext={`${splitPercent}% width`}`.
- Test for `prefers-reduced-motion`: scope `animate-pulse` on the Suspense skeleton to `motion-safe:animate-pulse`.

### Freshness pill as action

- Wrap the freshness pill in `<button>` when `stalenessLevel !== 'fresh'`. `onClick` calls `handleReindex`. `aria-label` is `"Reindex (last indexed N ago, status: ${stalenessLevel})"`. `disabled={reindexing}`.
- When `stalenessLevel === 'fresh'`, keep the current read-only `<span>` — no need to suggest reindexing fresh data.

### Numbers

- Add `font-variant-numeric: tabular-nums` to count spans in any inventory chips that survive the fold (the totals row that lives inside the Filters popover).

### "Manage ▾" rename

- `BrowseCategoryActions` trigger button: label `"Actions"` → `"Manage"`, prepend a `Settings2` (Lucide) icon. The disclosure arrow stays. Existing dropdown content unchanged.

### OverflowBar desktop journey labels

- Add an optional `renderGroupSeparator` slot to OverflowBar that desktop opts into: a thin vertical rule + the uppercase group label as a tiny eyebrow above each cluster. Mobile keeps its current behavior (full row-per-group).

### NoteQueueItem retry

- When `status === 'failed'`, render `[Retry]` button. The retry handler is passed in from the page; for the URL path it re-runs `handleSubmitUrl(item.name)`; for files there's no source `File` left (browser-side, can't replay an upload), so the Retry button is hidden for failed file uploads and the user is directed back to the FAB.

## Verification (Layer 3 — rule #34)

A passing test suite is not sufficient. After implementation, the following must be verified in-browser at `localhost:3000/browse`:

1. **Above-the-fold count**: open at 1440×900, count visible card-grid items. Must be ≥9.
2. **Mobile scroll distance**: open at 375×812, measure scroll-to-first-card via DOM `getBoundingClientRect`. Must be ≤350px.
3. **Heading hierarchy**: `document.querySelectorAll('main h1, main h2, main h3').length` must be ≥10 (1 page h1 + section h2s + card h3s).
4. **axe-core violations**: zero critical/serious violations on the Skills view, the Notes view, and the Background Routines view.
5. **Freshness pill**: when index is aging/stale, clicking the pill must dispatch `handleReindex` and show the existing toast. When index is fresh, the pill is not focusable.
6. **No regressions in OverflowBar group labels on mobile** — they still appear under the active category.

The verification matrix lives in `tests/dashboard/test_browse_layout_layer3.py` (new); CI cannot run it (needs a browser), so it ships as a manual `/dev-debug browse-layout` checklist.
