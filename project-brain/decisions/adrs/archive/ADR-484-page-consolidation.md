---
status: Superseded
date: 2026-03-23
deciders:
- Gur Sannikov
related:
- 483
- 260
- 163
hub: system
tags:
- dashboard
- pages
- components
- refactor
- autopage
- deduplication
superseded_by: ADR-490
---

# ADR-484: Page Consolidation

## Context

The dashboard has 58 pages across 6 hubs totaling ~16,659 LOC. Analysis found ~95 UI patterns independently reimplemented across pages (stat card rows, button rows, item lists, page headers, loading states), 11 logical duplicates where the same data is shown in multiple pages with different code, 7 pages with internal tab navigation, and only 3 AutoPage users (5% adoption). 5 pages grade C (no clear UX purpose); 11 grade B (mixed concerns). The `observe` hub contains no original content — every sub-page duplicates data canonical elsewhere.

## Decision

A 6-phase bottom-up consolidation. The approach is decompose → deduplicate → rebuild, not delete-first.

### Phase 1: Extract 12 shared components

Build reusable components targeting the ~95 duplicated patterns:

| Component | Replaces | Est. LOC saved |
|-----------|----------|----------------|
| `<StatGrid>` | Inline stat card rows (16 pages) | ~800 |
| `<ActionBar>` | Button rows with loading states (13 pages) | ~400 |
| `<DataList>` | Vertical item lists (15+ pages) | ~500 |
| `<DataTable>` | Sortable/filterable tables (6 pages) | ~400 |
| `<StatusBadge>` | Color-mapped status indicators (9 pages) | ~150 |
| `<SearchFilter>` | Search + filter + debounce (6 pages) | ~250 |
| `<PageHero>` | GlassCard header with icon/title/actions (~20 pages) | ~600 |
| `<CollapsibleSection>` | Expand/collapse toggle (15 sections) | ~600 |
| `<NavLinkGrid>` | Navigation card grids (5 pages) | ~150 |
| `<LightControlCard>` | Light toggle + brightness slider (exact dup) | ~150 |
| `<SceneQuickButtons>` | Scene activation grid (exact dup) | ~30 |
| `<PageStates>` | Loading/error/empty state wrapper (~30 pages) | ~600 |

**Total: ~4,630 LOC replaced by ~1,200 LOC of shared components = ~3,400 net reduction.**

### Phase 2: Kill logical duplicates + dissolve `observe` hub

13 pages/redirects killed. Key deletions: `observe/health` (canonical at `daemon/health`), `observe` overview widgets (dup of daemon landing blocks), `daemon` IntegrationsTab (dup of `ai_bridge/integrations`), `ai_bridge` MemoryTab (link to `knowledge/memory` instead), 3 redirect pages converted to Next.js rewrites in config.

`observe` hub dissolved entirely. Original content promoted: `observe/logs` → `command/logs`, `observe/sessions` → `command/sessions`, self-heal tab → `command/self-heal`.

### Phase 3: Split tabbed mega-pages into focused standalone pages

No page retains internal tab navigation. Each tab becomes its own page; landing pages use `<NavLinkGrid>` + `<StatGrid>`. Key splits:

- `daemon/page.tsx` (1,081 LOC) → landing ~80 LOC + 6 standalone pages
- `ai_bridge/page.tsx` (1,565 LOC) → landing ~60 LOC + 3 standalone pages
- `interview/page.tsx` (337 LOC) → 3 standalone pages
- `knowledge/memory` (200 LOC) → 3 standalone pages

### Phase 4: Focus fuzzy pages (grade B → grade A)

Remove embedded duplicates from `venture-augur` (inline pipeline/dev stats → link to canonical pages), `updater` (remove WorkflowsSection, canonical at `/command/workflows`), `home-automation` (landing page only, not inline light controls), `venture-augur/demo` (remove skill scores embed, link to `/adaptive/skill-scores`).

### Phase 5: Convert 20 pages to AutoPage

20 pages replaced by `<SkillAutoPage skillId="..." />` with blocks declared in SKILL.md. 14 pages converted partially (block-expressible elements use blocks; custom interactions remain). 11 pages kept fully custom (interactive workflows, non-data-display UX, terminal emulator, etc.).

### Phase 6: Rebuild remaining pages with shared components

All 14 partial-AutoPage and 11 custom pages rebuilt using Phase 1 components to eliminate inline boilerplate. One PR per page.

## Consequences

### Positive
- ~6,100 LOC total reduction (shared components + AutoPage conversions)
- AutoPage adoption: 3 pages (5%) → 23 pages (41%)
- Zero logical duplicates remaining
- No internal tab navigation anywhere
- Pages graded A (clear user question): 23 → ~50
- `observe` hub eliminated — its canonical content promoted to `command`

### Negative
- Phase 3 splits break any hardcoded links to tabbed pages — Next.js rewrites required for all old tab URLs
- Phase 5 AutoPage conversion requires verifying MCP tool existence per block before converting — missing tools must be created as pre-work
- 6 sequential phases means full completion takes weeks; intermediate states are partially consolidated

### Neutral
- Total page count barely changes: 58 → 56. The win is code quality and UX clarity, not file count
- Phases 2 and 1 can run in parallel; phases 5 and 6 can run in parallel; phases 3–6 require phase 1 to complete first

## Alternatives Considered

### Top-down (delete files first)
Rejected: deletes pages before understanding what's in them, risks losing original content embedded in duplicates.

### Keep internal tabs
Rejected: tabs violate the "one clear user question per page" rule and prevent deep-linking to specific concerns.

### Keep `observe` hub with redirects
Rejected: every observe sub-page is a duplicate. Redirects would keep dead code alive. The canonical pages should simply be promoted.

### Convert all pages to AutoPage aggressively
Rejected: 11 pages have interactions (terminal, wizard, matrix layout, slider with debounce) that blocks cannot express. Forcing AutoPage would degrade UX.

## References

- Source spec: `docs/superpowers/specs/2026-03-21-page-consolidation-design.md`
- ADR-483: UI Skill Architecture (provides `skills/dashboard/` home for shared components)
- ADR-260: MCP proxy catch-all routes

## Impact Manifest

```yaml
hubs_dissolved:
  - observe  # content promoted to command hub

pages_killed: 13  # logical duplicates + stubs + redirect pages
pages_added: 8    # splits from mega-pages + promoted observe content
pages_net: -2     # 58 → 56

shared_components_added:
  - skills/dashboard/components/shared/StatGrid.tsx
  - skills/dashboard/components/shared/ActionBar.tsx
  - skills/dashboard/components/shared/DataList.tsx
  - skills/dashboard/components/shared/DataTable.tsx
  - skills/dashboard/components/shared/StatusBadge.tsx
  - skills/dashboard/components/shared/SearchFilter.tsx
  - skills/dashboard/components/shared/PageHero.tsx
  - skills/dashboard/components/shared/CollapsibleSection.tsx
  - skills/dashboard/components/shared/NavLinkGrid.tsx
  - skills/dashboard/components/shared/LightControlCard.tsx
  - skills/dashboard/components/shared/SceneQuickButtons.tsx
  - skills/dashboard/components/shared/PageStates.tsx

loc_delta: -6100  # approximate
```
