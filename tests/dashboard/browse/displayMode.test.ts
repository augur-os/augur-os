import { BROWSE_CATEGORIES } from "@/lib/browse/types";
import {
  BROWSE_DISPLAY_MODE_STORAGE_KEY,
  displayModeForCategory,
  readDisplayModeOverrides,
  writeDisplayModeOverride,
} from "@/lib/browse/displayMode";

describe("Browse display modes", () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  it("uses category defaults when no override is stored", () => {
    const technicalCategoryIds = [
      "background-routines",
      "mcp-servers",
      "api-routes",
      "tests",
      "logs",
      "system-metadata",
    ];
    const contentCategoryIds = ["notes", "documents", "wiki"];

    technicalCategoryIds.forEach((categoryId) => {
      const category = BROWSE_CATEGORIES.find(
        (candidate) => candidate.id === categoryId,
      );
      expect(category).toBeDefined();
      expect(displayModeForCategory(category!, readDisplayModeOverrides())).toBe("list");
    });

    contentCategoryIds.forEach((categoryId) => {
      const category = BROWSE_CATEGORIES.find((candidate) => candidate.id === categoryId);
      expect(category).toBeDefined();
      expect(category!.defaultDisplayMode).toBeUndefined();
      expect(displayModeForCategory(category!, readDisplayModeOverrides())).toBe("card");
    });
  });

  it("returns empty overrides when localStorage getItem throws", () => {
    jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage unavailable");
    });

    expect(readDisplayModeOverrides()).toEqual({});
  });

  it("returns empty overrides when localStorage property access throws", () => {
    jest.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new Error("storage blocked");
    });

    expect(readDisplayModeOverrides()).toEqual({});
  });

  it("returns the next overrides when localStorage setItem throws", () => {
    window.localStorage.setItem(
      BROWSE_DISPLAY_MODE_STORAGE_KEY,
      JSON.stringify({ notes: "list" }),
    );
    jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });

    expect(writeDisplayModeOverride("wiki", "list")).toEqual({
      notes: "list",
      wiki: "list",
    });
  });

  it("applies a valid override only to the matching tab", () => {
    window.localStorage.setItem(
      BROWSE_DISPLAY_MODE_STORAGE_KEY,
      JSON.stringify({ notes: "list", skills: "card" }),
    );

    const notesCategory = BROWSE_CATEGORIES.find((category) => category.id === "notes");
    const wikiCategory = BROWSE_CATEGORIES.find((category) => category.id === "wiki");

    expect(notesCategory).toBeDefined();
    expect(wikiCategory).toBeDefined();
    const overrides = readDisplayModeOverrides();
    expect(displayModeForCategory(notesCategory!, overrides)).toBe("list");
    expect(displayModeForCategory(wikiCategory!, overrides)).toBe("card");
  });

  it("ignores invalid stored values and unknown keys while preserving valid ViewMode keys", () => {
    window.localStorage.setItem(
      BROWSE_DISPLAY_MODE_STORAGE_KEY,
      JSON.stringify({
        notes: "list",
        skills: "grid",
        "made-up": "card",
        logs: "card",
        tests: null,
      }),
    );

    expect(readDisplayModeOverrides()).toEqual({
      notes: "list",
      logs: "card",
    });
  });

  it("writes one tab override without dropping other overrides", () => {
    window.localStorage.setItem(
      BROWSE_DISPLAY_MODE_STORAGE_KEY,
      JSON.stringify({ notes: "list", skills: "card" }),
    );

    expect(writeDisplayModeOverride("wiki", "list")).toEqual({
      notes: "list",
      skills: "card",
      wiki: "list",
    });
    expect(JSON.parse(window.localStorage.getItem(BROWSE_DISPLAY_MODE_STORAGE_KEY) ?? "{}")).toEqual({
      notes: "list",
      skills: "card",
      wiki: "list",
    });
  });
});
