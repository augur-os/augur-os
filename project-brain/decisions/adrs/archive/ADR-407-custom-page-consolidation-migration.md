---
status: Implemented
date: '2026-03-12'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- custom
- page
- consolidation
- migration
superseded_by: null
---

# ADR-407: Custom Page Consolidation — 103→27 Migration

**Related ADRs**: ADR-272 (Enhanced Auto-Pages), ADR-273 (Page Cleanup — Stub Removal), ADR-274 (Auto-Page Capability Enhancements)

## Context

ADR-273 removed 111 stub and low-quality pages. What remains are 103 customized pages — hand-written TSX files that serve as agentic apps within hubs. An audit of all 103 pages revealed that most contain AI-generated fluff (stats-grid + lazy-content patterns), mock data, or thin wrappers that SkillAutoPage (ADR-272) now handles natively. Only 27 pages solve unique problems that auto-pages cannot cover.

The 76 pages marked for conversion fall into four patterns:
- **11 empty wrappers/mocks** — zero custom logic, strictly less useful than auto-pages
- **26 stats-grid pages** — standard stat cards + data lists that auto-page sections already render
- **25 data-table/markdown pages** — tabular data or document browsers covered by DataSourceRenderer
- **14 merges/complex conversions** — pages that merge into siblings or need case-by-case evaluation

Each surviving custom page must justify its existence with a `problem_statement` in metadata, visible in the UI as a quality gate. If the subtitle feels vague, the page should be reconsidered.

### Current State

| Metric | Value |
|--------|-------|
| Total custom pages | 103 |
| Pages across hubs | 15 hubs |
| Unique agentic apps (KEEP) | 27 |
| Convertible to auto-pages | 76 |
| Reduction | 74% |

## Decision

### D1: Page Type Metadata

Every page declares its type in augur.yaml:

```yaml
contributions:
  pages:
    - path: /career/pipeline
      problem_statement: "Track job applications across pipeline stages with state transitions"
      page_type: custom
      state: mature
```

- **`page_type: custom`** — Hand-written TSX solving a unique problem. Requires `problem_statement`.
- **`page_type: auto`** — Rendered by `<SkillAutoPage>` from augur.yaml + vault + data sources. Uses skill `description` as subtitle.

### D2: Problem Statement UI

Display a subtitle under every page title in `HubHeaderSection`:

- **Font**: `text-xs`, `text-muted-foreground`
- **Position**: Below page title, above tab bar or content
- **Source**: `problem_statement` for custom pages, skill `description` for auto-pages

```tsx
{pageConfig?.problem_statement && (
  <p className="text-xs text-muted-foreground mt-1">
    {pageConfig.problem_statement}
  </p>
)}
```

### D3: The 27 Custom Pages Registry

| # | Hub | Page | Problem Statement |
|---|-----|------|------------------|
| 1 | Career | career/pipeline | Track job applications across pipeline stages with state transitions |
| 2 | Career | career/resume | AI-tailor resumes for specific jobs with master/tailored version management |
| 3 | Career | career/interview | Prep for interviews by company project with linked source files |
| 4 | Career | career/star | Build and refine STAR interview stories with AI coaching |
| 5 | Career | growth/knowledge | Map expertise domains and identify gaps with AI analysis |
| 6 | Career | growth/learning | Track courses and generate AI learning roadmaps |
| 7 | Career | growth/habits | Track daily career habits with streaks and completion rates |
| 8 | Career | growth/hardening | Generate knowledge reports from session activity with file upload |
| 9 | Career | growth/hardening/quiz | Interactive quiz with tier progression and 4 question types |
| 10 | Productivity | apple/voice | Record, import, and organize voice memos by folder |
| 11 | Productivity | reading-list | Manage articles with sortable columns, inline add, and read/unread state |
| 12 | Productivity | eisenhower/* | Manage tasks across Eisenhower quadrants (merged dynamic route) |
| 13 | Professional | project-dev/overview | Live dev dashboard with refresh and inline commit/pipeline previews |
| 14 | Professional | venture-augur/overview | Daily ops board with business positioning and five principles |
| 15 | Professional | venture-augur/market/competition | Competitive risk analysis with agent dispatch and comparison matrix |
| 16 | Professional | venture-augur/demo | Interactive product walkthrough (1305 LOC bespoke demo) |
| 17 | Consulting | client-ai-consulting/overview | AI consulting command center with live session stats |
| 18 | Consulting | client-smb-design/content-pipeline | Manage content lifecycle from draft to publish |
| 19 | Consulting | client-terminal-automation/terminal | Browser-based remote AS/400 terminal with credential gating |
| 20 | Consulting | client-hub/overview | Cross-engagement health dashboard with multi-endpoint normalization |
| 21 | Finance | finance/overview | Orchestrate balance sheet with dual-schema normalization |
| 22 | Finance | wealth/taxes | Calculate tax liability with category-based breakdowns |
| 23 | Lifestyle | lifestyle/overview | Cross-skill discovery and aggregate stats for lifestyle hub |
| 24 | Lifestyle | recipes/[id] | Display structured recipe with ingredients, instructions, and AI actions |
| 25 | Lifestyle | books/book-notes | Browse book notes with inline markdown edit and AI connections |
| 26 | Home | home-automation/overview | Room-based smart home control with live device polling |
| 27 | Admin | system-cleanup/overview | Category-based cleanup with terminal logging and progress tracking |

### D4: Wave-Based Conversion

Conversions are sequenced by pattern complexity, not by hub, to validate auto-page capabilities incrementally.

#### Wave 1 — Empty Wrappers & Mocks (11 pages)

Zero risk. No ADR-274 enhancements needed. Can proceed immediately.

**Pages:**
1. content/newsletters (mock)
2. content/books (mock)
3. content/notes (mock)
4. content/scripts (mock)
5. terminal-automation/overview (36 LOC wrapper)
6. terminal-automation/automations (36 LOC wrapper)
7. terminal-automation/settings (35 LOC wrapper)
8. apple/screenshots (dev, placeholder capture UI)
9. wearables/sense-overview (mock hero page)
10. wealth/overview (pure navigation)
11. reading (32 LOC wrapper — keep ReadingBoard as shared component)

**Also in Wave 1**: Add `problem_statement` and `page_type: custom` metadata to all 27 KEEP pages.

#### Wave 2 — Stats-Grid + Lazy-Content Pages (26 pages)

Requires ADR-274 Tier 1 (search, filtering, grouping, computed stats).

**Step 0 — Eisenhower Merge**: Merge 5 eisenhower pages (inbox, do-first, schedule, delegate, eliminate) into a single `[quadrant]` dynamic route. Net: 4 pages removed, 1 custom page remains as registry entry #12.

**Pages** (26, including 5 eisenhower pre-merge):
- lifestyle: recipes (list), movies, ideas, shopping, places, travel (6)
- eisenhower: inbox, do-first, schedule, delegate, eliminate → merge then convert (5)
- career: companies, hard-skills, content/posts (3)
- finance: accounts, transactions, budget, portfolio, crypto, goals, retirement (7)
- professional: projects, commits, codebase, pipelines, throughput (5)

#### Wave 3 — Data-Table / Markdown-Browser Pages (25 pages)

Requires ADR-274 Tier 1 + Tier 2 (view modes, progress bars, image gallery, modal detail views, charts).

**Pages:**
- career: growth/notes, growth/cheat-sheets, growth/hardening/history (3)
- finance: knowledge (1)
- consulting: knowledge, projects, services, assets, opportunities, showcase (6)
- professional: telemetry, market, market/positioning, market/comparison, analytics, gtm, sales, financials, investors, media, startups (11)
- admin: updater/releases (1)
- ai: knowledge/overview, ai_bridge/overview (2)
- dev: devops/overview (1)

#### Wave 4 — Merges & Complex Conversions (14 pages)

Requires all ADR-274 tiers. Case-by-case decisions.

**Merges** (5):
- consulting/sessions → into AI consulting overview
- consulting/showcase → into overview or convert
- consulting/smb-overview → into content-pipeline
- venture-augur/strategy → into venture overview or convert
- scraper/overview → simplify, keep modal wiring

**Complex conversions** (9):
- health/virtual-doctor (1)
- google-workspace: calendar, drive, docs (3)
- apple: notes, reminders, calendar, email (4)
- ai/scraper sub-pages (1)

**Cross-check**: 11 + 26 + 25 + 14 = 76 pages converted/merged. 103 − 76 = 27 remaining custom pages.

### D5: Conversion Process Per Page

1. **Audit**: Verify auto-page renders the skill's data correctly
2. **Extract**: Move reusable logic (CSV export, filter hooks) to shared utilities or API routes
3. **Delete**: Remove custom `page.tsx` from `plugins/{bundle}/skills/{skill}/augur/dashboard/`
4. **Update metadata**: Set `page_type: auto` in augur.yaml. Remove `problem_statement` and `page_type: custom` if present. Preserve all other augur.yaml keys (`description`, `data_sources`, `actions`, `data`) which the auto-page will use
5. **Verify**: Run mount copier, confirm auto-page generates at correct route
6. **Smoke test**: Load page in browser, confirm data appears, actions fire, no console errors

**For merges** (Wave 4): Before deleting source page, identify which custom elements migrate to the target page.

**Rollback**: If auto-page cannot cover a case, re-add page.tsx and file a follow-up to enhance auto-page capabilities.

## Consequences

### Positive

- **74% reduction** in custom pages (103 → 27) — dramatically less maintenance
- **Quality gate** — every custom page must justify its existence with a problem statement
- **Consistent UX** — converted pages get the same auto-page rendering as all other skills
- **Showcase clarity** — 27 pages that each solve one problem perfectly, not 103 pages of varying quality
- **Faster iteration** — auto-pages improve globally; custom pages improve individually

### Negative

- **Multi-wave execution** — Waves 2-4 depend on ADR-274 tier completion, creating a sequential dependency
- **Eisenhower merge complexity** — 5→1 page merge requires careful state/route consolidation
- **Wave 4 ambiguity** — merge targets for 5 pages require case-by-case judgment

### Neutral

- Overview pages are untouched (out of scope)
- The 27 KEEP pages stay as-is; only metadata is added
- Auto-page rendering quality depends on ADR-274 implementation quality

## Alternatives Considered

### Alternative 1: Hub-by-Hub Conversion

Convert all pages in one hub before moving to the next. Rejected because it mixes easy and hard pages within each hub, making it harder to validate auto-page capabilities incrementally.

### Alternative 2: Convert Everything at Once

Delete all 76 pages simultaneously after ADR-274 is fully implemented. Rejected because it creates a single high-risk change with no incremental validation. The wave approach validates each auto-page capability tier before depending on it for more pages.

### Alternative 3: Keep Low-Quality Pages, Only Convert Empty Wrappers

Only convert the 11 empty wrappers in Wave 1. Rejected because the 65 remaining low-quality pages add marginal value over auto-pages and create ongoing maintenance burden. The design spec audit confirmed these pages contain duplicate patterns already covered by SkillAutoPage.

## Testing

### T1: Metadata Validation
- All 27 KEEP pages have `problem_statement` and `page_type: custom` in augur.yaml
- All converted pages have `page_type: auto` in augur.yaml
- Problem statement is visible in UI via HubHeaderSection

### T2: Wave 1 Conversion
- Delete 11 pages, run mount copier, verify auto-page wrappers generate
- All 11 routes resolve (no 404s)
- No broken imports referencing deleted pages

### T3: Eisenhower Merge
- 5 pages → 1 `[quadrant]` dynamic route
- Each quadrant route renders correctly
- State transitions work across quadrants

### T4: Wave 2-3 Conversion
- Each converted page's auto-page shows data from the skill's data sources
- Search, filters, grouping work on converted pages (Wave 2)
- View modes, charts, modals work on converted pages (Wave 3)

### T5: Wave 4 Merges
- Merged pages retain all functionality from source pages
- No orphaned components or imports from deleted source pages

### T6: Build and Route Integrity
- `npm run build` passes after each wave
- All pre-existing tests pass (no regressions)
- No broken imports or missing routes
- Zero redirect shims (per CLAUDE.md rule 12)

### T7: Hub-by-Hub Counts
- Career: 19 → 9 custom pages
- Productivity: 18 → 3 custom pages
- Professional: 21 → 4 custom pages
- Consulting: 15 → 4 custom pages
- Finance: 11 → 2 custom pages
- Lifestyle: 10 → 3 custom pages
- Health: 2 → 0 custom pages
- Home: 1 → 1 custom page
- AI: 3 → 0 custom pages
- Admin: 2 → 1 custom page
- Dev: 1 → 0 custom pages

## Prerequisites

- **ADR-272** (Enhanced Auto-Pages): Implemented — required foundation
- **ADR-273** (Page Cleanup — Stub Removal): Implemented — stubs already removed
- **ADR-274** (Auto-Page Capability Enhancements): Must reach Implemented per tier before corresponding waves begin
  - **Wave 1** can proceed immediately
  - **Wave 2** requires ADR-274 Tier 1
  - **Wave 3** requires ADR-274 Tier 1 + Tier 2
  - **Wave 4** requires all ADR-274 tiers

## References

- Design spec: `docs/superpowers/specs/2026-03-12-pages-cleanup-design.md`
- ADR-274 implementation plan: `docs/superpowers/plans/2026-03-12-auto-page-enhancements.md`

## Impact Manifest

```yaml
impact:
  patterns_deprecated:
    - grep: "page_type.*custom.*content/newsletters|content/books|content/notes|content/scripts"
      replacement: "page_type: auto (Wave 1 conversion)"
    - grep: "44-line stub placeholder template"
      replacement: "Already removed by ADR-273"
  files_affected:
    - glob: "plugins/*/skills/*/augur/dashboard/page.tsx"
    - glob: "plugins/*/skills/*/augur/augur.yaml"
    - glob: "apps/dashboard/components/plugin/sections/HubHeaderSection.tsx"
  schema_changes:
    - field: "contributions.pages[].problem_statement"
      type: string
      required_when: "page_type == custom"
    - field: "contributions.pages[].page_type"
      type: enum
      values: [custom, auto]
```

## Hub-by-Hub Summary

| Hub | Before | After | Reduction | Notes |
|-----|--------|-------|-----------|-------|
| Career | 19 | 9 | 53% | Strongest retention — 9 agentic apps |
| Productivity | 18 | 3 | 83% | Eisenhower 5→1 merge, voice + reading-list kept |
| Professional | 21 | 4 | 81% | Demo (1305 LOC) is the flagship showcase |
| Consulting | 15 | 4 | 73% | Terminal + content-pipeline are unique |
| Finance | 11 | 2 | 82% | Only hub overview + taxes survive |
| Lifestyle | 10 | 3 | 70% | Hub overview, recipe detail, book-notes |
| Health | 2 | 0 | 100% | virtual-doctor + wearables → auto-pages |
| Home | 1 | 1 | 0% | home-automation kept (room-based control) |
| AI | 3 | 0 | 100% | knowledge, ai_bridge, scraper → auto-pages/merge |
| Admin | 2 | 1 | 50% | system-cleanup kept (terminal logging UX) |
| Dev | 1 | 0 | 100% | devops → auto-page |
| Observability | 0 | 0 | — | Already auto-page routed |
| **TOTAL** | **103** | **27** | **74%** | |

## Implementation Prompt

**Team name**: `adr-276-page-consolidation`

### Phase 1: Metadata & UI
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | implementer | low | Add `problem_statement` and `page_type: custom` to all 27 KEEP pages' augur.yaml | `plugins/*/skills/*/augur/augur.yaml` |
| 1.2 | implementer | low | Add problem statement subtitle to HubHeaderSection | `apps/dashboard/components/plugin/sections/HubHeaderSection.tsx` |
| 1.3 | validator | low | Verify all 27 pages show problem statement in UI | Browser validation |

### Phase 2: Wave 1 — Empty Wrappers
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | implementer | low | Delete 11 empty/mock page.tsx files | `plugins/*/skills/*/augur/dashboard/page.tsx` |
| 2.2 | implementer | low | Set `page_type: auto` in augur.yaml for deleted pages | `plugins/*/skills/*/augur/augur.yaml` |
| 2.3 | implementer | low | Run mount copier to generate SkillAutoPage wrappers | `apps/dashboard/scripts/mount/copier.ts` |
| 2.4 | validator | low | `npm run build` — verify no broken imports | `apps/dashboard/` |
| 2.5 | validator | low | Verify all 11 routes render auto-pages | Browser validation |

### Phase 3: Wave 2 — Stats-Grid Pages
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.0 | implementer | medium | Eisenhower merge: 5 pages → 1 `[quadrant]` dynamic route | `plugins/productivity/skills/eisenhower/augur/dashboard/` |
| 3.1 | implementer | low | Convert 26 stats-grid pages (audit, extract, delete, update metadata per D5) | `plugins/*/skills/*/augur/dashboard/page.tsx`, `plugins/*/skills/*/augur/augur.yaml` |
| 3.2 | implementer | low | Run mount copier | `apps/dashboard/scripts/mount/copier.ts` |
| 3.3 | validator | low | `npm run build` + test suite | `apps/dashboard/` |

### Phase 4: Wave 3 — Data-Table Pages
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | implementer | medium | Convert 25 data-table/markdown pages per D5 | `plugins/*/skills/*/augur/dashboard/page.tsx`, `plugins/*/skills/*/augur/augur.yaml` |
| 4.2 | implementer | low | Run mount copier | `apps/dashboard/scripts/mount/copier.ts` |
| 4.3 | validator | low | `npm run build` + test suite | `apps/dashboard/` |

### Phase 5: Wave 4 — Merges & Complex
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | implementer | high | Execute 5 page merges (migrate elements, then delete source pages) | `plugins/*/skills/*/augur/dashboard/` |
| 5.2 | implementer | medium | Convert 9 complex pages per D5 | `plugins/*/skills/*/augur/dashboard/page.tsx` |
| 5.3 | implementer | low | Run mount copier | `apps/dashboard/scripts/mount/copier.ts` |
| 5.4 | validator | low | `npm run build` + test suite | `apps/dashboard/` |

### Final Phase: Verification
| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run all tests, verify no regressions |
| V.2 | validator | low | `npm run build` passes |
| V.3 | validator | medium | Verify page counts match hub-by-hub summary (T7) |
| V.4 | validator | medium | Browser spot-check: 5 converted pages render auto-pages correctly |
| V.5 | architect | low | Verify zero redirect shims, zero orphaned imports |

### Completion Criteria
- [ ] 76 custom pages converted to auto-pages or merged
- [ ] 27 custom pages have `problem_statement` and `page_type: custom`
- [ ] Problem statement visible in HubHeaderSection
- [ ] Eisenhower 5→1 merge complete
- [ ] Zero broken routes
- [ ] Zero redirect shims
- [ ] All tests pass, build passes
- [ ] Hub-by-hub counts match summary table
