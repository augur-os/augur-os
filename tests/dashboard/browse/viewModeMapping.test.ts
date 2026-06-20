import {
  indexCategoryForViewMode,
  itemMatchesViewMode,
  journeyCategoryForViewMode,
  normalizeRequestedViewMode,
} from "@/lib/browse/viewModeMapping";

describe("viewModeMapping", () => {
  it("matches retired source paths as notes before journey metadata exists", () => {
    expect(
      itemMatchesViewMode(
        { path: "~/Projects/Au-vault/sources/web/source.md" },
        "notes",
      ),
    ).toBe(true);
  });

  it("matches archive from vault archive paths before journey metadata exists", () => {
    expect(itemMatchesViewMode({ path: "archive/career/old.md" }, "archive")).toBe(true);
  });

  it("does not match arbitrary absolute paths that contain a journey segment", () => {
    expect(
      itemMatchesViewMode(
        { path: "/Users/example/not-vault/sources/source.md" },
        "notes",
      ),
    ).toBe(false);
  });

  it("returns backend journey categories for vault journey display modes", () => {
    expect(journeyCategoryForViewMode("notes")).toBe("notes");
    expect(journeyCategoryForViewMode("pages")).toBeNull();
  });

  it("drops the deleted drafts view with no redirect target (no shim)", () => {
    expect(normalizeRequestedViewMode("drafts")).toBeNull();
  });

  it("keeps documents as a first-class Browse category", () => {
    expect(normalizeRequestedViewMode("documents")).toBe("documents");
    expect(indexCategoryForViewMode("documents")).toBe("documents");
    expect(journeyCategoryForViewMode("documents")).toBeNull();
  });

  it("keeps prompts as a first-class Browse category", () => {
    expect(normalizeRequestedViewMode("prompts")).toBe("prompts");
    expect(indexCategoryForViewMode("prompts")).toBe("prompts");
    expect(journeyCategoryForViewMode("prompts")).toBeNull();
  });
});
