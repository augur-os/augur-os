# ADR-760 Implementation Plan — Browse Page UX Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. **No prerequisites** — this plan is independent of in-flight ADRs (ADR-755 routine modernization, ADR-759 worktree toolchain). Touches dashboard UI surfaces only; no schema, MCP tool, or capability-exposure changes.

**Goal:** Reduce above-the-fold chrome on `/browse` from 8+ rows to 4, restore screen-reader heading hierarchy, make the stale-index pill an action button, fold two duplicated filter strips into the existing BrowseToolbar Filters popover. After this plan: 1440×900 viewport shows ≥9 cards above the fold (vs ~6 today); 375×812 mobile scroll-to-first-card ≤350px (vs ~600px today); axe-core reports zero critical/serious violations on the three primary views (Skills, Notes, Background Routines).

**Architecture:** Pure dashboard UI edits in `apps/dashboard/`. No new routes, no MCP changes, no config moves. Existing filter state (`useBrowseState`) is untouched — the strips fold *visually* into the Filters popover; their state bindings stay identical. Existing slot/handler contracts (`OverflowBar`, `BrowseCategoryActions`, `BrowseToolbar`) gain optional props, default-off for any non-Browse consumer.

**Tech Stack:** React/Next.js (`apps/dashboard/`), Tailwind tokens (`--*` CSS variables, no new ones), Lucide icons (already in tree), Playwright for Layer 3 verification.

**Spec:** `docs/superpowers/specs/2026-05-16-browse-page-ux-cleanup-design.md`. **Depends on:** nothing. **Independent of:** ADR-755, ADR-759.

---

## File Structure

### Create

| Path | Responsibility |
|------|----------------|
| `apps/dashboard/__tests__/browse/heading-hierarchy.test.tsx` | Assert card titles render as `<h3>` |
| `apps/dashboard/__tests__/browse/freshness-pill-action.test.tsx` | Assert stale freshness pill dispatches `handleReindex` on click and is non-interactive when fresh |
| `apps/dashboard/__tests__/browse/stats-disclosure.test.tsx` | Assert inventory strips collapse by default, open on click, persist via localStorage |
| `tests/dashboard/test_browse_layout_layer3.py` | Manual Playwright checklist — above-fold counts, mobile scroll distance, axe-core run |

### Move

None — pure in-file edits.

### Delete

| Path | Disposition |
|------|------|
| `QUICK_TIPS` constant + its `.flex` chip row in `apps/dashboard/app/(views)/browse/page.tsx` | Inlined removal; the WelcomeBanner keeps its title block + 2 CTAs |

### Modify

| Path | Change |
|------|--------|
| `apps/dashboard/app/(views)/browse/page.tsx` | Remove tip-chip row, merge eyebrow+H1 into a single H1 (`"Browse · " + activeCategory.label`), wrap freshness pill in conditional `<button>` when not fresh, add `aria-valuetext` to splitter |
| `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx` | Wrap the two inventory strips (lines 356-391) in a single `<details>` with summary "Show stats ▾" + `localStorage` persistence (key `augur-browse-stats-open`); add `tabular-nums` to count spans |
| `apps/dashboard/components/shared/BrowseCard.tsx` (line 681) | Title `<div>` → `<h3>`; visual classes unchanged |
| `apps/dashboard/components/shared/SkillBrowseCard.tsx` (line 151) | Title `<div>` → `<h3>`; visual classes unchanged |
| `apps/dashboard/components/browse/CommandCard.tsx` | Already uses `<h3>` (line 249); no change |
| `apps/dashboard/components/shared/BrowseCategoryActions.tsx` | Rename trigger label `"Actions"` → `"Manage"`; prepend `Settings2` Lucide icon |
| `apps/dashboard/components/shared/OverflowBar.tsx` | Accept optional `renderGroupSeparator` prop; when supplied (desktop), render a thin column-rule + uppercase group eyebrow above each cluster |
| `apps/dashboard/features/browse/NoteQueueItem.tsx` | When `status === 'failed'`, render a `[Retry]` button (URL items only; file uploads hide it — no replayable source) |
| `apps/dashboard/app/(views)/browse/page.tsx` (WelcomeBanner CTAs) | `py-1.5` → `py-2.5`, add `min-h-[44px]`, drop `text-xs` if present to allow content to anchor at base size |
| `apps/dashboard/app/(views)/browse/page.tsx` (Suspense skeleton) | `animate-pulse` → `motion-safe:animate-pulse` |
| `apps/dashboard/lib/timestamps.ts` (or wherever `getStalenessLevel` lives) | No change to the function. Just consumed by the new freshness button wrapper. |

---

## Tasks

> Order is dependency-driven. Each task ends with a manual or automated check that proves the change works before the next task starts. Layer 3 verification (rule #34) runs at the end.

### Task 0 — Baseline measurements

- [ ] Open `localhost:3000/browse` at 1440×900 with the dev server already running (via `/dev-build` if cold). Wait for skeletons to clear (~3s).
- [ ] Count visible cards above the fold via the browser DevTools console: `document.querySelectorAll('main .rounded-2xl').length` filtered to those with `getBoundingClientRect().bottom < 900`. Record the number (baseline target: ~6).
- [ ] Resize to 375×812 and measure `document.querySelector('main [role="article"], main .rounded-xl').getBoundingClientRect().top + window.scrollY`. Record the number (baseline target: ~600px).
- [ ] Run axe-core (`pnpm dlx @axe-core/cli localhost:3000/browse --tags wcag2a,wcag2aa`). Record critical+serious count.
- [ ] Save all three numbers in a comment block at the top of `tests/dashboard/test_browse_layout_layer3.py` as `# BASELINE 2026-05-16: cards_above_fold=N, mobile_scroll_to_first=Npx, axe_violations=N`.

**Why first:** rule #34 — we need a real-data baseline to prove the user-visible improvement, not just "the test passes".

### Task 1 — Heading hierarchy fix (smallest, safest, highest a11y leverage)

- [ ] Write `apps/dashboard/__tests__/browse/heading-hierarchy.test.tsx`: renders `BrowseContentGrid` with a fixture of 3 BrowseItems, asserts `screen.getAllByRole('heading', { level: 3 }).length === 3`.
- [ ] Run the test — it must fail (titles are `<div>` today).
- [ ] Change card title element in the card row components within `BrowseContentGrid` from `<div>` to `<h3>`. Keep all className strings identical so the visual is unchanged.
- [ ] Run the test — it must pass.
- [ ] Verify in browser: cards still render visually identical at 1440×900.

### Task 2 — Welcome-banner tip removal + CTA touch target

- [ ] Edit `apps/dashboard/app/(views)/browse/page.tsx`: delete `QUICK_TIPS` constant and the `<div className="flex flex-wrap gap-1.5" aria-label="Browse quick tips">` block that renders it.
- [ ] Change WelcomeBanner CTA `<Link>` className: `py-1.5` → `py-2.5`, add `min-h-[44px]`, ensure inline-flex centering keeps text vertical-centered.
- [ ] Visual check in browser at 1440×900: WelcomeBanner is shorter; CTAs are bigger; nothing else moves.
- [ ] Visual check at 375×812: banner stays hidden via existing `sm:flex` (no change needed).

### Task 3 — Replace eyebrow + H1 pair with single H1

- [ ] In the summary panel section of `page.tsx`: remove the `"WORKSPACE LIBRARY"` eyebrow `<div>`. Change `<h1>Browse</h1>` to `<h1>Browse · {activeCategory.label}</h1>`. Keep the count badge sibling identical.
- [ ] When `activeCategory.id === 'skills'`, the H1 reads `"Browse · Skills"`; when `'notes'`, `"Browse · Notes"`, etc.
- [ ] Visual check: H1 carries the active category context without taking an extra row.

### Task 4 — Freshness pill as Reindex action

- [ ] Write `apps/dashboard/__tests__/browse/freshness-pill-action.test.tsx`: render summary panel with `lastIndexed` set to 7 days ago. Assert pill is `<button>` and clicking it calls the `onReindex` prop. Set `lastIndexed` to "just now" — assert pill is `<span>` (not focusable).
- [ ] Run the test — fails today.
- [ ] In `page.tsx`, wrap the freshness pill `<span>` in `<button>` when `stalenessLevel !== 'fresh' && stalenessLevel !== null`. `onClick={handleReindex}`, `disabled={reindexing}`, `aria-label={`Reindex (last indexed ${formatTimeAgo(currentFreshness)}, status: ${stalenessLevel})`}`.
- [ ] Pass props through `BrowseCategoryActions` if necessary, or wire `handleReindex` directly to the pill since both live in the same component.
- [ ] Run the test — passes.
- [ ] Browser verification: with `?stale=test` query (or by waiting / faking the index date) click the pill → reindex toast appears, same flow as today's menu action.

### Task 5 — Collapse inventory strips behind disclosure

> **Premise correction (2026-05-16):** the strips at `BrowseContentGrid.tsx:356-391` are **read-only count summaries** rendered inline — not separate components, not filter controls. They display the output of `summarizeSkillInventory()` and `summarizeCapabilityInventory()`. Folding them into the Filters popover (the earlier plan) would have been wrong because they don't filter anything. The right move is to keep the data live but collapse it behind a disclosure so default chrome shrinks while power users can still expand on demand.

- [ ] Write `apps/dashboard/__tests__/browse/stats-disclosure.test.tsx`: render `BrowseContentGrid` with a fixture that triggers both summary strips. Assert: (1) the inventory strips are NOT visible by default; (2) clicking the `Show stats ▾` summary reveals both strips; (3) `localStorage.getItem('augur-browse-stats-open')` is set to `'true'` after opening; (4) on a re-render with `localStorage` already `'true'`, the strips render expanded.
- [ ] Run the test — must fail (today the strips render unconditionally).
- [ ] In `BrowseContentGrid.tsx`, replace the two unconditional `<div data-testid="skills-insight-strip">` and `<div data-testid="capability-insight-strip">` blocks with:
  - A `<details>` element wrapping both strip divs.
  - `<summary>` text reads `Show stats` with a chevron icon (`ChevronDown` from `lucide-react`), styled to match other disclosure widgets in the dashboard.
  - `<details>` `open` attribute reads from a useState initialized from `localStorage.getItem('augur-browse-stats-open') === 'true'` (guarded with a try/catch + SSR-safe `typeof window !== 'undefined'`).
  - `onToggle` handler writes back to `localStorage`.
- [ ] Run the test — passes.
- [ ] Visual check at 1440×900 with a fresh localStorage: cards sit ~70px higher; the `Show stats ▾` line is present and clicks open both strips inline.
- [ ] Reload — disclosure state persists.

### Task 6 — Tabular nums on inventory count spans

- [ ] In `BrowseContentGrid.tsx`, add `tabular-nums` (Tailwind utility) to each `<span>` inside the now-collapsed inventory strips that renders a count (`Total: N`, `Augur: N`, etc., lines 362-389).
- [ ] Visual check: open the disclosure, change the active category — count widths no longer twitch.

### Task 7 — Manage rename + icon

- [ ] In `BrowseCategoryActions.tsx`: change trigger button label from `"Actions"` to `"Manage"`. Import `Settings2` from `lucide-react` and prepend it inside the button (16×16, `mr-1.5`).
- [ ] Visual check: button reads `[icon] Manage ▾`; dropdown contents unchanged.

### Task 8 — OverflowBar journey labels on desktop

- [ ] In `OverflowBar.tsx`: add an optional prop `renderGroupSeparator?: (groupKey: string, groupLabel: string) => ReactNode`.
- [ ] In `page.tsx` BrowseOverflowBar call: supply a `renderGroupSeparator` that renders a thin vertical `border-l border-[var(--border-color)]/60` + an uppercase eyebrow with `text-[0.6rem] tracking-[0.18em] text-[var(--text-muted)]`. Render this between clusters only on `md:` and up (use `hidden md:flex`).
- [ ] Visual check at 1440×900: tabs cluster under their journey-group labels; the two-row wrap is structurally legible. At 375×812: unchanged.

### Task 9 — NoteQueueItem retry for URL failures

- [ ] In `NoteQueueItem.tsx`: when `status === 'failed'` and the item has a parseable URL source, render a `[Retry]` button. `onClick` calls a passed-in `onRetry?: (item: NoteQueueItemData) => void` prop.
- [ ] In `page.tsx`, wire `onRetry` to detect URL items (e.g. `item.name.match(/^https?:\/\//)`) and call `handleSubmitUrl(item.name)`; otherwise no-op.
- [ ] Visual check: simulate a failed URL ingest (use a 404 URL). Retry button appears; clicking it re-submits.

### Task 10 — Splitter aria-valuetext + reduced-motion

- [ ] In the splitter `<div role="separator">` in `page.tsx`: add `aria-valuetext={`${splitPercent}% width`}`.
- [ ] In the Suspense skeleton at the bottom of `page.tsx`: change `animate-pulse` to `motion-safe:animate-pulse` everywhere it appears in the skeleton subtree.
- [ ] Verify with SR (VoiceOver): focusing the splitter announces "60 percent width" not just "60".
- [ ] Verify with `prefers-reduced-motion: reduce` in DevTools: skeleton is static.

### Task 11 — Layer 3 verification (rule #34)

- [ ] Reopen `localhost:3000/browse` at 1440×900. Re-run the above-fold card count from Task 0's recipe. Must be ≥9.
- [ ] Reopen at 375×812. Re-run the scroll-to-first-card measurement. Must be ≤350px.
- [ ] Re-run axe-core. Critical+serious violations must be 0.
- [ ] Update `tests/dashboard/test_browse_layout_layer3.py` with the new numbers under `# POST-CHANGE 2026-MM-DD:` line below the BASELINE comment.
- [ ] In all three views (Skills, Notes, Background Routines): verify cards still render, filters still filter, sweep/reindex actions still dispatch from the Manage menu, detail panel still opens and closes, NoteFAB still opens the NoteModal.
- [ ] **If any of the above three numbers misses target**, do not merge. Add a finding to the spec under "Verification" and triage the gap before re-running.

### Task 12 — Commit + handoff

- [ ] Run `/auto-lint` and `/auto-format`. Fix anything they flag.
- [ ] Run `/auto-test-build` to ensure the dashboard still builds.
- [ ] `git add -A` the files in the Modify table above + the new test files.
- [ ] Commit: `feat(browse): ADR-760 reduce chrome density, restore heading hierarchy, make freshness pill actionable`. Include the BASELINE → POST-CHANGE numbers in the commit body.
- [ ] Update ADR-760 status from `Proposed` to `Implemented`. Update `docs/generated/adr-index.md` if it's hand-maintained (otherwise the regen step covers it).
- [ ] Do **not** push without explicit user confirmation per CLAUDE.md.

---

## Out of scope (deferred)

- **Card hierarchy redesign** (title + description + chips + actions visual weight). The card row components stay structurally identical; only the title element changes for a11y. A broader redesign of card hierarchy is a separate decision; not bundled here.
- **Detail-panel mobile collapse.** The right-side detail panel uses `flex-1` next to the list panel — its small-screen behavior wasn't verified in this review. Tracked as a follow-up via `TODO_BUG` placed in `page.tsx:728` during Task 11 if observed broken.
- **Empty-state copy review for each of the 13 categories.** Only "Skills" was loaded with real data during the review; empty states weren't exhaustively audited.
- **Welcome-banner per-action dismissal vs per-device dismissal.** Today it's per-device via localStorage. Left as-is.
