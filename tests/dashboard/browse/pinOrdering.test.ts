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
    expect(
      getBrowseItemTimestampMs(
        item({
          metadata: { promoted_at: "2026-05-15T10:00:00Z", modified: "2026-05-16T10:00:00Z" },
        }),
      ),
    ).toBe(Date.parse("2026-05-15T10:00:00Z"));

    expect(
      getBrowseItemTimestampMs(
        item({
          metadata: { modified: "2026-05-16T10:00:00Z" },
        }),
      ),
    ).toBe(Date.parse("2026-05-16T10:00:00Z"));
  });

  it("checks timestamp fields in the documented precedence order", () => {
    const timestampFields = [
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
    ];

    timestampFields.forEach((field, index) => {
      const metadata = Object.fromEntries(
        timestampFields.slice(index).map((candidate, candidateIndex) => [
          candidate,
          `2026-05-${String(candidateIndex + 1).padStart(2, "0")}T00:00:00Z`,
        ]),
      );

      expect(getBrowseItemTimestampMs(item({ metadata }))).toBe(Date.parse("2026-05-01T00:00:00Z"));
    });
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
    const pins = normalizePinEntries(
      [{ category: "skills", itemKey: "skills::old-pinned", url: "/old-pinned" }],
      "skills",
    );

    expect(
      sortBrowseItems([noDate, newest, oldPinned], {
        category: "skills",
        pins,
        sortBy: "default",
        narrowed: false,
      }).map((entry) => entry.id),
    ).toEqual(["old-pinned", "newest", "alpha"]);
  });

  it("keeps category pins scoped to their category", () => {
    const target = item({
      id: "same-id",
      primaryAction: { label: "Open", type: "navigate", target: "/same-id" },
    });
    const skillPins = normalizePinEntries(
      [{ category: "adrs", itemKey: "adrs::same-id", url: "/same-id" }],
      "skills",
    );

    expect(browseItemPinKeys("skills", target).some((key) => skillPins.has(key))).toBe(false);
  });

  it("matches category-scoped URL-only pins by item URL", () => {
    const target = item({
      id: "knowledge",
      title: "Knowledge",
      primaryAction: { label: "Open", type: "navigate", target: "/browse/knowledge" },
    });
    const pins = normalizePinEntries([{ category: "skills", url: "/browse/knowledge" }], "skills");

    expect(browseItemPinKeys("skills", target).some((key) => pins.has(key))).toBe(true);
  });

  it("matches legacy Pages pins by url", () => {
    const page = item({
      id: "live:/workspace/profile",
      title: "Profile",
      primaryAction: { label: "Open Page", type: "navigate", target: "/workspace/profile" },
      metadata: { kind: "live" },
    });
    const pins = normalizePinEntries(
      [{ url: "/workspace/profile", title: "Profile", kind: "live" }],
      "pages",
    );

    expect(browseItemPinKeys("pages", page).some((key) => pins.has(key))).toBe(true);
  });

  it("uses active sort for narrowed results while keeping matching pins first", () => {
    const zed = item({
      id: "zed",
      title: "Zed",
      primaryAction: { label: "Open", type: "navigate", target: "/zed" },
    });
    const alpha = item({
      id: "alpha",
      title: "Alpha",
      primaryAction: { label: "Open", type: "navigate", target: "/alpha" },
    });
    const pins = normalizePinEntries([{ category: "skills", itemKey: "skills::zed", url: "/zed" }], "skills");

    expect(
      sortBrowseItems([alpha, zed], {
        category: "skills",
        pins,
        sortBy: "default",
        narrowed: true,
      }).map((entry) => entry.id),
    ).toEqual(["zed", "alpha"]);
  });

  it("keeps pins first while unpinned items follow explicit name-desc sort", () => {
    const pinnedAlpha = item({
      id: "pinned-alpha",
      title: "Alpha",
      primaryAction: { label: "Open", type: "navigate", target: "/pinned-alpha" },
    });
    const bravo = item({
      id: "bravo",
      title: "Bravo",
      primaryAction: { label: "Open", type: "navigate", target: "/bravo" },
    });
    const zed = item({
      id: "zed",
      title: "Zed",
      primaryAction: { label: "Open", type: "navigate", target: "/zed" },
    });
    const pins = normalizePinEntries(
      [{ category: "skills", itemKey: "skills::pinned-alpha", url: "/pinned-alpha" }],
      "skills",
    );

    expect(
      sortBrowseItems([bravo, pinnedAlpha, zed], {
        category: "skills",
        pins,
        sortBy: "name-desc",
        narrowed: false,
      }).map((entry) => entry.id),
    ).toEqual(["pinned-alpha", "zed", "bravo"]);
  });

  it("builds pin mutation target with category and itemKey", () => {
    expect(
      browseItemPinTarget(
        "skills",
        item({
          id: "knowledge",
          title: "Knowledge",
          primaryAction: { label: "View", type: "navigate", target: "/browse/knowledge" },
        }),
      ),
    ).toEqual({
      category: "skills",
      itemKey: "skills::knowledge",
      url: "/browse/knowledge",
      title: "Knowledge",
      kind: "browse-card",
    });
  });

  it("accepts typed pin entries", () => {
    const entry: BrowsePinEntry = {
      category: "skills",
      itemKey: "skills::knowledge",
      url: "/browse/knowledge",
      title: "Knowledge",
      kind: "browse-card",
    };

    expect(normalizePinEntries([entry], "skills").has("skills::knowledge")).toBe(true);
  });

  it("detects search and filters as narrowing", () => {
    expect(
      isBrowseNarrowed({
        search: "",
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
      }),
    ).toBe(false);

    expect(
      isBrowseNarrowed({
        search: "wiki",
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
      }),
    ).toBe(true);
  });
});
