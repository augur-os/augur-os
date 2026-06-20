import { buildSweepPrompt } from "@/lib/browse/sweepPrompt";

describe("buildSweepPrompt", () => {
  it("builds an apply-oriented agent prompt with selection, tools, filters, and recovery", () => {
    const prompt = buildSweepPrompt({
      sourceTab: "sources",
      selectionId: "browse-sweep-1",
      targetCount: 3,
      refusalCount: 1,
      filterSummary: { search: "venture", hub: "workspace" },
    });

    expect(prompt).toContain("Sweep visible");
    expect(prompt).toContain("browse-sweep-1");
    expect(prompt).toContain("Target count: 3");
    expect(prompt).toContain("Refusal count: 1");
    expect(prompt).toContain('"search":"venture"');
    expect(prompt).toContain("apply-oriented");
    expect(prompt).toContain("ADR-736");
    expect(prompt).toContain("hygiene-create-selection");
    expect(prompt).toContain("hygiene-scan-selection");
    expect(prompt).toContain("hygiene-apply-selection");
    expect(prompt).toContain("user Q&A");
    expect(prompt).toContain("Archive tab");
    expect(prompt).toContain("manual recovery");
  });
});
