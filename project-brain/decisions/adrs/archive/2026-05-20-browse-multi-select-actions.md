# Browse Multi-Select Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user enter a select mode on any Browse tab, pick several cards, and hand the selected set to the interactive floating chat — via a generic "Send to chat" plus curated presets (Summarize, Sweep).

**Architecture:** A small zustand selection store holds the selected `BrowseItem` objects (full objects, so dispatch survives filter/search changes). The `BrowseDisplayRenderer` reads the store directly and gives each card-shell three new props (`selectionMode`, `isMultiSelected`, `onToggleMultiSelect`); in select mode a transparent overlay button turns the whole card into a toggle, and a checkbox indicator shows state. A presentational `SelectionActionBar` (sticky, rendered by the page) shows the count and the actions whose `appliesTo(viewMode)` is true; each action builds an `initialPrompt` and dispatches through the existing `openChat`-backed `handleTriggerPrompt` (ADR-748). Sweep reuses `buildSweepCandidates` + `hygiene-create-selection` + `buildSweepPrompt`.

**Tech Stack:** Next.js (App Router) dashboard, React client components, zustand, TypeScript, Jest + React Testing Library (jsdom), Tailwind CSS variables.

**Spec:** `docs/superpowers/specs/2026-05-20-browse-multi-select-actions-design.md`

---

## Conventions for this plan

- **Test runner:** Jest config at `apps/dashboard/jest.config.js`; tests live in repo-root `tests/dashboard/`; `@/` maps to `apps/dashboard/`. Run a single test file during the TDD loop with:
  `cd apps/dashboard && npx jest <relative-test-path> --silent`
  (Single-file `npx jest` is the tight TDD loop only. **Final verification** for any dashboard build/lint/page-load goes through the dashboard slash commands — `/dev build`, `/dev debug`, and the lint loop — never raw `pnpm dev`/`pnpm test`, per Augur rules 19/29.)
- **Zustand store test pattern** (matches `tests/dashboard/stores/chatStore.test.ts`): import the store, `useStore.getState()` to read/mutate, `renderHook(() => useStore())` + `act()` for reactive reads, and reset in `beforeEach`.
- **Component test pattern** (matches `tests/dashboard/browse/BrowseCardAction.test.tsx`): `@jest-environment jsdom`, `render`/`screen`/`fireEvent`, mock `next/navigation` and `sonner` where imported.
- **Commit after each task.** Branch is `feat/browse-multi-select-actions` (already created).

---

## File Structure

**New files**

| File | Responsibility |
|---|---|
| `apps/dashboard/lib/browse/useBrowseSelection.ts` | Zustand store: select-mode flag + selected `BrowseItem` objects keyed by id; toggle / select-all-visible / clear / reset. |
| `apps/dashboard/lib/browse/selectionPrompt.ts` | Pure builder turning selected items + viewMode (+ optional intent) into the chat `initialPrompt` string. |
| `apps/dashboard/lib/browse/selectionActions.ts` | Action registry (`send-to-chat`, `summarize`, `sweep`) with `appliesTo` + `build`; `selectionActionsForViewMode`. |
| `apps/dashboard/components/shared/SelectionActionBar.tsx` | Presentational sticky bar: count, applicable action buttons, Select-all-visible, Clear. |
| `tests/dashboard/browse/useBrowseSelection.test.ts` | Store unit tests. |
| `tests/dashboard/browse/selectionPrompt.test.ts` | Prompt-builder unit tests. |
| `tests/dashboard/browse/selectionActions.test.ts` | Registry unit tests (Sweep mocks `mcpCall`). |
| `tests/dashboard/browse/BrowseCardSelection.test.tsx` | Card-shell + list-row select-mode behavior. |
| `tests/dashboard/browse/SelectionActionBar.test.tsx` | Action-bar rendering + callbacks. |
| `docs/adrs/ADR-<next>-browse-multi-select-actions.md` | Records the pattern. |

**Modified files**

| File | Change |
|---|---|
| `apps/dashboard/components/shared/BrowseCardShell.tsx` | Add selection props + overlay toggle + checkbox indicator. |
| `apps/dashboard/components/shared/BrowseListRowCard.tsx` | Same for list rows. |
| `apps/dashboard/app/(views)/browse/BrowseDisplayRenderer.tsx` | Read selection store; pass new props to shells. |
| `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx` | Add `Select`/`Done` toggle button. |
| `apps/dashboard/app/(views)/browse/page.tsx` | Wire toggle, reset on tab change, render `SelectionActionBar`, dispatch. |
| `docs/superpowers/specs/2026-05-20-browse-multi-select-actions-design.md` | Flip `status: draft` → `accepted` (final task). |

---

## Task 1: Selection store (`useBrowseSelection`)

**Files:**
- Create: `apps/dashboard/lib/browse/useBrowseSelection.ts`
- Test: `tests/dashboard/browse/useBrowseSelection.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { act, renderHook } from "@testing-library/react";
import { useBrowseSelection } from "@/lib/browse/useBrowseSelection";
import type { BrowseItem } from "@/lib/browse/types";

function item(id: string, overrides: Partial<BrowseItem> = {}): BrowseItem {
  return {
    id,
    title: `Title ${id}`,
    description: "",
    hub: "brain",
    primaryAction: { label: "Open", type: "open-file", target: `notes/${id}.md` },
    path: `notes/${id}.md`,
    ...overrides,
  };
}

describe("useBrowseSelection", () => {
  beforeEach(() => {
    act(() => useBrowseSelection.getState().reset());
  });

  it("enters and exits select mode, clearing on exit", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.enter());
    act(() => result.current.toggle(item("a")));
    expect(result.current.selectionMode).toBe(true);
    expect(result.current.selected.size).toBe(1);
    act(() => result.current.exit());
    expect(result.current.selectionMode).toBe(false);
    expect(result.current.selected.size).toBe(0);
  });

  it("toggle adds then removes an item by id", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.toggle(item("a")));
    expect(result.current.isSelected("a")).toBe(true);
    act(() => result.current.toggle(item("a")));
    expect(result.current.isSelected("a")).toBe(false);
  });

  it("selectAllVisible merges without duplicating", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.toggle(item("a")));
    act(() => result.current.selectAllVisible([item("a"), item("b"), item("c")]));
    expect(result.current.selected.size).toBe(3);
    expect(result.current.selectedItemList().map((i) => i.id).sort()).toEqual(["a", "b", "c"]);
  });

  it("clear empties selection but keeps select mode; reset clears both", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.enter());
    act(() => result.current.selectAllVisible([item("a"), item("b")]));
    act(() => result.current.clear());
    expect(result.current.selected.size).toBe(0);
    expect(result.current.selectionMode).toBe(true);
    act(() => result.current.toggle(item("a")));
    act(() => result.current.reset());
    expect(result.current.selected.size).toBe(0);
    expect(result.current.selectionMode).toBe(false);
  });

  it("toggleSelectionMode turns on, then off and clears", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.toggleSelectionMode());
    expect(result.current.selectionMode).toBe(true);
    act(() => result.current.toggle(item("a")));
    act(() => result.current.toggleSelectionMode());
    expect(result.current.selectionMode).toBe(false);
    expect(result.current.selected.size).toBe(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/useBrowseSelection.test.ts --silent`
Expected: FAIL — `Cannot find module '@/lib/browse/useBrowseSelection'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// apps/dashboard/lib/browse/useBrowseSelection.ts
import { create } from "zustand";
import type { BrowseItem } from "@/lib/browse/types";

export interface BrowseSelectionState {
  selectionMode: boolean;
  /** Selected items keyed by id. Full objects are stored so a later dispatch
   * still has the data even if the item scrolled out of the filtered set. */
  selected: Map<string, BrowseItem>;

  enter: () => void;
  exit: () => void;
  toggleSelectionMode: () => void;
  toggle: (item: BrowseItem) => void;
  selectAllVisible: (items: BrowseItem[]) => void;
  clear: () => void;
  reset: () => void;

  isSelected: (id: string) => boolean;
  selectedItemList: () => BrowseItem[];
  selectedCount: () => number;
}

export const useBrowseSelection = create<BrowseSelectionState>((set, get) => ({
  selectionMode: false,
  selected: new Map(),

  enter: () => set({ selectionMode: true }),
  exit: () => set({ selectionMode: false, selected: new Map() }),
  toggleSelectionMode: () =>
    set((s) =>
      s.selectionMode
        ? { selectionMode: false, selected: new Map() }
        : { selectionMode: true },
    ),

  toggle: (item) =>
    set((s) => {
      const next = new Map(s.selected);
      if (next.has(item.id)) next.delete(item.id);
      else next.set(item.id, item);
      return { selected: next };
    }),

  selectAllVisible: (items) =>
    set((s) => {
      const next = new Map(s.selected);
      for (const item of items) next.set(item.id, item);
      return { selected: next };
    }),

  clear: () => set({ selected: new Map() }),
  reset: () => set({ selectionMode: false, selected: new Map() }),

  isSelected: (id) => get().selected.has(id),
  selectedItemList: () => Array.from(get().selected.values()),
  selectedCount: () => get().selected.size,
}));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/useBrowseSelection.test.ts --silent`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/useBrowseSelection.ts tests/dashboard/browse/useBrowseSelection.test.ts
git commit -m "feat(browse): selection store for multi-select"
```

---

## Task 2: Prompt builder (`selectionPrompt`)

**Files:**
- Create: `apps/dashboard/lib/browse/selectionPrompt.ts`
- Test: `tests/dashboard/browse/selectionPrompt.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { buildSelectionPrompt } from "@/lib/browse/selectionPrompt";
import type { BrowseItem } from "@/lib/browse/types";

function item(id: string, overrides: Partial<BrowseItem> = {}): BrowseItem {
  return {
    id,
    title: `Title ${id}`,
    description: "",
    hub: "brain",
    primaryAction: { label: "Open", type: "open-file", target: `notes/${id}.md` },
    path: `notes/${id}.md`,
    ...overrides,
  };
}

describe("buildSelectionPrompt", () => {
  it("renders a numbered list with a known tab label and default intent", () => {
    const prompt = buildSelectionPrompt([item("a"), item("b")], "notes");
    expect(prompt).toContain("Selected 2 items from Browse · Notes:");
    expect(prompt).toContain('1. "Title a" — notes/a.md');
    expect(prompt).toContain('2. "Title b" — notes/b.md');
    expect(prompt.trimEnd().endsWith("<describe what you'd like to do with these>")).toBe(true);
  });

  it("uses singular wording for one item", () => {
    expect(buildSelectionPrompt([item("a")], "notes")).toContain("Selected 1 item from Browse");
  });

  it("prefers metadata source_path, then falls back to id when no path exists", () => {
    const withMeta = item("a", { path: undefined, metadata: { source_path: "/abs/a.md" } });
    const noPath = item("b", { path: undefined });
    const prompt = buildSelectionPrompt([withMeta, noPath], "documents");
    expect(prompt).toContain('1. "Title a" — /abs/a.md');
    expect(prompt).toContain('2. "Title b" — b');
  });

  it("uses a custom intent and falls back to the raw viewMode label", () => {
    const prompt = buildSelectionPrompt([item("a")], "skills", { intent: "Do the thing." });
    expect(prompt).toContain("from Browse · skills:");
    expect(prompt.trimEnd().endsWith("Do the thing.")).toBe(true);
  });

  it("collapses whitespace in titles so each item stays on one line", () => {
    const messy = item("a", { title: "Line one\nLine  two" });
    expect(buildSelectionPrompt([messy], "notes")).toContain('1. "Line one Line two" — notes/a.md');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/selectionPrompt.test.ts --silent`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```ts
// apps/dashboard/lib/browse/selectionPrompt.ts
import type { BrowseItem, ViewMode } from "@/lib/browse/types";

const VIEW_MODE_LABELS: Partial<Record<ViewMode, string>> = {
  notes: "Notes",
  documents: "Documents",
  wiki: "Wiki",
  pages: "Pages",
};

function itemReference(item: BrowseItem): string {
  const ref =
    item.metadata?.source_path ||
    item.metadata?.filePath ||
    item.path ||
    item.id;
  const title = (item.title || item.id).replace(/\s+/g, " ").trim();
  return `"${title}" — ${ref}`;
}

export interface SelectionPromptOptions {
  /** Trailing instruction line. Omitted → a placeholder invites the user to type. */
  intent?: string;
}

export function buildSelectionPrompt(
  items: BrowseItem[],
  viewMode: ViewMode,
  options: SelectionPromptOptions = {},
): string {
  const label = VIEW_MODE_LABELS[viewMode] ?? viewMode;
  const noun = items.length === 1 ? "item" : "items";
  const header = `Selected ${items.length} ${noun} from Browse · ${label}:`;
  const lines = items.map((item, i) => `${i + 1}. ${itemReference(item)}`);
  const intent = options.intent ?? "<describe what you'd like to do with these>";
  return [header, ...lines, "", intent].join("\n");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/selectionPrompt.test.ts --silent`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/selectionPrompt.ts tests/dashboard/browse/selectionPrompt.test.ts
git commit -m "feat(browse): selection prompt builder"
```

---

## Task 3: Action registry (`selectionActions`)

**Files:**
- Create: `apps/dashboard/lib/browse/selectionActions.ts`
- Test: `tests/dashboard/browse/selectionActions.test.ts`

Note: `buildSweepCandidates(mode, items)` accepts `mode: ViewMode | "sources"` and returns `{ source_tab, targets, unsupported }`; `buildSweepPrompt(input)` takes `{ sourceTab, selectionId, targetCount, refusalCount, filterSummary }`. Both already exist in `apps/dashboard/lib/browse/`.

- [ ] **Step 1: Write the failing test**

```ts
import {
  SELECTION_ACTIONS,
  selectionActionsForViewMode,
} from "@/lib/browse/selectionActions";
import type { BrowseItem } from "@/lib/browse/types";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));
import { mcpCall } from "@/lib/mcp/client";

function noteItem(id: string): BrowseItem {
  return {
    id,
    title: `Note ${id}`,
    description: "",
    hub: "brain",
    primaryAction: { label: "Open", type: "open-file", target: `notes/${id}.md` },
    path: `notes/${id}.md`,
    metadata: { source_path: `notes/${id}.md`, journey_category: "sources", source_root: "private" },
  };
}

describe("selectionActionsForViewMode", () => {
  it("offers send-to-chat everywhere", () => {
    for (const vm of ["notes", "skills", "api-routes", "documents"] as const) {
      expect(selectionActionsForViewMode(vm).map((a) => a.id)).toContain("send-to-chat");
    }
  });

  it("offers summarize on content tabs only", () => {
    expect(selectionActionsForViewMode("notes").map((a) => a.id)).toContain("summarize");
    expect(selectionActionsForViewMode("documents").map((a) => a.id)).toContain("summarize");
    expect(selectionActionsForViewMode("skills").map((a) => a.id)).not.toContain("summarize");
  });

  it("offers sweep on notes and pages only", () => {
    expect(selectionActionsForViewMode("notes").map((a) => a.id)).toContain("sweep");
    expect(selectionActionsForViewMode("pages").map((a) => a.id)).toContain("sweep");
    expect(selectionActionsForViewMode("documents").map((a) => a.id)).not.toContain("sweep");
  });
});

describe("send-to-chat / summarize build", () => {
  const send = SELECTION_ACTIONS.find((a) => a.id === "send-to-chat")!;
  const summarize = SELECTION_ACTIONS.find((a) => a.id === "summarize")!;

  it("send-to-chat bundles items with the default placeholder", async () => {
    const result = await send.build([noteItem("a")], "notes");
    expect(result.initialPrompt).toContain("Selected 1 item from Browse · Notes:");
    expect(result.initialPrompt).toContain("<describe what you'd like to do with these>");
  });

  it("summarize injects a synthesis instruction", async () => {
    const result = await summarize.build([noteItem("a"), noteItem("b")], "notes");
    expect(result.initialPrompt).toContain("Summarize and synthesize");
    expect(result.initialPrompt).not.toContain("<describe what");
  });
});

describe("sweep build", () => {
  const sweep = SELECTION_ACTIONS.find((a) => a.id === "sweep")!;
  beforeEach(() => (mcpCall as jest.Mock).mockReset());

  it("creates a selection and returns the sweep prompt", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({ success: true, selection_id: "sel-123", refusal_count: 0 });
    const result = await sweep.build([noteItem("a"), noteItem("b")], "notes");
    expect(mcpCall).toHaveBeenCalledWith("hygiene-create-selection", expect.objectContaining({
      targets: expect.any(Array),
    }));
    expect(result.initialPrompt).toContain("Selection id: sel-123");
    expect(result.dropped).toBe(0);
  });

  it("returns an empty prompt and drops all when nothing is archivable", async () => {
    const bare: BrowseItem = {
      id: "x", title: "X", description: "", hub: "brain",
      primaryAction: { label: "Open", type: "open-file", target: "" },
    };
    const result = await sweep.build([bare], "notes");
    expect(result.initialPrompt).toBe("");
    expect(result.dropped).toBe(1);
    expect(mcpCall).not.toHaveBeenCalled();
  });

  it("throws when selection creation fails", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({ success: false, error: "boom" });
    await expect(sweep.build([noteItem("a")], "notes")).rejects.toThrow("boom");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/selectionActions.test.ts --silent`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```ts
// apps/dashboard/lib/browse/selectionActions.ts
import type { BrowseItem, ViewMode } from "@/lib/browse/types";
import { mcpCall } from "@/lib/mcp/client";
import { buildSelectionPrompt } from "./selectionPrompt";
import { buildSweepCandidates } from "./sweepCandidates";
import { buildSweepPrompt } from "./sweepPrompt";

export interface SelectionDispatch {
  /** Prompt to hand to the chat. Empty string means "nothing to do" (skip dispatch). */
  initialPrompt: string;
  /** Count of selected items the action could not handle. */
  dropped?: number;
}

export interface SelectionAction {
  id: string;
  label: string;
  icon: string;
  appliesTo: (viewMode: ViewMode) => boolean;
  build: (
    items: BrowseItem[],
    viewMode: ViewMode,
  ) => SelectionDispatch | Promise<SelectionDispatch>;
}

const CONTENT_VIEW_MODES = new Set<ViewMode>(["notes", "documents", "wiki", "pages"]);
const SWEEP_VIEW_MODES = new Set<ViewMode>(["notes", "pages"]);

interface SweepSelectionResponse {
  success?: boolean;
  selection_id?: string;
  error?: string;
  refusal_count?: number;
}

function parseSweepSelectionResponse(value: unknown): SweepSelectionResponse {
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as SweepSelectionResponse;
    } catch {
      return { success: false, error: "Selection creation returned invalid JSON." };
    }
  }
  if (typeof value === "object" && value !== null) {
    return value as SweepSelectionResponse;
  }
  return { success: false, error: "Selection creation returned an invalid response." };
}

export const SELECTION_ACTIONS: SelectionAction[] = [
  {
    id: "send-to-chat",
    label: "Send to chat",
    icon: "MessageSquare",
    appliesTo: () => true,
    build: (items, viewMode) => ({
      initialPrompt: buildSelectionPrompt(items, viewMode),
    }),
  },
  {
    id: "summarize",
    label: "Summarize",
    icon: "Sparkles",
    appliesTo: (viewMode) => CONTENT_VIEW_MODES.has(viewMode),
    build: (items, viewMode) => ({
      initialPrompt: buildSelectionPrompt(items, viewMode, {
        intent:
          "Summarize and synthesize these items into one coherent overview. Call out shared themes, contradictions, and anything worth following up.",
      }),
    }),
  },
  {
    id: "sweep",
    label: "Sweep",
    icon: "Archive",
    appliesTo: (viewMode) => SWEEP_VIEW_MODES.has(viewMode),
    build: async (items, viewMode) => {
      const mode = viewMode === "pages" ? "pages" : "notes";
      const candidates = buildSweepCandidates(mode, items);
      if (candidates.targets.length === 0) {
        return { initialPrompt: "", dropped: items.length };
      }
      const filterSummary = { source: "browse-multi-select", view: viewMode };
      const raw = await mcpCall<unknown>("hygiene-create-selection", {
        source_tab: candidates.source_tab,
        filter_summary: filterSummary,
        targets: candidates.targets,
      });
      const selection = parseSweepSelectionResponse(raw);
      if (!selection.success || !selection.selection_id) {
        throw new Error(selection.error || "Failed to create sweep selection.");
      }
      const dropped = candidates.unsupported.length;
      return {
        initialPrompt: buildSweepPrompt({
          sourceTab: candidates.source_tab,
          selectionId: selection.selection_id,
          targetCount: candidates.targets.length,
          refusalCount: (selection.refusal_count ?? 0) + dropped,
          filterSummary,
        }),
        dropped,
      };
    },
  },
];

export function selectionActionsForViewMode(viewMode: ViewMode): SelectionAction[] {
  return SELECTION_ACTIONS.filter((action) => action.appliesTo(viewMode));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/selectionActions.test.ts --silent`
Expected: PASS. If the "empty/dropped" test fails, confirm the bare item really has no `source_path`/`path` so `buildSweepCandidates` lists it under `unsupported` with zero targets.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/selectionActions.ts tests/dashboard/browse/selectionActions.test.ts
git commit -m "feat(browse): selection action registry (send-to-chat, summarize, sweep)"
```

---

## Task 4: Card-shell + list-row select mode

**Files:**
- Modify: `apps/dashboard/components/shared/BrowseCardShell.tsx`
- Modify: `apps/dashboard/components/shared/BrowseListRowCard.tsx`
- Test: `tests/dashboard/browse/BrowseCardSelection.test.tsx`

Approach: when `selectionMode` is true, the existing card content stays untouched but a **transparent full-card overlay button** captures clicks and toggles selection (so the inner action buttons can't fire), plus a **checkbox indicator** shows state. The article gets `relative` and the selected ring keys off `effectivelySelected`.

- [ ] **Step 1: Write the failing test**

```tsx
/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrowseCardShell } from "@/components/shared/BrowseCardShell";
import { BrowseListRowCard } from "@/components/shared/BrowseListRowCard";
import { buildBrowseCardModel } from "@/lib/browse/cardModel";
import type { BrowseItem } from "@/lib/browse/types";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

function model() {
  const item: BrowseItem = {
    id: "a",
    title: "Note A",
    description: "desc",
    hub: "brain",
    primaryAction: { label: "Open", type: "open-file", target: "notes/a.md" },
    path: "notes/a.md",
  };
  return buildBrowseCardModel(item, { viewMode: "notes" });
}

describe("BrowseCardShell selection mode", () => {
  it("shows a select overlay and toggles via it, not opening detail", () => {
    const onToggle = jest.fn();
    const onSelect = jest.fn();
    render(
      <BrowseCardShell
        model={model()}
        selectionMode
        isMultiSelected={false}
        onToggleMultiSelect={onToggle}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByTestId("browse-card-select-overlay"));
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("reflects checked state and has no overlay outside select mode", () => {
    const { rerender } = render(
      <BrowseCardShell model={model()} selectionMode isMultiSelected onToggleMultiSelect={jest.fn()} />,
    );
    expect(screen.getByTestId("browse-card-checkbox")).toBeChecked();
    rerender(<BrowseCardShell model={model()} onSelect={jest.fn()} />);
    expect(screen.queryByTestId("browse-card-select-overlay")).not.toBeInTheDocument();
  });
});

describe("BrowseListRowCard selection mode", () => {
  it("toggles via the overlay", () => {
    const onToggle = jest.fn();
    render(
      <BrowseListRowCard
        model={model()}
        selectionMode
        isMultiSelected={false}
        onToggleMultiSelect={onToggle}
        onSelect={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("browse-list-row-select-overlay"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/BrowseCardSelection.test.tsx --silent`
Expected: FAIL — props not accepted / overlay testid missing.

- [ ] **Step 3a: Edit `BrowseCardShell.tsx` — extend props**

Replace the props interface:

```tsx
interface BrowseCardShellProps {
  model: BrowseCardModel;
  selected?: boolean;
  pinned?: boolean;
  onPin?: () => void;
  onSelect?: () => void;
  onPrimaryAction?: () => void | Promise<void>;
  onAction?: (actionId: string) => void | Promise<void>;
  onPolicy?: () => void;
  selectionMode?: boolean;
  isMultiSelected?: boolean;
  onToggleMultiSelect?: () => void;
}
```

Update the function signature destructuring to add the three new params (with defaults):

```tsx
export function BrowseCardShell({
  model,
  selected = false,
  pinned = false,
  onPin,
  onSelect,
  onPrimaryAction,
  onAction,
  onPolicy,
  selectionMode = false,
  isMultiSelected = false,
  onToggleMultiSelect,
}: BrowseCardShellProps) {
```

- [ ] **Step 3b: Edit `BrowseCardShell.tsx` — derive selection state (after the `handleSelect` definition)**

Find:

```tsx
  const handleSelect = () => {
    onSelect?.();
  };
```

Add immediately after it:

```tsx
  const effectivelySelected = selectionMode ? isMultiSelected : selected;
  const interactive = selectionMode || Boolean(onSelect);
```

- [ ] **Step 3c: Edit `BrowseCardShell.tsx` — rewrite the `<article>` open tag + insert overlay**

Replace:

```tsx
    <article
      data-testid="browse-card-shell"
      className={`flex h-full min-h-[184px] flex-col rounded-xl border bg-[var(--bg-secondary)]/95 p-3.5 shadow-sm transition-[border-color,box-shadow,transform] duration-200 hover:border-[var(--accent-primary)]/35 hover:shadow-md ${
        selected
          ? "border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]/25"
          : "border-[var(--border-color)]"
      } ${onSelect ? "cursor-pointer active:scale-[0.99]" : ""}`}
      onClick={onSelect ? handleSelect : undefined}
      onKeyDown={onSelect ? handleKeyDown : undefined}
      role={onSelect ? "group" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      aria-label={onSelect ? model.title : undefined}
    >
```

With:

```tsx
    <article
      data-testid="browse-card-shell"
      className={`relative flex h-full min-h-[184px] flex-col rounded-xl border bg-[var(--bg-secondary)]/95 p-3.5 shadow-sm transition-[border-color,box-shadow,transform] duration-200 hover:border-[var(--accent-primary)]/35 hover:shadow-md ${
        effectivelySelected
          ? "border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]/25"
          : "border-[var(--border-color)]"
      } ${interactive ? "cursor-pointer active:scale-[0.99]" : ""}`}
      onClick={selectionMode ? undefined : onSelect ? handleSelect : undefined}
      onKeyDown={selectionMode ? undefined : onSelect ? handleKeyDown : undefined}
      role={selectionMode ? undefined : onSelect ? "group" : undefined}
      tabIndex={selectionMode ? undefined : onSelect ? 0 : undefined}
      aria-label={!selectionMode && onSelect ? model.title : undefined}
    >
      {selectionMode ? (
        <>
          <button
            type="button"
            data-testid="browse-card-select-overlay"
            aria-label={`${isMultiSelected ? "Deselect" : "Select"} ${model.title}`}
            aria-pressed={isMultiSelected}
            onClick={onToggleMultiSelect}
            className="absolute inset-0 z-10 cursor-pointer rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          />
          <input
            type="checkbox"
            data-testid="browse-card-checkbox"
            checked={isMultiSelected}
            readOnly
            tabIndex={-1}
            aria-hidden="true"
            className="pointer-events-none absolute right-3 top-3 z-20 h-4 w-4 accent-[var(--accent-primary)]"
          />
        </>
      ) : null}
```

(The existing children — header div, badges, metadata, footer — stay exactly as they are; the overlay sits above them at `z-10`.)

- [ ] **Step 3d: Edit `BrowseListRowCard.tsx` — apply the same four changes**

Props interface — add the same three optional props:

```tsx
  selectionMode?: boolean;
  isMultiSelected?: boolean;
  onToggleMultiSelect?: () => void;
```

Signature — add `selectionMode = false, isMultiSelected = false, onToggleMultiSelect,`.

After the `handleKeyDown` definition, add:

```tsx
  const effectivelySelected = selectionMode ? isMultiSelected : selected;
  const interactive = selectionMode || Boolean(onSelect);
```

Replace the `<article>` open tag:

```tsx
    <article
      data-testid="browse-list-row-card"
      className={`grid min-h-[76px] grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-xl border bg-[var(--bg-secondary)]/95 p-3 shadow-sm transition-[border-color,box-shadow,transform] duration-200 hover:border-[var(--accent-primary)]/35 hover:shadow-md md:grid-cols-[auto_minmax(0,1.2fr)_minmax(160px,0.8fr)_auto] md:items-center ${
        selected
          ? "border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]/25"
          : "border-[var(--border-color)]"
      } ${onSelect ? "cursor-pointer active:scale-[0.995]" : ""}`}
      onClick={onSelect}
      onKeyDown={onSelect ? handleKeyDown : undefined}
      role={onSelect ? "group" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      aria-label={onSelect ? model.title : undefined}
    >
```

with:

```tsx
    <article
      data-testid="browse-list-row-card"
      className={`relative grid min-h-[76px] grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-xl border bg-[var(--bg-secondary)]/95 p-3 shadow-sm transition-[border-color,box-shadow,transform] duration-200 hover:border-[var(--accent-primary)]/35 hover:shadow-md md:grid-cols-[auto_minmax(0,1.2fr)_minmax(160px,0.8fr)_auto] md:items-center ${
        effectivelySelected
          ? "border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]/25"
          : "border-[var(--border-color)]"
      } ${interactive ? "cursor-pointer active:scale-[0.995]" : ""}`}
      onClick={selectionMode ? undefined : onSelect}
      onKeyDown={selectionMode ? undefined : onSelect ? handleKeyDown : undefined}
      role={selectionMode ? undefined : onSelect ? "group" : undefined}
      tabIndex={selectionMode ? undefined : onSelect ? 0 : undefined}
      aria-label={!selectionMode && onSelect ? model.title : undefined}
    >
      {selectionMode ? (
        <>
          <button
            type="button"
            data-testid="browse-list-row-select-overlay"
            aria-label={`${isMultiSelected ? "Deselect" : "Select"} ${model.title}`}
            aria-pressed={isMultiSelected}
            onClick={onToggleMultiSelect}
            className="absolute inset-0 z-10 cursor-pointer rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          />
          <input
            type="checkbox"
            data-testid="browse-list-row-checkbox"
            checked={isMultiSelected}
            readOnly
            tabIndex={-1}
            aria-hidden="true"
            className="pointer-events-none absolute right-3 top-3 z-20 h-4 w-4 accent-[var(--accent-primary)]"
          />
        </>
      ) : null}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/BrowseCardSelection.test.tsx --silent`
Expected: PASS (3 tests). Also re-run the existing card tests to confirm no regression:
Run: `cd apps/dashboard && npx jest tests/dashboard/browse/BrowseCardAction.test.tsx --silent`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/shared/BrowseCardShell.tsx apps/dashboard/components/shared/BrowseListRowCard.tsx tests/dashboard/browse/BrowseCardSelection.test.tsx
git commit -m "feat(browse): card-shell select mode overlay + checkbox"
```

---

## Task 5: Renderer threads selection state to cards

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/BrowseDisplayRenderer.tsx`

The renderer reads the selection store directly (no new props on `BrowseContentGrid`), computes per-item state, and passes the three props to both shells. Single-select detail props (`selected`/`onSelect`) remain wired exactly as before.

- [ ] **Step 1: Add the store import**

After the existing imports at the top of the file, add:

```tsx
import { useBrowseSelection } from "@/lib/browse/useBrowseSelection";
```

- [ ] **Step 2: Subscribe inside the component**

Find:

```tsx
  const router = useRouter();
  const models = useMemo(
    () => items.map((item) => buildBrowseCardModel(item, { viewMode })),
    [items, viewMode],
  );
```

Insert directly after it:

```tsx
  const selectionMode = useBrowseSelection((s) => s.selectionMode);
  const selectedMap = useBrowseSelection((s) => s.selected);
  const toggleSelect = useBrowseSelection((s) => s.toggle);
```

- [ ] **Step 3: Extend `sharedProps`**

Find:

```tsx
          onPolicy: item.metadata?.capabilityId ? () => onSelectCapability(item) : undefined,
        };
```

Replace with:

```tsx
          onPolicy: item.metadata?.capabilityId ? () => onSelectCapability(item) : undefined,
          selectionMode,
          isMultiSelected: selectedMap.has(item.id),
          onToggleMultiSelect: () => toggleSelect(item),
        };
```

- [ ] **Step 4: Verify the existing renderer test still passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/BrowseUnifiedRendererIntegration.test.tsx --silent`
Expected: PASS (selection store defaults to off, so default rendering is unchanged).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/app/(views)/browse/BrowseDisplayRenderer.tsx
git commit -m "feat(browse): renderer threads selection state to cards"
```

---

## Task 6: `SelectionActionBar` component

**Files:**
- Create: `apps/dashboard/components/shared/SelectionActionBar.tsx`
- Test: `tests/dashboard/browse/SelectionActionBar.test.tsx`

Presentational only: it receives the resolved actions, the count, and callbacks. It does not read the store (keeps it pure and testable).

- [ ] **Step 1: Write the failing test**

```tsx
/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SelectionActionBar } from "@/components/shared/SelectionActionBar";
import { selectionActionsForViewMode } from "@/lib/browse/selectionActions";

describe("SelectionActionBar", () => {
  it("shows the count and only applicable actions, wiring callbacks", () => {
    const onAction = jest.fn();
    const onSelectAll = jest.fn();
    const onClear = jest.fn();
    render(
      <SelectionActionBar
        count={2}
        actions={selectionActionsForViewMode("notes")}
        onAction={onAction}
        onSelectAllVisible={onSelectAll}
        onClear={onClear}
      />,
    );
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send to chat" }));
    expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ id: "send-to-chat" }));
    fireEvent.click(screen.getByRole("button", { name: "Select all visible" }));
    expect(onSelectAll).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onClear).toHaveBeenCalled();
  });

  it("uses singular wording for one item", () => {
    render(
      <SelectionActionBar
        count={1}
        actions={selectionActionsForViewMode("skills")}
        onAction={jest.fn()}
        onSelectAllVisible={jest.fn()}
        onClear={jest.fn()}
      />,
    );
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    // skills tab → only the generic action
    expect(screen.queryByRole("button", { name: "Summarize" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/SelectionActionBar.test.tsx --silent`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// apps/dashboard/components/shared/SelectionActionBar.tsx
"use client";

import React from "react";
import { resolveIcon } from "@/lib/icon-map";
import type { SelectionAction } from "@/lib/browse/selectionActions";

interface SelectionActionBarProps {
  count: number;
  actions: SelectionAction[];
  onAction: (action: SelectionAction) => void;
  onSelectAllVisible: () => void;
  onClear: () => void;
}

export function SelectionActionBar({
  count,
  actions,
  onAction,
  onSelectAllVisible,
  onClear,
}: SelectionActionBarProps) {
  return (
    <div
      data-testid="selection-action-bar"
      className="sticky bottom-3 z-30 mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-[var(--accent-primary)]/30 bg-[var(--bg-card)]/95 p-3 shadow-lg backdrop-blur"
    >
      <span className="text-sm font-semibold text-[var(--text-primary)] tabular-nums">
        {count} selected
      </span>
      <div className="flex flex-wrap items-center gap-2">
        {actions.map((action) => {
          const Icon = resolveIcon(action.icon);
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onAction(action)}
              className="inline-flex min-h-[36px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 py-2 text-xs font-semibold text-[var(--accent-primary)] transition-colors hover:bg-[var(--accent-primary)]/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            >
              {React.createElement(Icon, { className: "h-4 w-4" })}
              {action.label}
            </button>
          );
        })}
      </div>
      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onSelectAllVisible}
          className="inline-flex min-h-[36px] cursor-pointer items-center rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          Select all visible
        </button>
        <button
          type="button"
          onClick={onClear}
          className="inline-flex min-h-[36px] cursor-pointer items-center rounded-lg px-3 py-2 text-xs font-medium text-[var(--text-secondary)] underline-offset-2 transition-colors hover:text-[var(--text-primary)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/SelectionActionBar.test.tsx --silent`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/shared/SelectionActionBar.tsx tests/dashboard/browse/SelectionActionBar.test.tsx
git commit -m "feat(browse): selection action bar component"
```

---

## Task 7: Toolbar `Select` / `Done` toggle

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- Test: `tests/dashboard/browse/SelectionActionBar.test.tsx` is component-level; the toggle is verified in the Task 8 integration test. (No separate test here — keep the toolbar change minimal and let integration cover it.)

- [ ] **Step 1: Add props to `BrowseToolbarProps`**

Find the end of the `interface BrowseToolbarProps {` block — the last two fields are:

```tsx
  /* Filter panel visibility */
  filtersOpen?: boolean;
  onFiltersOpenChange?: (open: boolean) => void;
}
```

Replace with:

```tsx
  /* Filter panel visibility */
  filtersOpen?: boolean;
  onFiltersOpenChange?: (open: boolean) => void;

  /* Multi-select mode */
  selectionMode?: boolean;
  onToggleSelectionMode?: () => void;
}
```

- [ ] **Step 2: Destructure the new props**

Find in the function signature:

```tsx
  filtersOpen: controlledFiltersOpen,
  onFiltersOpenChange,
}: BrowseToolbarProps) {
```

Replace with:

```tsx
  filtersOpen: controlledFiltersOpen,
  onFiltersOpenChange,
  selectionMode = false,
  onToggleSelectionMode,
}: BrowseToolbarProps) {
```

- [ ] **Step 3: Render the toggle button next to Filters**

Find the Filters button's closing `</button>` (the block that starts with `onClick={() => setFiltersOpen((current) => !current)}`). Immediately after that `</button>`, add:

```tsx
        {onToggleSelectionMode ? (
          <button
            type="button"
            onClick={onToggleSelectionMode}
            aria-pressed={selectionMode}
            aria-label={selectionMode ? "Exit select mode" : "Enter select mode"}
            className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-2.5 text-xs font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
              selectionMode
                ? "border-[var(--accent-primary)] bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
                : "border-[var(--border-primary)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            }`}
          >
            <CheckSquare className="h-4 w-4" />
            <span>{selectionMode ? "Done" : "Select"}</span>
          </button>
        ) : null}
```

- [ ] **Step 4: Import the icon**

Find the lucide import line:

```tsx
import { BrainCircuit, Grid2x2Plus, List, Loader2, Search, SlidersHorizontal, X } from "lucide-react";
```

Replace with:

```tsx
import { BrainCircuit, CheckSquare, Grid2x2Plus, List, Loader2, Search, SlidersHorizontal, X } from "lucide-react";
```

- [ ] **Step 5: Type-check the toolbar in isolation, then commit**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse --silent`
Expected: PASS (existing browse suite still green; no toolbar test asserts the button yet — integration covers it).

```bash
git add apps/dashboard/app/(views)/browse/BrowseToolbar.tsx
git commit -m "feat(browse): toolbar select-mode toggle"
```

---

## Task 8: Page wiring (toggle, reset, bar, dispatch)

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`
- Test: `tests/dashboard/browse/BrowseMultiSelectIntegration.test.tsx`

Wire: pass the toggle to the toolbar; reset selection when the tab changes; render `SelectionActionBar` when `count > 0`; dispatch a chosen action through `handleTriggerPrompt`, surface dropped counts via `toast`, and reset afterward.

- [ ] **Step 1: Write the failing integration test**

This test renders the page with mocked data hooks so it exercises the real selection store, toolbar toggle, card overlay, and dispatch path end to end at the component level.

```tsx
/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import BrowsePage from "@/app/(views)/browse/page";
import { useBrowseSelection } from "@/lib/browse/useBrowseSelection";
import type { BrowseItem } from "@/lib/browse/types";

const openChat = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn(), loading: jest.fn(() => "t"), message: jest.fn() } }));
jest.mock("@/lib/stores/chatStore", () => ({
  useChatStore: (selector: (s: { openChat: typeof openChat }) => unknown) => selector({ openChat }),
}));

const NOTES: BrowseItem[] = [
  { id: "a", title: "Note A", description: "", hub: "brain", path: "notes/a.md",
    primaryAction: { label: "Open", type: "open-file", target: "notes/a.md" }, metadata: { source_path: "notes/a.md" } },
  { id: "b", title: "Note B", description: "", hub: "brain", path: "notes/b.md",
    primaryAction: { label: "Open", type: "open-file", target: "notes/b.md" }, metadata: { source_path: "notes/b.md" } },
];

// Mock the heavy state hook so the page renders deterministically with our items.
jest.mock("@/app/(views)/browse/useBrowseState", () => {
  const actual = jest.requireActual("@/app/(views)/browse/useBrowseState");
  return {
    ...actual,
    useBrowseState: () => ({
      ...actual.__mockBaseState?.(),
    }),
  };
});

describe("Browse multi-select integration", () => {
  beforeEach(() => {
    openChat.mockReset();
    act(() => useBrowseSelection.getState().reset());
  });

  it("select → choose Send to chat → openChat receives the bundled prompt", () => {
    // NOTE: implementer wires __mockBaseState (below) to return the minimal
    // useBrowseState shape with effectiveViewMode "notes", sorted: NOTES,
    // semanticResultsActive: false, visibleCount: 50, and no-op setters.
    render(<BrowsePage />);

    fireEvent.click(screen.getByRole("button", { name: "Enter select mode" }));
    fireEvent.click(screen.getByLabelText("Select Note A"));
    fireEvent.click(screen.getByLabelText("Select Note B"));
    expect(screen.getByText("2 selected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Send to chat" }));
    expect(openChat).toHaveBeenCalledTimes(1);
    const arg = openChat.mock.calls[0][0];
    expect(arg.initialPrompt).toContain("Selected 2 items from Browse · Notes:");
    expect(arg.initialPrompt).toContain('"Note A" — notes/a.md');
  });
});
```

> **Implementer note:** `useBrowseState` is large. Rather than fight its internals, add an exported test helper `__mockBaseState()` in `useBrowseState.ts` guarded by `process.env.NODE_ENV === "test"` **only if** simpler mocking proves impractical. Preferred: replace the whole `useBrowseState` mock factory with an inline object returning the ~40 fields the page destructures (all setters as `jest.fn()`, `effectiveViewMode: "notes"`, `activeCategory: { id: "notes", label: "Notes" }`, `sorted: NOTES`, `pinnedItems: []`, `semanticResults: []`, `semanticResultsActive: false`, `visibleCount: 50`, `pageSize: 50`, booleans false, arrays empty, `handleTriggerPrompt` delegating to the mocked `openChat`). Keep this fixture in the test file. The goal of the test is the selection→dispatch path, not `useBrowseState`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/BrowseMultiSelectIntegration.test.tsx --silent`
Expected: FAIL — no Select button / no action bar yet.

- [ ] **Step 3a: Imports in `page.tsx`**

Find:

```tsx
import { Suspense, useState, useCallback } from "react";
```

Replace with:

```tsx
import { Suspense, useState, useCallback, useEffect, useMemo } from "react";
```

After the existing `BrowseContentGrid` import block, add:

```tsx
import { SelectionActionBar } from "@/components/shared/SelectionActionBar";
import { useBrowseSelection } from "@/lib/browse/useBrowseSelection";
import { selectionActionsForViewMode, type SelectionAction } from "@/lib/browse/selectionActions";
```

- [ ] **Step 3b: Subscribe + reset + derive (inside `BrowsePageInner`, after the existing `useState` block near `const [selectedCapability, ...]`)**

Add:

```tsx
  const selectionMode = useBrowseSelection((s) => s.selectionMode);
  const selectedCount = useBrowseSelection((s) => s.selected.size);
  const toggleSelectionMode = useBrowseSelection((s) => s.toggleSelectionMode);

  // Selection is scoped to the active tab — reset whenever it changes.
  useEffect(() => {
    useBrowseSelection.getState().reset();
  }, [effectiveViewMode]);

  const visibleItems = useMemo(
    () => (semanticResultsActive ? semanticResults : sorted).slice(0, visibleCount),
    [semanticResultsActive, semanticResults, sorted, visibleCount],
  );

  const handleSelectionAction = useCallback(
    async (action: SelectionAction) => {
      const items = useBrowseSelection.getState().selectedItemList();
      if (items.length === 0) return;
      try {
        const result = await action.build(items, effectiveViewMode);
        if (result.dropped && result.dropped > 0) {
          toast.message(`${result.dropped} item(s) skipped — not supported by ${action.label}.`);
        }
        if (result.initialPrompt) {
          handleTriggerPrompt(result.initialPrompt);
          useBrowseSelection.getState().reset();
        } else {
          toast.error(`Nothing to ${action.label.toLowerCase()} in the current selection.`);
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : `${action.label} failed.`);
      }
    },
    [effectiveViewMode, handleTriggerPrompt],
  );
```

- [ ] **Step 3c: Pass the toggle to the toolbar**

Find in the `<BrowseToolbar ... />` props:

```tsx
              filtersOpen={toolbarFiltersOpen}
              onFiltersOpenChange={setToolbarFiltersOpen}
            />
```

Replace with:

```tsx
              filtersOpen={toolbarFiltersOpen}
              onFiltersOpenChange={setToolbarFiltersOpen}
              selectionMode={selectionMode}
              onToggleSelectionMode={toggleSelectionMode}
            />
```

- [ ] **Step 3d: Render the action bar after the content grid**

Find the closing of the content block:

```tsx
              onTriggerPrompt={handleTriggerPrompt}
              coverageIndex={coverageIndex}
            />
          </div>
        </div>
      </div>
```

Replace with:

```tsx
              onTriggerPrompt={handleTriggerPrompt}
              coverageIndex={coverageIndex}
            />
          </div>
          {selectionMode && selectedCount > 0 ? (
            <SelectionActionBar
              count={selectedCount}
              actions={selectionActionsForViewMode(effectiveViewMode)}
              onAction={handleSelectionAction}
              onSelectAllVisible={() => useBrowseSelection.getState().selectAllVisible(visibleItems)}
              onClear={() => useBrowseSelection.getState().clear()}
            />
          ) : null}
        </div>
      </div>
```

- [ ] **Step 4: Run the integration test and the full browse suite**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse/BrowseMultiSelectIntegration.test.tsx --silent`
Expected: PASS.
Run: `cd apps/dashboard && npx jest tests/dashboard/browse --silent`
Expected: PASS (no regressions).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/app/(views)/browse/page.tsx tests/dashboard/browse/BrowseMultiSelectIntegration.test.tsx
git commit -m "feat(browse): wire multi-select toggle, action bar, and dispatch"
```

---

## Task 9: ADR + spec status

**Files:**
- Create: `docs/adrs/ADR-<next>-browse-multi-select-actions.md`
- Modify: `docs/superpowers/specs/2026-05-20-browse-multi-select-actions-design.md`

- [ ] **Step 1: Determine the next ADR number**

Run: `ls docs/adrs/ | grep -oE 'ADR-[0-9]+' | sort -t- -k2 -n | tail -1`
The latest at planning time is `ADR-766`; use the next free number (likely `ADR-767`). Confirm with the command output.

- [ ] **Step 2: Write the ADR**

Create `docs/adrs/ADR-<next>-browse-multi-select-actions.md` with frontmatter matching the repo's ADR convention (open an existing recent ADR such as `docs/adrs/ADR-766-*.md` to copy the exact frontmatter keys). Body covers: Context (single-item Browse + all-filtered headless Sweep, gap for user-curated subsets), Decision (select-mode multi-select layer over the same card grid; action registry dispatching to the interactive chat via `openChat`/ADR-748; Sweep reuses `hygiene-create-selection`), Consequences (extensible registry; selection scoped per tab; no new persistent storage for generic/summarize; Rule 32 preserved — bar is a contextual toolbar, not a bespoke panel), and Status: Implemented.

- [ ] **Step 3: Flip the spec status**

Edit `docs/superpowers/specs/2026-05-20-browse-multi-select-actions-design.md` frontmatter: change `status: draft` to `status: accepted`.

- [ ] **Step 4: Commit**

```bash
git add docs/adrs/ADR-*-browse-multi-select-actions.md docs/superpowers/specs/2026-05-20-browse-multi-select-actions-design.md
git commit -m "docs(adr): record browse multi-select actions decision"
```

---

## Task 10: Build, lint, and real-browser verification

**Files:** none (verification only).

- [ ] **Step 1: Full browse Jest suite**

Run: `cd apps/dashboard && npx jest tests/dashboard/browse --silent`
Expected: PASS — all browse tests including the five new files.

- [ ] **Step 2: Build + lint via slash commands (Augur rules 19/29)**

Use `/dev build` to rebuild and validate the dashboard (do **not** run `pnpm dev` / `rm -rf .next` manually). Run the lint loop and fix any findings. Expected: build green, no lint errors in the changed files.

- [ ] **Step 3: Client-side browser verification (Rules 28, 31, 34, 35)**

Determine the worktree/dev dashboard port (from `.augur-worktree.yaml` if in a worktree; else `:3000`). Auto-select the **local** browser via `list_connected_browsers` → `select_browser` (Rule 35). Then, in a real browser:
  1. Open `/browse?view=notes`.
  2. Click **Select** → confirm checkboxes appear on cards and the page is interactive (no chunk-load error boundary).
  3. Select two real notes → confirm the sticky bar shows `2 selected` with **Send to chat**, **Summarize**, **Sweep**.
  4. Click **Send to chat** → confirm the floating chat opens pre-filled with the real selected note titles/paths.
  5. Switch to the **Skills** tab → confirm selection cleared and the bar offers only **Send to chat**.

Capture a screenshot of step 3 (the action bar over real selected cards) as the evidence artifact.

> **Do not** drive the floating chat's Start/Reconnect during verification — that spawns real autonomous agents (memory `feedback_dashboard_chat_verification_spawns_agents`). Verifying that the chat opens **pre-filled** is sufficient; do not send.

- [ ] **Step 4: Report**

State the exact URL/port verified, that cards entered select mode and the bar dispatched a real bundled prompt into the chat input, and attach the screenshot. If anything is empty/broken, fix before declaring done (Rule 9).

---

## Self-Review (completed during planning)

**Spec coverage:**
- Select-mode toggle → Task 7 (toolbar) + Task 8 (wiring). ✓
- Checkboxes on all tabs / cards → Task 4 (shells) + Task 5 (renderer). ✓
- Sticky action bar with count, actions, select-all, clear → Task 6 + Task 8. ✓
- Action registry: send-to-chat (all), summarize (content), sweep (notes/pages) → Task 3. ✓
- Generic prompt format with path/id fallback + sanitization → Task 2. ✓
- Dispatch via interactive `openChat`/`handleTriggerPrompt` → Task 8. ✓
- Sweep reuses `hygiene-create-selection` + `buildSweepPrompt` → Task 3. ✓
- Selection scoped per tab (reset on viewMode change) → Task 8 (`useEffect`). ✓
- New prop names avoid `selected`/`onSelect` collision → Task 4 (`isMultiSelected`/`onToggleMultiSelect`). ✓
- Selection stored as full objects (survives filter/search) → Task 1. ✓
- Testing incl. real-browser verification → Tasks 1–6, 8, 10. ✓
- ADR + spec status → Task 9. ✓

**Type consistency:** `SelectionAction` / `SelectionDispatch` defined in Task 3 are imported unchanged in Tasks 6 and 8. Store method names (`enter/exit/toggle/selectAllVisible/clear/reset/isSelected/selectedItemList/selectedCount/toggleSelectionMode`) defined in Task 1 are used identically in Tasks 5 and 8. Card props (`selectionMode/isMultiSelected/onToggleMultiSelect`) defined in Task 4 are passed identically in Task 5. `buildSelectionPrompt(items, viewMode, options?)` signature is consistent across Tasks 2 and 3.

**Placeholder scan:** No `TBD`/`TODO`/"handle edge cases" — every code step shows complete code. The one `<describe what you'd like to do with these>` string is intentional product copy (the chat placeholder), not a plan placeholder.
