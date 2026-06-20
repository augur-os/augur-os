import {
  indexCategoryForViewMode,
  itemMatchesViewMode,
  normalizeRequestedViewMode,
} from "@/lib/browse/viewModeMapping";

describe("viewModeMapping pages rename", () => {
  it("normalizes pages to the pages ViewMode", () => {
    expect(normalizeRequestedViewMode("pages")).toBe("pages");
  });

  it("aliases legacy dashboard-surfaces to pages for back-compat", () => {
    expect(normalizeRequestedViewMode("dashboard-surfaces")).toBe("pages");
  });

  it("maps pages to the pages index category", () => {
    expect(indexCategoryForViewMode("pages")).toBe("pages");
  });

  it("keeps documents as the documents index category", () => {
    expect(normalizeRequestedViewMode("documents")).toBe("documents");
    expect(indexCategoryForViewMode("documents")).toBe("documents");
  });

  it("keeps agent profiles on the current inventory-backed index category", () => {
    expect(normalizeRequestedViewMode("agents")).toBe("agent-profiles");
    expect(indexCategoryForViewMode("agent-profiles")).toBe("agent-profiles");
  });

  it("maps scheduled-executions legacy URL to background-routines for one release", () => {
    expect(normalizeRequestedViewMode("scheduled-executions")).toBe("background-routines");
    expect(indexCategoryForViewMode("background-routines")).toBe("background-routines");
  });

  it("maps retired inbox/source views into notes and keeps prompts as its own view", () => {
    expect(normalizeRequestedViewMode("inbox")).toBe("notes");
    expect(normalizeRequestedViewMode("sources")).toBe("notes");
    expect(normalizeRequestedViewMode("prompts")).toBe("prompts");
  });

  it("maps the retired workflows view to skills (ADR-805 Model A fold target)", () => {
    expect(normalizeRequestedViewMode("workflows")).toBe("skills");
  });

  it("drops the deleted extensions-bundles view with no redirect target", () => {
    expect(normalizeRequestedViewMode("extensions-bundles")).toBeNull();
  });

  it("drops the deleted profile and memory views with no redirect target (no shim)", () => {
    // Profile is now Workspace-only; memory was the legacy deep-link for profile.
    // Both fall to the default view per rule 14 — no shim.
    expect(normalizeRequestedViewMode("profile")).toBeNull();
    expect(normalizeRequestedViewMode("memory")).toBeNull();
  });

  it("keeps legacy vault roots visible in the notes view during the migration window", () => {
    expect(itemMatchesViewMode({ metadata: { journey_category: "sources" } }, "notes")).toBe(true);
    expect(itemMatchesViewMode({ path: "C:/Users/intel/Projects/Au-vault/prompts/digest.md" }, "notes")).toBe(true);
    expect(itemMatchesViewMode({ metadata: { journey_category: "archive" } }, "notes")).toBe(false);
  });
});
