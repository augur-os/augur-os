# Page Consolidation Design — Component-Level Approach

## Summary

Rebuild the dashboard's 58 pages from the bottom up: decompose into atomic elements, extract shared components, kill logical duplicates, dissolve the observe hub, split tabbed mega-pages into focused standalone pages, and ensure every surviving page answers ONE clear user question.

**Approach:** Bottom-up (decompose → deduplicate → rebuild), not top-down (delete files).

**Primary wins:** ~3,400 net LOC reduction through 12 shared components replacing ~95 duplicated elements, plus clearer UX on every page.

## Current State

- **58 pages**, ~16,659 LOC across 6 hubs
- **~95 duplicated elements** — same UI patterns reimplemented independently across pages
- **11 logical duplicates** — same data/concept shown in multiple pages with different code
- **5 pages with no clear UX purpose** (grade C) — mega-pages or pure duplicates
- **11 pages with fuzzy UX purpose** (grade B) — mixed concerns that need focus
- **3 existing AutoPage users** (5% adoption)

## Phase 1: Extract 12 Shared Components

Build reusable components to replace the ~95 independently reimplemented patterns. Each component replaces multiple inline implementations across pages.

| Component | Replaces | Instances | LOC saved |
|-----------|----------|-----------|-----------|
| `<StatGrid>` | Inline stat card rows (label + value + icon + color) | 16 pages | ~800 |
| `<ActionBar>` | Button rows with loading states + error handling | 13 pages | ~400 |
| `<DataList>` | Vertical item lists with map() + styling | 15+ pages | ~500 |
| `<DataTable>` | Sortable/filterable tables with column headers | 6 pages | ~400 |
| `<StatusBadge>` | Color-mapped status indicators (each page has own color map) | 9 pages | ~150 |
| `<SearchFilter>` | Search input + filter controls + debounce logic | 6 pages | ~250 |
| `<PageHero>` | GlassCard header with icon + title + subtitle + actions | ~20 pages | ~600 |
| `<CollapsibleSection>` | ChevronUp/Down toggle + expand/collapse state | 15 sections | ~600 |
| `<NavLinkGrid>` | Navigation card grids linking to sub-pages | 5 pages | ~150 |
| `<LightControlCard>` | Light toggle + brightness slider (exact duplicate) | 2 pages | ~150 |
| `<SceneQuickButtons>` | Scene activation button grid (exact duplicate) | 2 pages | ~30 |
| `<PageStates>` | Loading skeleton + error banner + empty state | ~30 pages | ~600 |

**Total: ~4,630 LOC replaced by ~1,200 LOC of shared components = ~3,400 net LOC reduction.**

Component location: `apps/dashboard/components/shared/` (or extend existing component library).

### Implementation notes

- Each component is self-contained with its own types, no external dependencies beyond shadcn/ui primitives
- `<StatGrid>` takes `items: {label: string, value: string|number, icon?: LucideIcon, color?: string}[]`
- `<ActionBar>` takes `actions: {label: string, icon: LucideIcon, onClick: () => Promise<void>, loadingKey?: string}[]` — manages loading states internally
- `<DataTable>` takes `columns: Column[]`, `rows: T[]`, `sortable?: boolean`, `filterable?: boolean`, `expandable?: (row: T) => ReactNode`
- `<PageStates>` wraps children and handles loading/error/empty rendering based on data fetch state
- `<PageHero>` includes built-in refresh button support via `onRefresh` prop

## Phase 2: Kill Logical Duplicates

Same data shown in multiple places with different code. Keep ONE canonical page per concept, kill the rest.

| Kill | Canonical stays at | Data source | Reason |
|------|-------------------|-------------|--------|
| `observe/health` page | `daemon/health` | `get-daemon-status` MCP | Same MCP tool, different UI wrapper |
| `observe` overview widgets | `daemon` landing blocks | `get-daemon-status` MCP | Same data, duplicate stat cards |
| `daemon` IntegrationsTab | `ai_bridge/integrations` | `get-settings` MCP | Near-identical integration management UI |
| `ai_bridge` MemoryTab | `knowledge/memory` | memory workspace tools | Read-only duplicate — link to canonical instead |
| `updater` workflow section | `command/workflows` | `/api/admin/workflows` | Same API, embedded duplicate |
| `venture-augur/demo` skill scores embed | `adaptive/skill-scores` | `skill-score` MCP | Same MCP tool, same components embedded |
| `reading-list/reading-list` page | `reading-list` parent | articles API | Subsumed by parent superset |
| `contracts` page | (none) | hardcoded sample data | Stub — no real backend |
| `outreach` page | (none) | hardcoded sample data | Stub — no real backend |
| `knowledge` redirect page | Next.js rewrite | N/A | 9-line redirect — move to config |
| `daemon/metrics` redirect | Next.js rewrite | N/A | 5-line redirect — move to config |
| `apple` redirect page | Next.js rewrite | N/A | 8-line redirect — move to config |
| `ops-daemon` page | `daemon` landing | `get-daemon-status` MCP | 31-line thin wrapper around DaemonOverviewClient — absorbed into daemon landing |

**Observe hub dissolved entirely.** Original content promoted:
- `observe/logs` → `command/logs` (standalone page)
- `observe/sessions` → `command/sessions` (standalone page)
- Self-heal tab → `command/self-heal` (new standalone page)

## Phase 3: Split Tabbed Mega-Pages → Clean Standalone Pages

No page should have internal tab navigation. Each tab becomes its own focused page. Landing pages use `<NavLinkGrid>` + `<StatGrid>` summary blocks.

### daemon/page.tsx (1,081 LOC → landing ~80 LOC)

**Current:** 4 sections with tabs (DaemonStatus, SystemHealth, SelfHealSection, OpsControl)

**After:**
| New page | Content from | User question |
|----------|-------------|---------------|
| `daemon` (landing) | Summary blocks + NavLinkGrid | "Quick system overview + navigate to details" |
| `daemon/health` | Existing wrapper → full standalone | "Is my system healthy?" |
| `daemon/loops` | Existing | "What are my auto-loops doing?" |
| `daemon/loops/configuration` | Existing | "How are my loops configured?" |
| `daemon/notifications` | Existing | "What happened in my system?" |
| `daemon/services` | Existing | "What services are connected?" |
| `daemon/jobs` | Existing | "What jobs ran?" |
| `command/self-heal` | Extracted from daemon's SelfHealSection | "What did the system auto-fix?" |
| `command/logs` | Promoted from observe/logs | "What's in the runtime logs?" |
| `command/sessions` | Promoted from observe/sessions | "What sessions were saved?" |

### ai_bridge/page.tsx (1,565 LOC → landing ~60 LOC)

**Current:** 5 tabs (Overview, Agents, Tools, Integrations, Memory)

**After:**
| New page | Content from | User question |
|----------|-------------|---------------|
| `ai_bridge` (landing) | Summary blocks + NavLinkGrid | "My AI infrastructure at a glance" |
| `ai_bridge/agents` | Existing AgentsTab | "What agents are available?" |
| `ai_bridge/tools` | New page — MCP tool inventory (verify tab exists during implementation) | "What MCP tools can I use?" |
| `ai_bridge/integrations` | Extracted from IntegrationsTab (verify exists as tab or section) | "What services are integrated?" |
| Memory tab | KILLED — link to `knowledge/memory` | N/A |

### interview/page.tsx (337 LOC → 3 pages)

**Current:** 3 tabs (Projects, STAR Stories, Knowledge Topics)

**After:**
| New page | User question |
|----------|---------------|
| `interview/projects` | "What companies am I prepping for?" |
| `interview/stories` | "What STAR stories do I have?" |
| `interview/knowledge` | "What topics should I study?" |

### knowledge/memory (200 LOC → 3 pages)

**Current:** 3 collapsible sections (Workspace, API Profile, Daily Logs)

**After:**
| New page | User question |
|----------|---------------|
| `knowledge/memory/workspace` | "What's in my memory workspace?" |
| `knowledge/memory/profile` | "What does the system know about me?" |
| `knowledge/memory/logs` | "What happened today/this week?" |

## Phase 4: Focus Fuzzy Pages (Grade B → Grade A)

Pages with mixed concerns that need simplification:

| Page | Problem | Fix |
|------|---------|-----|
| `venture-augur` (680 LOC) | Inlines pipeline + dev stats that have their own pages | Reduce to dashboard landing: key metrics + NavLinkGrid. Remove inline VenturePipelineSection and ProjectDevSection. |
| `home-automation` (357 LOC) | Duplicates light controls from lighting page | Make landing page: StatGrid (counts) + NavLinkGrid (lighting, scenes). Remove inline light cards. |
| `updater` (546 LOC) | Embeds workflow section | Remove WorkflowsSection (canonical at `/command/workflows`). Keep update status + recent activity only. |
| `venture-augur/demo` (71 LOC) | Embeds skill scores from adaptive page | Remove TierDistribution/WeightConfig/SkillScoreTable embed. Keep DemoCatalog only. Link to `/adaptive/skill-scores`. |
| `apple/overview` (90 LOC) | Mostly placeholder cards | Convert to clean NavLinkGrid landing page. |
| `factory` (420 LOC) | Mixes plugin overview + validator | Keep as vertical sections (both relate to plugin quality). Rebuild with shared components. |
| `design` (318 LOC) | Mixes audit + page builder grid | Move page grid to page-builder page. Keep audit as standalone design/audit page. |
| `learning` (200+ LOC) | 5 collapsible sections | Keep as vertical sections with shared CollapsibleSection component. |
| `workbench` (928 LOC) | 3 unrelated domains | Keep as-is for now (928 LOC is manageable). If user wants split later, break into advisor/developer/devops. |
| `gtm` (571 LOC) | 4 tabs | Remove tab navigation. Keep as vertical sections (user's decision). |
| `daemon/jobs` | Overlaps with loops journal | Keep but clarify distinction — jobs shows artifacts/results, loops shows execution status. |

## Phase 5: Convert to AutoPage Where Possible

20 pages can be fully replaced by AutoPage + block YAML — no custom page.tsx needed. 14 more are partial candidates (blocks handle data display, custom code stays for interactive bits). 11 must remain fully custom.

### Full AutoPage replacement (20 pages → 13-line wrappers + YAML)

Each page becomes `<SkillAutoPage skillId="..." />` with blocks declared in the skill's `augur.yaml`.

| Page | Block types needed |
|------|--------------------|
| daemon (landing) | stat-grid + card-grid (nav links) |
| daemon/health | stat-grid + data-table |
| daemon/notifications | data-list with filters + row actions (dismiss) |
| daemon/services | data-table with status badges |
| daemon/jobs | data-list or activity-feed |
| command/self-heal | data-list with filters |
| command/sessions | data-list with row actions (copy) |
| workflows | data-list or card-grid |
| updater/plugins | card-grid with row actions (restore) |
| ai_bridge (landing) | stat-grid + card-grid (nav links) |
| knowledge/memory/workspace | data-list with row actions (open-file) |
| knowledge/memory/profile | stat-grid + data-list |
| reading-list | data-table with search + filters + row actions (toggle-read) |
| venture-augur (landing) | stat-grid + card-grid (nav links) |
| interview/stories | card-grid with filters |
| interview/knowledge | data-list with status badges |
| resume | card-grid with row actions |
| home-automation (landing) | stat-grid + card-grid (nav links) |
| home-automation/scenes | card-grid with row actions (activate-scene) |
| apple/overview (landing) | card-grid (static nav links) |

**Pre-requisite per page:** Verify MCP tool exists for each block's `dataSource.mcpTool` and returns the expected shape. Create missing tools as pre-work.

### Partial AutoPage (14 pages — blocks + custom code)

These pages have block-expressible elements mixed with custom interactions that blocks can't handle. Convert what's possible to blocks; keep custom code for the rest. Pages shrink from ~200-300 LOC to ~80-120 LOC.

| Page | Block-expressible | Custom blocker |
|------|------------------|----------------|
| daemon/loops | stat-grid, data-table (journal) | Loop cards with budget bars, probation, category toggles |
| command/logs | data-list with filters | Log streaming, syntax highlighting |
| updater | stat-grid, activity-feed | Update action triggers system ops with progress |
| ai_bridge/agents | card-grid, stat-grid | Config modal with form validation |
| ai_bridge/tools | data-table with editable fields | Preset management (multi-step) |
| ai_bridge/integrations | data-list with row actions | Configure action opens complex form |
| knowledge/memory/logs | calendar, markdown viewer | Calendar click → load log (cross-block state) |
| knowledge/index | stat-grid, data-table | Rebuild triggers long-running op with progress |
| interview/projects | data-list | Two-panel layout (sidebar + detail) |
| pipeline | stat-grid, data-table | Custom score bars, complex grouping |
| attention | 3x data-list with row actions | Tier-based layout with auto-resolve |
| health | stat-grid, 3x data-list | Custom SeverityBadge color logic |
| finance | stat-grid, 2x data-list | Client-side tax computation (must move to MCP tool) |
| learning | 5x collapsible sections | Dynamic imports, action dispatch per section |

### Keep fully custom (11 pages)

Blocks cannot express these — interactive workflows, custom layouts, or non-data-display UX.

| Page | Reason |
|------|--------|
| daemon/loops/config | Dynamic config panel with arbitrary key-value pairs |
| system-cleanup | Multi-step stateful workflow: scan → select → confirm → execute → terminal |
| gtm | Masonry grid, phase timeline with week tracking, content calendar |
| learning/quiz | Quiz state machine with 4 question types, tier advancement |
| competition | Risk gauge, factor analysis, async competitor updates |
| eisenhower | 2x2 matrix layout with inline add per quadrant |
| eisenhower/[quadrant] | Move-between-quadrants dropdown + AI prioritize |
| file-manager | Recursive file tree + resizable editor panes |
| home-automation/lighting | Brightness slider with optimistic updates + debounce |
| workbench | 3 complex domains with forms, audits, refactoring tools |
| terminal | Interactive terminal emulator |

## Phase 6: Rebuild Remaining Pages with Shared Components

The 14 partial pages and 11 custom pages get rebuilt using Phase 1's shared components (PageHero, PageStates, StatGrid, etc.) to eliminate inline boilerplate. This is the final pass — each page as an independent PR.

## Result

### Page count

| Hub | Before | After | Change |
|-----|--------|-------|--------|
| command | 17 | 14 | -3 (kill: observe×2, ops-daemon, daemon/metrics = -4; new: self-heal = +1) |
| brain | 7 | 9 | +2 (kill: knowledge redirect, reading-list/reading-list = -2; new: ai_bridge/tools, ai_bridge/integrations = +2; memory 1→3 = +2) |
| career | 12 | 12 | 0 (kill: contracts, outreach = -2; interview 1→3 = +2) |
| life | 14 | 13 | -1 (kill: apple redirect = -1) |
| studio | 6 | 6 | 0 |
| adaptive | 2 | 2 | 0 |
| **Total** | **58** | **56** | **-2** |

Page COUNT stays nearly the same — the win is not fewer files but:

### Quality metrics

| Metric | Before | After |
|--------|--------|-------|
| Custom LOC per page (avg) | 287 | ~80 |
| Pages with internal tabs | 7 | 0 |
| Logical duplicates | 11 concepts × 2-6 views | 0 |
| Shared components | 0 | 12 |
| AutoPage pages | 3 (5%) | 23 (41%) |
| Fully custom pages | 55 | 11 (20%) |
| Pages graded A (clear UX) | 23 | ~50 |
| Pages graded B/C (fuzzy/broken) | 16 | ~8 (B only, no C) |
| Duplicated UI elements | ~95 | 0 |
| Estimated total LOC reduction | — | ~6,100 (shared components + AutoPage conversions) |

## Pages Unchanged (Phase 6 Rebuild Only)

These pages have clear UX purpose (grade A). Pages listed in Phase 5 as "full replace" get AutoPage conversion. Remaining pages receive Phase 6 rebuild with shared components only.

| Hub | Page | User question |
|-----|------|---------------|
| command | system-cleanup | "How do I free up disk space?" |
| command | workflows | "What workflows are available?" |
| command | updater/plugins | "What plugins are installed?" |
| brain | knowledge/index | "Is my search index working?" |
| brain | reading-list | "What should I read?" |
| career | pipeline | "Where am I in my job search?" |
| career | resume | "What resumes do I have?" |
| career | competition | "How do I compare to competitors?" |
| career | learning/quiz | "Test my knowledge" |
| career | venture-augur/strategy | "What's my strategic plan?" (AutoPage) |
| life | attention | "What needs my attention right now?" |
| life | eisenhower | "What should I prioritize?" |
| life | eisenhower/[quadrant] | "Manage tasks in this quadrant" |
| life | file-manager | "Browse and edit my files" |
| life | home-automation/lighting | "Control my lights" |
| life | home-automation/scenes | "Activate a scene" |
| life | apple/voice | "My voice memos" |
| life | health | "My health data" |
| life | finance | "My financial overview" |
| life | wealth | "My investment portfolio" (AutoPage) |
| life | lifestyle/recipes/[id] | "View this recipe" |
| studio | terminal | "Remote terminal access" |
| adaptive | auto-vault-hygiene | "Is my vault healthy?" |
| adaptive | skill-scores | "How are my skills scoring?" |

## Non-Page Files

Pages in `plugins/ui/pages/` are accompanied by ~37,500 LOC of component, tab, and client files (e.g., `components/*.tsx`, `tabs/*.tsx`, `*Client.tsx`). When mega-pages are split (Phase 3) and pages rebuilt (Phase 5), these supporting files are migrated alongside their parent pages:

- **Observe dissolution:** Tab files (`OverviewTab.tsx`, `HealthTab.tsx`, `SelfHealTab.tsx`, `SessionsTab.tsx`, `LogsTabView.tsx`, `MarkersTab.tsx`, `WorkflowSuiteCard.tsx`, ~1,826 LOC) are either promoted into standalone pages or killed alongside their duplicate wrappers.
- **Daemon split:** Component files (`DaemonClient.tsx`, `LoopsView.tsx`, `DaemonLoopsClient.tsx`, `NotificationsView.tsx`, etc.) stay with their respective promoted pages.
- **AI bridge split:** Tab components become the content of their respective standalone pages.

Phase 5 rebuild applies shared components to both page files and their supporting component files.

## Execution Sequence

1. **Phase 1** — Build 12 shared components (no pages change yet, purely additive)
2. **Phase 2** — Kill logical duplicates + dissolve observe (delete code, add rewrites)
3. **Phase 3** — Split mega-pages (daemon, ai_bridge, interview, memory)
4. **Phase 4** — Focus fuzzy pages (trim embedded duplicates from venture-augur, updater, home-automation, demo)
5. **Phase 5** — Convert 20 pages to AutoPage + block YAML (verify MCP tools first, then replace page.tsx)
6. **Phase 6** — Rebuild remaining 25 pages (14 partial + 11 custom) with shared components

Each phase is a separate branch/PR. Phase 1 must complete before phases 3-6 (shared components needed). Phase 2 is independent and can run in parallel with Phase 1. Phase 5 (AutoPage) can run in parallel with Phase 6 (rebuild).

## Verification

- `pnpm build` gate on every phase
- Screenshot baseline before Phase 5 (rebuild)
- Visual comparison after each page rebuild — same data sections, cleaner layout
- Navigation flow testing after Phase 3 (split pages) — old URLs rewrite correctly
- No `@ts-ignore`, `eslint-disable`, or workarounds

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Shared components don't cover all variation | Medium | Build components with flexible props; allow page-specific overrides |
| Splitting mega-pages breaks cross-section state | Low | Audit shared state during split; extract to hooks if needed |
| Observe dissolution breaks bookmarks | Low | Next.js rewrites preserve all old URLs |
| Phase 5 rebuild changes UX unintentionally | Medium | Screenshot comparison per page; user review of each rebuilt page |
| 12 components is too many to build at once | Low | Prioritize by frequency: StatGrid, PageHero, PageStates first (cover most pages) |

## Design Decisions

1. **Bottom-up, not top-down** — Decompose pages into elements, find duplicates, rebuild. Not "which files to delete."
2. **No internal tabs** — Every concern gets its own clean page with one clear user question.
3. **Observe dissolved** — Every observe sub-page duplicates canonical data elsewhere. Only logs, sessions, and self-heal are original content — promoted to standalone pages.
4. **GTM stays as one page** (vertical sections, no tabs) — user decision.
5. **Interview splits into 3** — user decision.
6. **Knowledge/memory splits into 3** — user decision.
7. **Workbench stays as-is** (928 LOC) — manageable size, split later if needed.
8. **Page count stays ~same** — the win is code quality, UX clarity, and eliminated duplication, not fewer files.
