import { semanticHitToBrowseItem } from "@/app/(views)/browse/useBrowseState";
// NOTE: export the function (see Step 3) before this resolves.

describe("semanticHitToBrowseItem", () => {
  it("does not repeat the scope across hub, type, and tags for a knowledge note", () => {
    const item = semanticHitToBrowseItem(
      { scope: "knowledge", file: "/v/notes/2026-05-31-prompt-run-demo-readiness-live-wow.md",
        label: "Run Demo Readiness (Live Wow)" } as any,
      0, "balanced",
    );
    const chips = [item.hub, item.typeBadge, ...(item.tags ?? [])].filter(Boolean);
    const knowledgeCount = chips.filter((c) => c.toLowerCase() === "knowledge").length;
    expect(knowledgeCount).toBeLessThanOrEqual(1);
  });

  it("prefers a frontmatter label/title over the filename slug", () => {
    const item = semanticHitToBrowseItem(
      { scope: "knowledge", file: "/v/notes/2026-05-31-prompt-run-demo-readiness-live-wow.md",
        label: "Run Demo Readiness (Live Wow)" } as any,
      0, "balanced",
    );
    expect(item.title).toBe("Run Demo Readiness (Live Wow)");
  });
});
