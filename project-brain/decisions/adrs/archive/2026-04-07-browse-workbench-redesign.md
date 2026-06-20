# Browse Workbench Redesign Implementation Plan

> **Implements**: ADR-540 — Browse Workbench Redesign
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `/browse` into a three-zone, power-user-biased workspace that improves discovery, metadata inspection, and action launch without regressing existing browse data flows.

**Architecture:** Keep the current browse data model and MCP wiring intact while restructuring the page into a left control rail, center results workspace, and right detail/actions panel. Promote search and pinned filters into stable regions, reduce repeated result-card clutter, and preserve category-specific layouts only where they materially outperform a denser default list presentation.

**Tech Stack:** Next.js App Router, React 19, TypeScript, Jest + Testing Library, Playwright, existing dashboard MCP hooks/state helpers

**Spec:** `~/Projects/Augur/docs/superpowers/specs/2026-04-07-browse-redesign-design.md`
**ADR:** `~/Projects/Au-vault/dev/adrs/ADR-540-browse-workbench-redesign.md`

---

### Task 1: Lock the Workspace Shell With Tests

**Files:**
- Create: `~/Projects/Augur/apps/dashboard/app/(views)/browse/page.test.tsx`
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/page.tsx`
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/useBrowseState.ts`

- [ ] **Step 1: Write the failing browse shell test**

```tsx
import { render, screen } from "@testing-library/react";
import BrowsePage from "./page";

jest.mock("./useBrowseState", () => ({
  useBrowseState: () => ({
    containerRef: { current: null },
    selectedSkill: "advisor",
    splitPercent: 52,
    handleDragStart: jest.fn(),
    handleKeyboardResize: jest.fn(),
    effectiveViewMode: "skills",
    activeCategory: { id: "skills", label: "Skills", viewLayout: "cards" },
    visibleCategories: [{ id: "skills", label: "Skills", group: "core" }],
    changeView: jest.fn(),
    lastIndexed: "2026-04-07T20:00:00Z",
    categoryFreshness: { skills: "2026-04-07T20:00:00Z" },
    refetch: jest.fn(),
    search: "",
    setSearch: jest.fn(),
    semanticMode: false,
    setSemanticMode: jest.fn(),
    semanticResults: [],
    setSemanticResults: jest.fn(),
    semanticLoading: false,
    semanticSearched: false,
    setSemanticSearched: jest.fn(),
    semanticError: null,
    handleSemanticSearch: jest.fn(),
    tagFilter: null,
    setTagFilter: jest.fn(),
    tagItems: [],
    hubFilter: null,
    setHubFilter: jest.fn(),
    hubItems: [],
    sourceFilter: null,
    setSourceFilter: jest.fn(),
    masterFilter: null,
    setMasterFilter: jest.fn(),
    masterClients: [],
    pluginFilter: null,
    setPluginFilter: jest.fn(),
    pluginNames: [],
    typeFilter: null,
    setTypeFilter: jest.fn(),
    typeItems: [],
    skillTagFilter: null,
    setSkillTagFilter: jest.fn(),
    skillTagItems: [],
    sortBy: "name-asc",
    setSortBy: jest.fn(),
    sorted: [],
    filtered: [],
    loading: false,
    error: null,
    notIndexed: false,
    truncated: false,
    totalCount: 225,
    visibleCount: 30,
    setVisibleCount: jest.fn(),
    pageSize: 30,
    handleRunMcp: jest.fn(),
    skillDetail: { id: "advisor", title: "advisor" },
    detailLoading: false,
    selectSkill: jest.fn(),
    closeDetail: jest.fn(),
  }),
}));

describe("BrowsePage layout shell", () => {
  it("renders navigation, results workspace, and detail panel landmarks", async () => {
    render(<BrowsePage />);
    expect(await screen.findByRole("heading", { name: "Browse" })).toBeInTheDocument();
    expect(screen.getByRole("separator", { name: "Resize panels" })).toBeInTheDocument();
    expect(screen.getByText("225 skills")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify the current page shape fails or is incomplete**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/page.test.tsx'
```

Expected: the test fails because the current shell does not yet expose the intended workbench structure cleanly enough for the new assertions.

- [ ] **Step 3: Refactor the page into explicit workspace regions**

Create named layout regions in `/browse/page.tsx` so the shell reads as a workbench instead of a single list column with an optional side detail.

```tsx
<div ref={state.containerRef} className="browse-workbench grid min-h-[calc(100dvh-2rem)] gap-3 lg:grid-cols-[18rem_minmax(0,1fr)_24rem]">
  <aside aria-label="Browse controls" className="rounded-2xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60">
    <BrowseControlRail {...railProps} />
  </aside>

  <section aria-label="Browse results workspace" className="min-w-0 rounded-2xl border border-[var(--border-color)] bg-[var(--bg-primary)]">
    <BrowseWorkspace {...workspaceProps} />
  </section>

  <aside aria-label="Selected item details" className="min-w-0 rounded-2xl border border-[var(--border-color)] bg-[var(--bg-primary)]">
    <BrowseDetailPanel detail={state.skillDetail} onClose={state.closeDetail} />
  </aside>
</div>
```

- [ ] **Step 4: Re-run the shell test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/page.test.tsx'
```

Expected: PASS

- [ ] **Step 5: Commit the shell restructure**

```bash
cd ~/Projects/Augur
git add apps/dashboard/app/\(views\)/browse/page.tsx apps/dashboard/app/\(views\)/browse/useBrowseState.ts apps/dashboard/app/\(views\)/browse/page.test.tsx
git commit -m "feat(browse): restructure browse into workbench shell"
```

---

### Task 2: Add Durable Workbench State for Left-Rail Controls

**Files:**
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Create: `~/Projects/Augur/apps/dashboard/app/(views)/browse/useBrowseState.test.ts`
- Modify: `~/Projects/Augur/apps/dashboard/lib/browse/types.ts`

- [ ] **Step 1: Write the failing state test for pinned filters and saved scopes**

```ts
import { renderHook, act } from "@testing-library/react";
import { useBrowseState } from "./useBrowseState";

describe("useBrowseState workbench controls", () => {
  it("keeps pinned filter state separate from secondary filters", () => {
    const { result } = renderHook(() => useBrowseState());
    act(() => {
      result.current.setHubFilter("brain");
      result.current.setTagFilter("A");
    });
    expect(result.current.hubFilter).toBe("brain");
    expect(result.current.tagFilter).toBe("A");
  });
});
```

- [ ] **Step 2: Run the state test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/useBrowseState.test.ts'
```

Expected: FAIL because the test file and any new workbench-facing state contracts do not exist yet.

- [ ] **Step 3: Add explicit workbench-facing state contracts**

Refactor `useBrowseState` so the page can render a stable left rail and center workspace without recomputing UI assumptions inline.

```ts
export interface BrowseState {
  pinnedFilters: {
    hub: string | null;
    quality: string | null;
    source: string | null;
  };
  secondaryFiltersOpen: boolean;
  setSecondaryFiltersOpen: React.Dispatch<React.SetStateAction<boolean>>;
  quickScopes: Array<{ id: string; label: string; count?: number }>;
  savedViews: Array<{ id: string; label: string; viewMode: ViewMode; filters: Record<string, string | null> }>;
  // existing fields...
}
```

Use derived values rather than new remote data. Keep the current query contract intact.

- [ ] **Step 4: Re-run the state test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/useBrowseState.test.ts'
```

Expected: PASS

- [ ] **Step 5: Commit the state-model changes**

```bash
cd ~/Projects/Augur
git add apps/dashboard/app/\(views\)/browse/useBrowseState.ts apps/dashboard/app/\(views\)/browse/useBrowseState.test.ts apps/dashboard/lib/browse/types.ts
git commit -m "feat(browse): add workbench state for persistent controls"
```

---

### Task 3: Replace the Flat Toolbar With a Search-First Left Rail + Workspace Header

**Files:**
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- Create: `~/Projects/Augur/apps/dashboard/app/(views)/browse/BrowseToolbar.test.tsx`
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/page.tsx`

- [ ] **Step 1: Write the failing toolbar test**

```tsx
import { render, screen } from "@testing-library/react";
import { BrowseToolbar } from "./BrowseToolbar";

describe("BrowseToolbar workbench header", () => {
  it("renders search as the dominant control and keeps secondary filters behind a toggle", () => {
    render(
      <BrowseToolbar
        activeCategory={{ id: "skills", label: "Skills", viewLayout: "cards" }}
        effectiveViewMode="skills"
        filteredCount={225}
        refetch={jest.fn()}
        search=""
        onSearchChange={jest.fn()}
        semanticMode={false}
        onToggleSemantic={jest.fn()}
        onSemanticSearch={jest.fn()}
        semanticLoading={false}
        semanticResults={[]}
        semanticSearched={false}
        semanticError={null}
        tagFilter={null}
        onTagFilterChange={jest.fn()}
        tagItems={[{ id: "all", label: "Quality: All" }, { id: "A", label: "A (12)" }]}
        hubFilter={null}
        onHubFilterChange={jest.fn()}
        hubItems={[{ id: "all", label: "Hub: All" }, { id: "brain", label: "brain (40)" }]}
        sourceFilter={null}
        onSourceFilterChange={jest.fn()}
        masterFilter={null}
        onMasterFilterChange={jest.fn()}
        masterClients={[]}
        pluginFilter={null}
        onPluginFilterChange={jest.fn()}
        pluginNames={[]}
        typeFilter={null}
        onTypeFilterChange={jest.fn()}
        typeItems={[]}
        skillTagFilter={null}
        onSkillTagFilterChange={jest.fn()}
        skillTagItems={[]}
        sortBy="name-asc"
        onSortChange={jest.fn()}
      />
    );

    expect(screen.getByRole("searchbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /filters/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the toolbar test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/BrowseToolbar.test.tsx'
```

Expected: FAIL because the current toolbar is still organized as a flat filter strip.

- [ ] **Step 3: Refactor the toolbar into a workspace header**

Keep the search input prominent and move only secondary filters behind a compact toggle. High-value browse context should render in the left rail via the page shell.

```tsx
<div className="flex flex-col gap-3 border-b border-[var(--border-color)] px-4 py-4">
  <div className="flex items-center gap-3">
    <div className="relative flex-1">
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
      <input
        id="browse-search"
        type="search"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        className="h-12 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-primary)] pl-10 pr-4 text-sm"
        placeholder="Search skills, pages, docs, actions..."
      />
    </div>
    <button type="button" className="inline-flex h-12 items-center gap-2 rounded-xl border border-[var(--border-color)] px-4">
      <SlidersHorizontal className="h-4 w-4" />
      Filters
    </button>
  </div>

  <div className="flex flex-wrap items-center gap-2">
    <QuickScopePill id="semantic" active={semanticMode} label="Semantic" onClick={onToggleSemantic} />
    <QuickScopePill id="fresh" active={false} label="Fresh only" onClick={() => onTagFilterChange("fresh")} />
    <QuickScopePill id="runnable" active={false} label="Runnable" onClick={() => onTagFilterChange("fire")} />
  </div>
</div>
```

- [ ] **Step 4: Re-run the toolbar test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/BrowseToolbar.test.tsx'
```

Expected: PASS

- [ ] **Step 5: Commit the toolbar redesign**

```bash
cd ~/Projects/Augur
git add apps/dashboard/app/\(views\)/browse/BrowseToolbar.tsx apps/dashboard/app/\(views\)/browse/BrowseToolbar.test.tsx apps/dashboard/app/\(views\)/browse/page.tsx
git commit -m "feat(browse): make search and filters workbench-first"
```

---

### Task 4: Densify Results and Centralize Actions in the Detail Panel

**Files:**
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- Modify: `~/Projects/Augur/apps/dashboard/components/shared/BrowseCard.tsx`
- Modify: `~/Projects/Augur/apps/dashboard/components/shared/BrowseDetailPanel.tsx`
- Create: `~/Projects/Augur/apps/dashboard/app/(views)/browse/BrowseContentGrid.test.tsx`

- [ ] **Step 1: Write the failing results/detail test**

```tsx
import { render, screen } from "@testing-library/react";
import { BrowseContentGrid } from "./BrowseContentGrid";

const items = [
  {
    id: "advisor",
    title: "advisor",
    description: "Optimize prompts and agent quality",
    hub: "studio",
    icon: "Box",
    metadata: { skillType: "skill", qualityTier: "C" },
  },
];

describe("BrowseContentGrid workbench results", () => {
  it("supports dense result rendering while preserving selection affordances", () => {
    render(
      <BrowseContentGrid
        effectiveViewMode="skills"
        activeCategory={{ id: "skills", label: "Skills", viewLayout: "cards" }}
        sorted={items as never}
        semanticMode={false}
        semanticResults={[]}
        semanticLoading={false}
        loading={false}
        error={null}
        refetch={jest.fn()}
        notIndexed={false}
        visibleCount={30}
        onLoadMore={jest.fn()}
        pageSize={30}
        selectedSkill="advisor"
        hubFilter={null}
        search=""
        onRunMcp={jest.fn()}
        onSelectSkill={jest.fn()}
      />
    );
    expect(screen.getByText("advisor")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the results test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/BrowseContentGrid.test.tsx'
```

Expected: FAIL or provide insufficient guarantees for dense result mode and reduced action duplication.

- [ ] **Step 3: Introduce a denser default result presentation**

Refactor the center workspace to prefer a compact list-style rendering for browse-heavy categories while preserving category-specific table/grouped-list layouts.

```tsx
const layout = activeCategory.viewLayout ?? "list";
const isDenseList = layout === "list" || effectiveViewMode === "skills";

return isDenseList ? (
  <BrowseDenseList
    items={displayItems}
    selectedId={selectedSkill}
    onSelect={onSelectSkill}
    onRunMcp={onRunMcp}
  />
) : (
  <BrowseCardGrid
    items={displayItems}
    selectedId={selectedSkill}
    onSelect={onSelectSkill}
    onRunMcp={onRunMcp}
  />
);
```

At the same time, remove low-value repeated actions from `BrowseCard` and move primary action emphasis into `BrowseDetailPanel`.

- [ ] **Step 4: Expand the detail panel into the primary inspect-and-act surface**

Add explicit metadata blocks and action grouping.

```tsx
<section className="space-y-4 p-4">
  <header className="space-y-2">
    <p className="text-xs uppercase tracking-[0.12em] text-[var(--text-muted)]">Selected item</p>
    <h2 className="text-xl font-semibold text-[var(--text-primary)]">{detail.title}</h2>
    <p className="text-sm text-[var(--text-secondary)]">{detail.summary}</p>
  </header>

  <BrowseMetadataGrid detail={detail} />
  <BrowseRelatedItems detail={detail} />
  <BrowseDetailActions detail={detail} />
</section>
```

- [ ] **Step 5: Re-run the dense-results test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/BrowseContentGrid.test.tsx'
```

Expected: PASS

- [ ] **Step 6: Commit the result/detail redesign**

```bash
cd ~/Projects/Augur
git add apps/dashboard/app/\(views\)/browse/BrowseContentGrid.tsx apps/dashboard/app/\(views\)/browse/BrowseContentGrid.test.tsx apps/dashboard/components/shared/BrowseCard.tsx apps/dashboard/components/shared/BrowseDetailPanel.tsx
git commit -m "feat(browse): densify results and centralize detail actions"
```

---

### Task 5: Rework Loading, Empty, Error, and Responsive States; Then Verify in Browser

**Files:**
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- Modify: `~/Projects/Augur/apps/dashboard/app/(views)/browse/page.tsx`
- Modify: `~/Projects/Augur/apps/dashboard/components/shared/BrowseCard.tsx` (or the shared empty/error state exports it hosts)
- Create: `~/Projects/Augur/apps/dashboard/app/(views)/browse/page.responsive.test.tsx`

- [ ] **Step 1: Write the failing state/responsive test**

```tsx
import { render, screen } from "@testing-library/react";
import BrowsePage from "./page";

describe("BrowsePage responsive and state handling", () => {
  it("renders useful empty-state guidance instead of a dead end", async () => {
    render(<BrowsePage />);
    expect(await screen.findByText(/try a different scope|relax filters|search/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the state/responsive test**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/page.responsive.test.tsx'
```

Expected: FAIL because the current empty/error patterns are not yet aligned with the new workbench model.

- [ ] **Step 3: Redesign the workbench states**

Update loading, empty, error, and not-indexed states so they belong to the three-zone workspace and guide the user toward recovery.

```tsx
<BrowseEmptyState
  title="No results in this scope"
  description="Try another category, relax a pinned filter, or switch on semantic search."
  suggestions={[
    { label: "Clear filters", onClick: clearAllFilters },
    { label: "Search all scopes", onClick: () => changeView("skills") },
  ]}
/>
```

Also add a mobile fallback that stacks controls and promotes detail into a bottom-sheet or overlay trigger.

- [ ] **Step 4: Re-run tests and build verification**

Run:
```bash
cd ~/Projects/Augur/apps/dashboard
pnpm test -- --runInBand 'app/(views)/browse/page.test.tsx' 'app/(views)/browse/useBrowseState.test.ts' 'app/(views)/browse/BrowseToolbar.test.tsx' 'app/(views)/browse/BrowseContentGrid.test.tsx' 'app/(views)/browse/page.responsive.test.tsx'
```

Then run:
```bash
cd ~/Projects/Augur
/dev-build
```

Expected: all Jest targets PASS, then the dashboard build succeeds through the lifecycle gate.

- [ ] **Step 5: Run browser verification**

Use Playwright or Chrome MCP against `http://localhost:3000/browse` and confirm:

- left rail, center workspace, and right panel all render with real data
- search and pinned filters narrow results without losing selection context
- right panel actions remain usable
- empty / error / not-indexed states are helpful rather than blank
- mobile-width behavior preserves the browse workflow

- [ ] **Step 6: Commit the state and verification pass**

```bash
cd ~/Projects/Augur
git add apps/dashboard/app/\(views\)/browse/page.tsx apps/dashboard/app/\(views\)/browse/BrowseContentGrid.tsx apps/dashboard/components/shared/BrowseCard.tsx apps/dashboard/app/\(views\)/browse/page.responsive.test.tsx
git commit -m "feat(browse): finish workbench states and responsive behavior"
```
