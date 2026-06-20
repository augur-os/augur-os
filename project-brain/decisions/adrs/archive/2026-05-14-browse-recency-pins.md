# Browse Recency Pins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Browse default to category-scoped pinned cards first, then recent cards, while keeping search, filters, and explicit sorts trustworthy.

**Architecture:** Add one tested Browse ordering helper that owns stable pin identities, timestamp fallback parsing, and priority sorting. Extend the existing MCP pin store with optional `category` and `itemKey` fields while preserving legacy page pins. Wire `useBrowseState` as the ordering/mutation owner, and keep `BrowseCard` / `SkillBrowseCard` as presentation-only consumers of pin state.

**Tech Stack:** TypeScript, React, Next.js dashboard components, Jest dashboard tests, Python MCP helper tests, PyYAML pin persistence, Augur auto-loop verification through `/auto-test-dashboard`, `/auto-test-pytest`, `/auto-lint`, and `/dev-build`.

**Spec:** `docs/superpowers/specs/2026-05-14-browse-recency-pins-design.md`

---

## Boundary Rules

- Keep dashboard persistence MCP-backed. Do not write `pins.yaml` from dashboard code.
- Do not change Browse category taxonomy, sweep behavior, capability policy actions, or ADR generated indexes.
- Preserve existing page/artifact pin behavior for pins that only have `url`.
- Treat search and filters as authoritative: a pinned non-match must remain hidden.
- Introduce a visible `Default` sort option so the dropdown matches the pins-plus-recency default order.
- Use repo slash/auto-loop commands for verification. Do not run raw `pnpm test`, raw `pytest`, or `pnpm dev`.
- Browser verification is required after implementation because Browse UI changes are user-visible.

## File Structure

### Frontend

- Create `apps/dashboard/lib/browse/pinOrdering.ts`
  - Owns pin identity, timestamp fallback parsing, legacy pin matching, and sorted item ordering.
- Create `tests/dashboard/browse/pinOrdering.test.ts`
  - Unit tests for timestamp precedence, category-scoped pins, legacy Pages pins, search/filter behavior helpers, and explicit sort behavior.
- Modify `apps/dashboard/app/(views)/browse/useBrowseState.ts`
  - Fetch pins for all Browse categories, expose pin state, toggle pins through MCP, switch default sort to `default`, and call the ordering helper.
- Modify `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
  - Add `Default` sort option and keep existing explicit sort options.
- Modify `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
  - Pass pin props into card renderers.
- Modify `apps/dashboard/components/shared/BrowseCard.tsx`
  - Render compact pin control and overflow `Pin` / `Unpin`.
- Modify `apps/dashboard/components/shared/SkillBrowseCard.tsx`
  - Render the same pin UX for skill cards.
- Create `apps/dashboard/components/shared/BrowsePinButton.tsx`
  - Shared accessible icon button used by generic and skill Browse cards.

### Backend

- Modify `src/mcp/augur_framework/tools/infrastructure/pins.py`
  - Add optional `category` and `itemKey` support to pin add/remove without breaking current call sites.
- Modify `tests/test_pins_tool.py`
  - Cover category-scoped pins, legacy URL pins, and idempotent remove behavior.

### Tests

- Modify `tests/dashboard/browse/useBrowseState.test.tsx`
  - Cover default ordering, filtered behavior, and pin mutation calls.
- Modify `tests/dashboard/browse/BrowseContentGridSkills.test.tsx`
  - Cover pin state reaching `SkillBrowseCard`.
- Add or modify `tests/dashboard/browse/BrowseCardPins.test.tsx`
  - Cover generic Browse card pin button and overflow actions.

---

## Task 1: Pin Ordering Helper

**Files:**
- Create: `apps/dashboard/lib/browse/pinOrdering.ts`
- Create: `tests/dashboard/browse/pinOrdering.test.ts`

- [ ] **Step 1: Write the failing helper tests**

Create `tests/dashboard/browse/pinOrdering.test.ts`:

```typescript
import type { BrowseItem } from "@/lib/browse/types";
import {
  browseItemPinKeys,
  browseItemPinTarget,
  getBrowseItemTimestampMs,
  isBrowseNarrowed,
  normalizePinEntries,
  sortBrowseItems,
  type BrowsePinEntry,
} from "@/lib/browse/pinOrdering";

function item(overrides: Partial<BrowseItem>): BrowseItem {
  return {
    id: "item",
    title: "Item",
    description: "Item description",
    hub: "brain",
    primaryAction: { label: "Open", type: "navigate", target: "/item" },
    ...overrides,
  };
}

describe("Browse pin ordering", () => {
  it("uses created_at before promoted_at before modified fields", () => {
    const target = item({
      metadata: {
        created_at: "2026-05-14T10:00:00Z",
        promoted_at: "2026-05-15T10:00:00Z",
        modified: "2026-05-16T10:00:00Z",
      },
    });

    expect(getBrowseItemTimestampMs(target)).toBe(Date.parse("2026-05-14T10:00:00Z"));
  });

  it("falls back to promoted_at and then modified when created is absent", () => {
    expect(getBrowseItemTimestampMs(item({
      metadata: { promoted_at: "2026-05-15T10:00:00Z", modified: "2026-05-16T10:00:00Z" },
    }))).toBe(Date.parse("2026-05-15T10:00:00Z"));

    expect(getBrowseItemTimestampMs(item({
      metadata: { modified: "2026-05-16T10:00:00Z" },
    }))).toBe(Date.parse("2026-05-16T10:00:00Z"));
  });

  it("sorts pins first, then newest timestamp, then title for default order", () => {
    const oldPinned = item({
      id: "old-pinned",
      title: "Old Pinned",
      primaryAction: { label: "Open", type: "navigate", target: "/old-pinned" },
      metadata: { created_at: "2026-05-01T00:00:00Z" },
    });
    const newest = item({
      id: "newest",
      title: "Newest",
      primaryAction: { label: "Open", type: "navigate", target: "/newest" },
      metadata: { created_at: "2026-05-14T00:00:00Z" },
    });
    const noDate = item({
      id: "alpha",
      title: "Alpha",
      primaryAction: { label: "Open", type: "navigate", target: "/alpha" },
    });
    const pins = normalizePinEntries([
      { category: "skills", itemKey: "skills::old-pinned", url: "/old-pinned" },
    ], "skills");

    expect(sortBrowseItems([noDate, newest, oldPinned], {
      category: "skills",
      pins,
      sortBy: "default",
      narrowed: false,
    }).map((entry) => entry.id)).toEqual(["old-pinned", "newest", "alpha"]);
  });

  it("keeps category pins scoped to their category", () => {
    const target = item({ id: "same-id", primaryAction: { label: "Open", type: "navigate", target: "/same-id" } });
    const skillPins = normalizePinEntries([
      { category: "adrs", itemKey: "adrs::same-id", url: "/same-id" },
    ], "skills");

    expect(browseItemPinKeys("skills", target).some((key) => skillPins.has(key))).toBe(false);
  });

  it("matches legacy Pages pins by url", () => {
    const page = item({
      id: "live:/brain/profile",
      title: "Profile",
      primaryAction: { label: "Open Page", type: "navigate", target: "/brain/profile" },
      metadata: { kind: "live" },
    });
    const pins = normalizePinEntries([{ url: "/brain/profile", title: "Profile", kind: "live", hub: "brain" }], "pages");

    expect(browseItemPinKeys("pages", page).some((key) => pins.has(key))).toBe(true);
  });

  it("uses active sort for narrowed results while keeping matching pins first", () => {
    const zed = item({ id: "zed", title: "Zed", primaryAction: { label: "Open", type: "navigate", target: "/zed" } });
    const alpha = item({ id: "alpha", title: "Alpha", primaryAction: { label: "Open", type: "navigate", target: "/alpha" } });
    const pins = normalizePinEntries([{ category: "skills", itemKey: "skills::zed", url: "/zed" }], "skills");

    expect(sortBrowseItems([alpha, zed], {
      category: "skills",
      pins,
      sortBy: "default",
      narrowed: true,
    }).map((entry) => entry.id)).toEqual(["zed", "alpha"]);
  });

  it("builds pin mutation target with category and itemKey", () => {
    expect(browseItemPinTarget("skills", item({
      id: "knowledge",
      title: "Knowledge",
      hub: "brain",
      primaryAction: { label: "View", type: "navigate", target: "/browse/knowledge" },
    }))).toEqual({
      category: "skills",
      itemKey: "skills::knowledge",
      url: "/browse/knowledge",
      title: "Knowledge",
      kind: "browse-card",
      hub: "brain",
    });
  });

  it("detects search and filters as narrowing", () => {
    expect(isBrowseNarrowed({
      search: "",
      hubFilter: null,
      tagFilter: null,
      typeFilter: null,
      skillTagFilter: null,
      masterFilter: null,
      pluginFilter: null,
      sourceFilter: null,
      kindFilter: "all",
      archivedFilter: null,
      scopeFilter: null,
      exposureFilter: null,
      surfaceFilter: null,
      ownerFilter: null,
      managementFilter: null,
      policyScopeFilter: null,
      driftFilter: null,
      capabilityClientFilter: null,
    })).toBe(false);

    expect(isBrowseNarrowed({
      search: "wiki",
      hubFilter: null,
      tagFilter: null,
      typeFilter: null,
      skillTagFilter: null,
      masterFilter: null,
      pluginFilter: null,
      sourceFilter: null,
      kindFilter: "all",
      archivedFilter: null,
      scopeFilter: null,
      exposureFilter: null,
      surfaceFilter: null,
      ownerFilter: null,
      managementFilter: null,
      policyScopeFilter: null,
      driftFilter: null,
      capabilityClientFilter: null,
    })).toBe(true);
  });
});
```

- [ ] **Step 2: Run the dashboard auto-loop and confirm failure**

Run: `/auto-test-dashboard`

Expected: dashboard test loop fails and the report names `tests/dashboard/browse/pinOrdering.test.ts` because `@/lib/browse/pinOrdering` does not exist.

- [ ] **Step 3: Add the helper implementation**

Create `apps/dashboard/lib/browse/pinOrdering.ts`:

```typescript
import type { BrowseItem, BrowsePageKindFilter, ViewMode } from "@/lib/browse/types";
import type { OverlayScopeFilter } from "@/lib/browse/overlay";

export type BrowseSortBy =
  | "default"
  | "name-asc"
  | "name-desc"
  | "rank-desc"
  | "hub"
  | "modified-desc"
  | "modified-asc";

export interface BrowsePinEntry {
  url?: string;
  title?: string;
  kind?: string;
  hub?: string;
  category?: string;
  itemKey?: string;
  pinnedAt?: string;
}

export interface BrowsePinTarget {
  category: ViewMode;
  itemKey: string;
  url: string;
  title: string;
  kind: string;
  hub: string;
}

export interface BrowseNarrowingState {
  search: string;
  hubFilter: string | null;
  tagFilter: string | null;
  typeFilter: string | null;
  skillTagFilter: string | null;
  masterFilter: string | null;
  pluginFilter: string | null;
  sourceFilter: string | null;
  kindFilter: BrowsePageKindFilter;
  archivedFilter: string | null;
  scopeFilter: OverlayScopeFilter | null;
  exposureFilter: string | null;
  surfaceFilter: string | null;
  ownerFilter: string | null;
  managementFilter: string | null;
  policyScopeFilter: string | null;
  driftFilter: string | null;
  capabilityClientFilter: string | null;
}

const TIMESTAMP_FIELDS = [
  "created_at",
  "createdAt",
  "created",
  "promoted_at",
  "promotedAt",
  "modified",
  "modified_at",
  "modifiedAt",
  "updated_at",
  "updatedAt",
  "timestamp",
  "date",
] as const;

function canonicalBrowseUrl(item: BrowseItem): string {
  const metadataUrl = item.metadata?.url?.trim();
  if (metadataUrl) return metadataUrl;
  if (item.primaryAction.type === "navigate" && item.primaryAction.target) {
    return item.primaryAction.target;
  }
  return item.path || item.primaryAction.target || item.id;
}

export function browseItemPinTarget(category: ViewMode, item: BrowseItem): BrowsePinTarget {
  return {
    category,
    itemKey: `${category}::${item.id || canonicalBrowseUrl(item)}`,
    url: canonicalBrowseUrl(item),
    title: item.title,
    kind: "browse-card",
    hub: item.hub || "system",
  };
}

export function browseItemPinKeys(category: ViewMode, item: BrowseItem): string[] {
  const target = browseItemPinTarget(category, item);
  const keys = new Set<string>([target.itemKey]);
  if (target.url) keys.add(`${category}::${target.url}`);
  if (category === "pages" && target.url) keys.add(`pages::${target.url}`);
  return [...keys];
}

export function normalizePinEntries(
  pins: BrowsePinEntry[] | undefined,
  category: ViewMode,
): Map<string, BrowsePinEntry> {
  const lookup = new Map<string, BrowsePinEntry>();
  for (const pin of pins ?? []) {
    if (pin.category && pin.category !== category) continue;
    if (pin.itemKey) {
      lookup.set(pin.itemKey, pin);
      continue;
    }
    if (category === "pages" && pin.url) {
      lookup.set(`pages::${pin.url}`, pin);
    }
  }
  return lookup;
}

export function getBrowseItemTimestampMs(item: BrowseItem): number | null {
  const metadata = item.metadata ?? {};
  for (const field of TIMESTAMP_FIELDS) {
    const raw = metadata[field];
    if (!raw) continue;
    const parsed = Date.parse(raw);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return null;
}

export function isBrowseItemPinned(
  category: ViewMode,
  item: BrowseItem,
  pins: Map<string, BrowsePinEntry>,
): boolean {
  return browseItemPinKeys(category, item).some((key) => pins.has(key));
}

export function isBrowseNarrowed(state: BrowseNarrowingState): boolean {
  return Boolean(
    state.search.trim() ||
    state.hubFilter ||
    state.tagFilter ||
    state.typeFilter ||
    state.skillTagFilter ||
    state.masterFilter ||
    state.pluginFilter ||
    state.sourceFilter ||
    state.kindFilter !== "all" ||
    state.archivedFilter ||
    state.scopeFilter ||
    state.exposureFilter ||
    state.surfaceFilter ||
    state.ownerFilter ||
    state.managementFilter ||
    state.policyScopeFilter ||
    state.driftFilter ||
    state.capabilityClientFilter
  );
}

function titleAsc(left: BrowseItem, right: BrowseItem): number {
  return left.title.localeCompare(right.title);
}

function baseSort(left: BrowseItem, right: BrowseItem, sortBy: BrowseSortBy): number {
  switch (sortBy) {
    case "name-desc":
      return right.title.localeCompare(left.title);
    case "rank-desc": {
      const scoreA = parseFloat(left.metadata?.qualityScore || "0");
      const scoreB = parseFloat(right.metadata?.qualityScore || "0");
      if (scoreA !== scoreB) return scoreB - scoreA;
      const tierOrder: Record<string, number> = { A: 1, B: 2, C: 3, D: 4, F: 5 };
      const tierA = tierOrder[left.metadata?.qualityTier || ""] ?? 6;
      const tierB = tierOrder[right.metadata?.qualityTier || ""] ?? 6;
      if (tierA !== tierB) return tierA - tierB;
      return titleAsc(left, right);
    }
    case "hub":
      return left.hub.localeCompare(right.hub) || titleAsc(left, right);
    case "modified-desc":
      return (right.metadata?.modified || "").localeCompare(left.metadata?.modified || "") || titleAsc(left, right);
    case "modified-asc":
      return (left.metadata?.modified || "").localeCompare(right.metadata?.modified || "") || titleAsc(left, right);
    case "name-asc":
    case "default":
    default:
      return titleAsc(left, right);
  }
}

export function sortBrowseItems(
  items: BrowseItem[],
  options: {
    category: ViewMode;
    pins: Map<string, BrowsePinEntry>;
    sortBy: BrowseSortBy;
    narrowed: boolean;
  },
): BrowseItem[] {
  return [...items].sort((left, right) => {
    const leftPinned = isBrowseItemPinned(options.category, left, options.pins);
    const rightPinned = isBrowseItemPinned(options.category, right, options.pins);
    if (leftPinned !== rightPinned) return leftPinned ? -1 : 1;

    if (options.sortBy === "default" && !options.narrowed) {
      const leftTimestamp = getBrowseItemTimestampMs(left);
      const rightTimestamp = getBrowseItemTimestampMs(right);
      if (leftTimestamp !== null && rightTimestamp !== null && leftTimestamp !== rightTimestamp) {
        return rightTimestamp - leftTimestamp;
      }
      if (leftTimestamp !== null && rightTimestamp === null) return -1;
      if (leftTimestamp === null && rightTimestamp !== null) return 1;
      return titleAsc(left, right);
    }

    const resolvedSort = options.sortBy === "default" ? "name-asc" : options.sortBy;
    return baseSort(left, right, resolvedSort);
  });
}
```

- [ ] **Step 4: Run the dashboard auto-loop and confirm pass**

Run: `/auto-test-dashboard`

Expected: dashboard test loop passes for the new helper tests or reports only unrelated pre-existing failures. Any failure in `pinOrdering.test.ts` must be fixed before continuing.

- [ ] **Step 5: Commit helper checkpoint**

```bash
git add apps/dashboard/lib/browse/pinOrdering.ts tests/dashboard/browse/pinOrdering.test.ts
git commit -m "feat(browse): add pin ordering helper"
```

---

## Task 2: MCP Pin Contract

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/pins.py`
- Modify: `tests/test_pins_tool.py`

- [ ] **Step 1: Add failing Python tests**

Append to `tests/test_pins_tool.py`:

```python
def test_pin_add_stores_category_and_item_key(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"

    result = pin_add_impl(
        pins_path=pins_path,
        url="/browse/knowledge",
        title="Knowledge",
        kind="browse-card",
        hub="brain",
        category="skills",
        itemKey="skills::knowledge",
    )
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert result == {"added": True, "url": "/browse/knowledge", "itemKey": "skills::knowledge"}
    assert pins[0]["category"] == "skills"
    assert pins[0]["itemKey"] == "skills::knowledge"


def test_pin_add_is_idempotent_by_category_item_key(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"

    first = pin_add_impl(
        pins_path=pins_path,
        url="/browse/knowledge",
        title="Knowledge",
        kind="browse-card",
        hub="brain",
        category="skills",
        itemKey="skills::knowledge",
    )
    second = pin_add_impl(
        pins_path=pins_path,
        url="/browse/knowledge-copy",
        title="Knowledge Copy",
        kind="browse-card",
        hub="brain",
        category="skills",
        itemKey="skills::knowledge",
    )

    pins = pin_list_impl(pins_path=pins_path)["pins"]
    assert first["added"] is True
    assert second == {"added": False, "url": "/browse/knowledge-copy", "itemKey": "skills::knowledge"}
    assert len(pins) == 1
    assert pins[0]["url"] == "/browse/knowledge"


def test_pin_remove_prefers_category_item_key(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"
    pin_add_impl(
        pins_path=pins_path,
        url="/same-url",
        title="Skill",
        kind="browse-card",
        hub="brain",
        category="skills",
        itemKey="skills::same",
    )
    pin_add_impl(
        pins_path=pins_path,
        url="/same-url",
        title="ADR",
        kind="browse-card",
        hub="dev",
        category="adrs",
        itemKey="adrs::same",
    )

    result = pin_remove_impl(
        pins_path=pins_path,
        url="/same-url",
        category="skills",
        itemKey="skills::same",
    )
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert result == {"removed": True, "url": "/same-url", "itemKey": "skills::same"}
    assert len(pins) == 1
    assert pins[0]["category"] == "adrs"
```

- [ ] **Step 2: Run Python auto-loop and confirm failure**

Run: `/auto-test-pytest`

Expected: Python test loop fails because `pin_add_impl` and `pin_remove_impl` do not accept `category` / `itemKey`.

- [ ] **Step 3: Extend pin helper signatures and matching**

In `src/mcp/augur_framework/tools/infrastructure/pins.py`, replace `pin_add_impl` and `pin_remove_impl` with:

```python
def _pin_identity(pin: dict[str, Any]) -> tuple[str | None, str | None]:
    category = pin.get("category")
    item_key = pin.get("itemKey")
    if isinstance(category, str) and isinstance(item_key, str) and category and item_key:
        return category, item_key
    return None, None


def pin_add_impl(
    *,
    pins_path: Path,
    url: str,
    title: str,
    kind: str,
    hub: str,
    category: str | None = None,
    itemKey: str | None = None,
) -> dict[str, Any]:
    pins = _load_pins(pins_path)
    requested_identity = (category, itemKey) if category and itemKey else (None, None)
    if requested_identity != (None, None):
        if any(_pin_identity(pin) == requested_identity for pin in pins):
            return {"added": False, "url": url, "itemKey": itemKey}
    elif any(pin.get("url") == url for pin in pins):
        return {"added": False, "url": url}

    entry: dict[str, Any] = {
        "url": url,
        "title": title,
        "kind": kind,
        "hub": hub,
        "pinnedAt": _now_iso(),
    }
    if category:
        entry["category"] = category
    if itemKey:
        entry["itemKey"] = itemKey

    pins.append(entry)
    _save_pins(pins_path, pins)
    result = {"added": True, "url": url}
    if itemKey:
        result["itemKey"] = itemKey
    return result


def pin_remove_impl(
    *,
    pins_path: Path,
    url: str,
    category: str | None = None,
    itemKey: str | None = None,
) -> dict[str, Any]:
    pins = _load_pins(pins_path)
    requested_identity = (category, itemKey) if category and itemKey else (None, None)
    if requested_identity != (None, None):
        next_pins = [pin for pin in pins if _pin_identity(pin) != requested_identity]
    else:
        next_pins = [pin for pin in pins if pin.get("url") != url]
    if len(next_pins) == len(pins):
        result = {"removed": False, "url": url}
        if itemKey:
            result["itemKey"] = itemKey
        return result

    _save_pins(pins_path, next_pins)
    result = {"removed": True, "url": url}
    if itemKey:
        result["itemKey"] = itemKey
    return result
```

Update MCP wrappers in the same file:

```python
    async def pin_add(
        url: str,
        title: str,
        kind: str,
        hub: str,
        category: str | None = None,
        itemKey: str | None = None,
    ) -> str:
        metrics.track_tool("pin_add")
        result = pin_add_impl(
            pins_path=_pins_path(),
            url=url,
            title=title,
            kind=kind,
            hub=hub,
            category=category,
            itemKey=itemKey,
        )
        return json.dumps(result, indent=2)
```

```python
    async def pin_remove(
        url: str,
        category: str | None = None,
        itemKey: str | None = None,
    ) -> str:
        metrics.track_tool("pin_remove")
        return json.dumps(
            pin_remove_impl(
                pins_path=_pins_path(),
                url=url,
                category=category,
                itemKey=itemKey,
            ),
            indent=2,
        )
```

- [ ] **Step 4: Run Python auto-loop and confirm pass**

Run: `/auto-test-pytest`

Expected: pin helper tests pass. Any failures in `tests/test_pins_tool.py` must be fixed before continuing.

- [ ] **Step 5: Commit MCP pin contract**

```bash
git add src/mcp/augur_framework/tools/infrastructure/pins.py tests/test_pins_tool.py
git commit -m "feat(browse): scope pins by category item key"
```

---

## Task 3: Browse State Ordering and Pin Mutations

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: `tests/dashboard/browse/useBrowseState.test.tsx`

- [ ] **Step 1: Add failing state tests**

Append these tests inside `describe("useBrowseState", () => { ... })` in `tests/dashboard/browse/useBrowseState.test.tsx`:

```typescript
  it("defaults to pinned then newest items when browse is not narrowed", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [{ category: "wiki", itemKey: "wiki::old-pinned", url: "/old-pinned" }] }, loading: false, error: null, refetch: jest.fn() };
      }
      return {
        data: {
          items: [
            { id: "old-pinned", title: "Old Pinned", description: "Old", hub: "brain", type: "wiki", metadata: { created_at: "2026-05-01T00:00:00Z" } },
            { id: "newest", title: "Newest", description: "New", hub: "brain", type: "wiki", metadata: { created_at: "2026-05-14T00:00:00Z" } },
            { id: "alpha", title: "Alpha", description: "No date", hub: "brain", type: "wiki", metadata: {} },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.sortBy).toBe("default");
      expect(result.current.sorted.map((entry) => entry.id)).toEqual(["old-pinned", "newest", "alpha"]);
    });
  });

  it("keeps nonmatching pinned cards hidden after search", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [{ category: "wiki", itemKey: "wiki::pinned-hidden", url: "/pinned-hidden" }] }, loading: false, error: null, refetch: jest.fn() };
      }
      return {
        data: {
          items: [
            { id: "pinned-hidden", title: "Pinned Hidden", description: "Does not match", hub: "brain", type: "wiki", metadata: { created_at: "2026-05-14T00:00:00Z" } },
            { id: "match", title: "Search Match", description: "needle", hub: "brain", type: "wiki", metadata: { created_at: "2026-05-01T00:00:00Z" } },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    act(() => {
      result.current.setSearch("needle");
    });

    await waitFor(() => {
      expect(result.current.sorted.map((entry) => entry.id)).toEqual(["match"]);
    });
  });

  it("toggles category scoped pins through MCP", async () => {
    const { mcpCall } = await import("@/lib/mcp/client");
    (mcpCall as jest.Mock).mockResolvedValue({ added: true });
    localStorage.setItem("augur:browse:view", "skills");

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.sorted.length).toBeGreaterThan(0));
    await act(async () => {
      await result.current.togglePin(result.current.sorted[0]);
    });

    expect(mcpCall).toHaveBeenCalledWith("pin-add", expect.objectContaining({
      category: "skills",
      itemKey: expect.stringMatching(/^skills::/),
      kind: "browse-card",
    }));
  });
```

- [ ] **Step 2: Run dashboard auto-loop and confirm failure**

Run: `/auto-test-dashboard`

Expected: dashboard test loop fails because `sortBy` is still `name-asc`, pins load only for Pages, and `togglePin` is not exposed.

- [ ] **Step 3: Update Browse state types and imports**

In `apps/dashboard/app/(views)/browse/useBrowseState.ts`, add imports:

```typescript
import {
  browseItemPinTarget,
  isBrowseItemPinned,
  isBrowseNarrowed,
  normalizePinEntries,
  sortBrowseItems,
  type BrowsePinEntry,
  type BrowseSortBy,
} from "@/lib/browse/pinOrdering";
```

Change `PinEntry` to:

```typescript
type PinEntry = BrowsePinEntry;
```

Change the BrowseState sort and pin section:

```typescript
  sortBy: BrowseSortBy;
  setSortBy: (value: BrowseSortBy) => void;
  pinnedItems: BrowseItem[];
  isPinned: (item: BrowseItem) => boolean;
  togglePin: (item: BrowseItem) => Promise<void>;
```

- [ ] **Step 4: Change default sort and reset behavior**

Replace:

```typescript
const [sortBy, setSortBy] = useState<string>("name-asc");
```

with:

```typescript
const [sortBy, setSortBy] = useState<BrowseSortBy>("default");
```

In `changeView`, replace `setSortBy("name-asc");` with:

```typescript
setSortBy("default");
```

- [ ] **Step 5: Fetch pins for every category and wire mutations**

Change the `pin-list` query `enabled` value from Pages-only to enabled for all non-extensions Browse modes:

```typescript
  const {
    data: pinsData,
    loading: pinsLoading,
    error: pinsError,
    refetch: pinsRefetch,
  } = useMcpQuery<{ pins: PinEntry[] }>(
    ["pin-list", effectiveViewMode],
    "pin-list",
    "user-data",
    {
      enabled: effectiveViewMode !== "extensions-bundles",
      fallback: { pins: [] },
    },
  );
```

Add after `filtered`:

```typescript
  const pinLookup = useMemo(
    () => normalizePinEntries(pinsData?.pins, effectiveViewMode),
    [pinsData?.pins, effectiveViewMode],
  );

  const browseIsNarrowed = useMemo(
    () => isBrowseNarrowed({
      search,
      hubFilter,
      tagFilter,
      typeFilter,
      skillTagFilter,
      masterFilter,
      pluginFilter,
      sourceFilter,
      kindFilter,
      archivedFilter,
      scopeFilter,
      exposureFilter,
      surfaceFilter,
      ownerFilter,
      managementFilter,
      policyScopeFilter,
      driftFilter,
      capabilityClientFilter,
    }),
    [search, hubFilter, tagFilter, typeFilter, skillTagFilter, masterFilter, pluginFilter, sourceFilter, kindFilter, archivedFilter, scopeFilter, exposureFilter, surfaceFilter, ownerFilter, managementFilter, policyScopeFilter, driftFilter, capabilityClientFilter],
  );

  const isPinned = useCallback(
    (item: BrowseItem) => isBrowseItemPinned(effectiveViewMode, item, pinLookup),
    [effectiveViewMode, pinLookup],
  );

  const togglePin = useCallback(async (item: BrowseItem) => {
    const target = browseItemPinTarget(effectiveViewMode, item);
    const pinned = isBrowseItemPinned(effectiveViewMode, item, pinLookup);
    try {
      if (pinned) {
        await mcpCall("pin-remove", {
          url: target.url,
          category: target.category,
          itemKey: target.itemKey,
        });
        toast.success("Unpinned");
      } else {
        await mcpCall("pin-add", target);
        toast.success("Pinned");
      }
      pinsRefetch();
    } catch {
      toast.error(pinned ? "Failed to remove pin" : "Failed to pin");
    }
  }, [effectiveViewMode, pinLookup, pinsRefetch]);
```

- [ ] **Step 6: Replace existing sort block**

Replace the `const sorted = useMemo(() => { ... })` block with:

```typescript
  const sorted = useMemo(() => {
    return sortBrowseItems(filtered, {
      category: effectiveViewMode,
      pins: pinLookup,
      sortBy,
      narrowed: browseIsNarrowed,
    });
  }, [filtered, effectiveViewMode, pinLookup, sortBy, browseIsNarrowed]);
```

Replace `pinnedItems` with:

```typescript
  const pinnedItems = useMemo(
    () => sorted.filter((item) => isPinned(item)),
    [sorted, isPinned],
  );
```

Return `isPinned` and `togglePin` from the hook.

- [ ] **Step 7: Run dashboard auto-loop and confirm pass**

Run: `/auto-test-dashboard`

Expected: Browse state tests pass. Failures caused by stale assumptions about `sortBy: "name-asc"` in test fixtures must be updated to `"default"`.

- [ ] **Step 8: Commit Browse state checkpoint**

```bash
git add apps/dashboard/app/\(views\)/browse/useBrowseState.ts tests/dashboard/browse/useBrowseState.test.tsx
git commit -m "feat(browse): order cards by pins and recency"
```

---

## Task 4: Card Pin Controls

**Files:**
- Create: `apps/dashboard/components/shared/BrowsePinButton.tsx`
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx`
- Modify: `apps/dashboard/components/shared/SkillBrowseCard.tsx`
- Create: `tests/dashboard/browse/BrowseCardPins.test.tsx`
- Modify: `tests/dashboard/browse/BrowseContentGridSkills.test.tsx`

- [ ] **Step 1: Add failing card tests**

Create `tests/dashboard/browse/BrowseCardPins.test.tsx`:

```typescript
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import type { BrowseItem } from "@/lib/browse/types";
import { BrowseCard } from "@/components/shared/BrowseCard";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), prefetch: jest.fn(), back: jest.fn() }),
}));

jest.mock("@/lib/mcp/client", () => ({ mcpCall: jest.fn().mockResolvedValue({}) }));

const item: BrowseItem = {
  id: "wiki-card",
  title: "Wiki Card",
  description: "A useful wiki page",
  hub: "brain",
  icon: "FileText",
  primaryAction: { label: "Read", type: "open-file", target: "/tmp/wiki.md" },
};

describe("BrowseCard pin controls", () => {
  it("renders inactive pin control and calls toggle", () => {
    const onTogglePin = jest.fn();
    render(<BrowseCard item={item} isPinned={false} onTogglePin={onTogglePin} />);

    fireEvent.click(screen.getByRole("button", { name: "Pin Wiki Card" }));

    expect(onTogglePin).toHaveBeenCalledTimes(1);
  });

  it("renders active pin control and overflow unpin action", () => {
    const onTogglePin = jest.fn();
    render(<BrowseCard item={item} isPinned onTogglePin={onTogglePin} />);

    expect(screen.getByRole("button", { name: "Unpin Wiki Card" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Unpin" }));

    expect(onTogglePin).toHaveBeenCalledTimes(1);
  });
});
```

Append to `tests/dashboard/browse/BrowseContentGridSkills.test.tsx`:

```typescript
  it("passes pin state to skill cards", () => {
    render(
      <BrowseContentGrid
        {...makeProps({ sorted: [skillItem] })}
        isPinned={(item) => item.id === "skill-one"}
        onTogglePin={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Unpin Skill One" })).toHaveAttribute("aria-pressed", "true");
  });
```

- [ ] **Step 2: Run dashboard auto-loop and confirm failure**

Run: `/auto-test-dashboard`

Expected: dashboard test loop fails because `BrowseCard` and `BrowseContentGrid` do not accept pin props and `BrowsePinButton` does not exist.

- [ ] **Step 3: Create shared pin button**

Create `apps/dashboard/components/shared/BrowsePinButton.tsx`:

```typescript
"use client";

import { Pin } from "lucide-react";

interface BrowsePinButtonProps {
  title: string;
  pinned: boolean;
  onToggle: () => void;
  className?: string;
}

export function BrowsePinButton({ title, pinned, onToggle, className = "" }: BrowsePinButtonProps) {
  return (
    <button
      type="button"
      aria-label={`${pinned ? "Unpin" : "Pin"} ${title}`}
      aria-pressed={pinned}
      title={pinned ? "Unpin" : "Pin"}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      className={`inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 ${
        pinned
          ? "border-[var(--accent-primary)]/40 bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]"
          : "border-[var(--border-color)] bg-[var(--bg-primary)]/70 text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
      } ${className}`}
    >
      <Pin className="h-4 w-4" />
    </button>
  );
}
```

- [ ] **Step 4: Add pin props to `BrowseCard`**

In `apps/dashboard/components/shared/BrowseCard.tsx`, import:

```typescript
import { BrowsePinButton } from "./BrowsePinButton";
```

Extend props:

```typescript
  isPinned?: boolean;
  onTogglePin?: () => void;
```

Update the function signature:

```typescript
export function BrowseCard({
  item,
  onRunMcp,
  onSelect,
  availableClients: _availableClients,
  isPinned = false,
  onTogglePin,
}: BrowseCardProps) {
```

Add pin action before existing item actions in `overflowActions`:

```typescript
    ...(onTogglePin ? [{
      id: `pin-${item.id}`,
      label: isPinned ? "Unpin" : "Pin",
      icon: "Pin",
      onSelect: () => onTogglePin(),
    }] : []),
```

In the card title/header block, replace the current standalone title element with this flex row:

```tsx
          <div className="flex items-start justify-between gap-2">
            <div className="line-clamp-2 text-[15px] font-semibold leading-5 text-[var(--text-primary)]">
              {item.title}
            </div>
            {onTogglePin && (
              <BrowsePinButton
                title={item.title}
                pinned={isPinned}
                onToggle={onTogglePin}
              />
            )}
          </div>
```

- [ ] **Step 5: Add pin props to `SkillBrowseCard`**

In `apps/dashboard/components/shared/SkillBrowseCard.tsx`, import `BrowsePinButton`, extend props, and add the same active pin state:

```typescript
import { BrowsePinButton } from "./BrowsePinButton";
```

```typescript
  isPinned?: boolean;
  onTogglePin?: () => void;
```

```typescript
export function SkillBrowseCard({
  item,
  onRunMcp,
  onSelect,
  onManageCapability,
  availableClients: _availableClients,
  isPinned = false,
  onTogglePin,
}: SkillBrowseCardProps) {
```

Add this `overflowItems` constant after `secondaryActions`:

```typescript
  const overflowItems = [
    ...(onTogglePin
      ? [{
          id: `pin-${item.id}`,
          label: isPinned ? "Unpin" : "Pin",
          icon: "Pin",
          onSelect: () => onTogglePin(),
        }]
      : []),
    ...secondaryActions.map((action) => ({
      ...action,
      onSelect: () => {
        void handleAction(action);
      },
    })),
  ];
```

Change the skill title header to:

```tsx
          <div className="mb-1.5 flex items-start justify-between gap-2">
            <div className="min-w-0 text-[15px] font-semibold leading-5 text-[var(--text-primary)]">
              {item.title}
            </div>
            {onTogglePin && (
              <BrowsePinButton
                title={item.title}
                pinned={isPinned}
                onToggle={onTogglePin}
              />
            )}
          </div>
```

Replace the existing secondary-actions overflow rendering with:

```tsx
        {overflowItems.length > 0 && (
          <BrowseOverflowMenu
            items={overflowItems}
            buttonLabel="More actions"
            menuLabel={`${item.title} actions`}
            stopPropagation
            className="ml-auto"
            buttonTestId="skill-card-overflow"
          />
        )}
```

- [ ] **Step 6: Pass pin props from content grid**

Extend `BrowseContentGridProps` in `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`:

```typescript
  isPinned: (item: BrowseItem) => boolean;
  onTogglePin: (item: BrowseItem) => void;
```

Update the `makeProps` helper in `tests/dashboard/browse/BrowseContentGridSkills.test.tsx` so existing tests keep defaults:

```typescript
    isPinned: jest.fn(() => false),
    onTogglePin: jest.fn(),
```

Pass to generic cards:

```tsx
<BrowseCard
  key={item.id}
  item={item}
  onRunMcp={onRunMcp}
  isPinned={isPinned(item)}
  onTogglePin={() => onTogglePin(item)}
/>
```

Pass to skill cards:

```tsx
<SkillBrowseCard
  item={item}
  onRunMcp={onRunMcp}
  onSelect={() => onSelectSkill(item.id)}
  onManageCapability={hasCapabilityMetadata(item) ? () => onSelectCapability(item) : undefined}
  isPinned={isPinned(item)}
  onTogglePin={() => onTogglePin(item)}
/>
```

- [ ] **Step 7: Wire props from page**

In `apps/dashboard/app/(views)/browse/page.tsx`, destructure:

```typescript
    isPinned,
    togglePin,
```

Pass to `BrowseContentGrid`:

```tsx
                isPinned={isPinned}
                onTogglePin={(item) => {
                  void togglePin(item);
                }}
```

- [ ] **Step 8: Run dashboard auto-loop and confirm pass**

Run: `/auto-test-dashboard`

Expected: card pin tests pass. Any accessibility failure around button labels or menu items must be fixed before continuing.

- [ ] **Step 9: Commit card UX checkpoint**

```bash
git add apps/dashboard/components/shared/BrowsePinButton.tsx apps/dashboard/components/shared/BrowseCard.tsx apps/dashboard/components/shared/SkillBrowseCard.tsx apps/dashboard/app/\(views\)/browse/BrowseContentGrid.tsx apps/dashboard/app/\(views\)/browse/page.tsx tests/dashboard/browse/BrowseCardPins.test.tsx tests/dashboard/browse/BrowseContentGridSkills.test.tsx
git commit -m "feat(browse): add card pin controls"
```

---

## Task 5: Toolbar Default Sort Option

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- Modify: `tests/dashboard/browse/BrowseToolbar.test.tsx`
- Modify: `tests/dashboard/browse/BrowseLayout.test.tsx`

- [ ] **Step 1: Add failing toolbar expectation**

In `tests/dashboard/browse/BrowseToolbar.test.tsx`, update the baseline render props to use `sortBy="default"` and add:

```typescript
it("shows Default as the first sort option", () => {
  render(<BrowseToolbar {...baseProps} sortBy="default" />);

  const sort = screen.getByRole("combobox", { name: /sort order/i });
  expect(sort).toHaveValue("default");
  expect(screen.getByRole("option", { name: "Default" })).toBeInTheDocument();
});
```

In `tests/dashboard/browse/BrowseLayout.test.tsx`, change `sortBy: "name-asc"` in `baseBrowseState` to:

```typescript
  sortBy: "default",
```

- [ ] **Step 2: Run dashboard auto-loop and confirm failure**

Run: `/auto-test-dashboard`

Expected: toolbar test fails because the `Default` option does not exist.

- [ ] **Step 3: Add Default option to toolbar**

In `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`, replace the sort options with:

```tsx
          <option value="default">Default</option>
          <option value="name-asc">Name (A-Z)</option>
          <option value="name-desc">Name (Z-A)</option>
          <option value="rank-desc">By Rank</option>
          <option value="modified-desc">Newest First</option>
          <option value="modified-asc">Oldest First</option>
          <option value="hub">By Hub</option>
```

Update the `sortBy` prop type import if TypeScript requires the `BrowseSortBy` union from `@/lib/browse/pinOrdering`.

- [ ] **Step 4: Run dashboard auto-loop and confirm pass**

Run: `/auto-test-dashboard`

Expected: toolbar tests pass and layout fixture failures caused by the old default are fixed.

- [ ] **Step 5: Commit toolbar checkpoint**

```bash
git add apps/dashboard/app/\(views\)/browse/BrowseToolbar.tsx tests/dashboard/browse/BrowseToolbar.test.tsx tests/dashboard/browse/BrowseLayout.test.tsx
git commit -m "feat(browse): expose default pin recency sort"
```

---

## Task 6: Final Verification and Browser Check

**Files:**
- Verify only; no planned source edits unless tests expose a real bug.

- [ ] **Step 1: Run frontend auto-loop**

Run: `/auto-test-dashboard`

Expected: dashboard test loop passes. If it fails, fix the named Browse pin regression before continuing.

- [ ] **Step 2: Run Python auto-loop**

Run: `/auto-test-pytest`

Expected: Python test loop passes. If failures mention `tests/test_pins_tool.py`, fix the pin MCP helper before continuing.

- [ ] **Step 3: Run lint**

Run: `/auto-lint`

Expected: lint reports green or applies allowed fixes. Commit allowed fixes with the Browse pin files only.

- [ ] **Step 4: Rebuild dashboard through the sanctioned command**

Run: `/dev-build`

Expected: dashboard build/rebuild completes without chunk-load drift or build errors.

- [ ] **Step 5: Browser verification**

Use the Browser plugin or another screenshot-capable browser tool against the actual running dashboard port. Verify:

- `/browse?category=skills` loads to interactive state with useful data;
- `/browse?category=wiki` or another populated non-skills category loads to interactive state;
- `Default` sort is selected;
- pinning a visible card moves it above unpinned matching cards after refresh/refetch;
- searching for text that excludes the pinned card hides it;
- clearing search shows the pinned card again at the top of that category;
- no fatal overlay, chunk-load error, or empty placeholder blocks the page.

- [ ] **Step 6: Commit final verification fixes**

If verification required fixes, commit them:

```bash
git add apps/dashboard/lib/browse/pinOrdering.ts apps/dashboard/app/\(views\)/browse/useBrowseState.ts apps/dashboard/app/\(views\)/browse/BrowseToolbar.tsx apps/dashboard/app/\(views\)/browse/BrowseContentGrid.tsx apps/dashboard/app/\(views\)/browse/page.tsx apps/dashboard/components/shared/BrowsePinButton.tsx apps/dashboard/components/shared/BrowseCard.tsx apps/dashboard/components/shared/SkillBrowseCard.tsx src/mcp/augur_framework/tools/infrastructure/pins.py tests/test_pins_tool.py tests/dashboard/browse/pinOrdering.test.ts tests/dashboard/browse/useBrowseState.test.tsx tests/dashboard/browse/BrowseCardPins.test.tsx tests/dashboard/browse/BrowseContentGridSkills.test.tsx tests/dashboard/browse/BrowseToolbar.test.tsx tests/dashboard/browse/BrowseLayout.test.tsx
git commit -m "fix(browse): harden recency pin verification"
```

If no fixes were required, do not create an empty commit.

---

## Completion Report

At handoff, report:

- commit hashes for each checkpoint;
- exact auto-loop commands run and whether they passed;
- exact browser URLs checked;
- whether pins were tested on both a skill card and a non-skill Browse card;
- any pre-existing unrelated working-tree changes left untouched.
