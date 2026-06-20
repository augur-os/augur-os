import {
  PROJECT_INVENTORY_QUESTION_PROMPT,
  buildProjectInventoryQuestionDraft,
  canAskProjectInventoryQuestion,
  sumProjectProblemCounts,
} from "@/lib/browse/projectQuestion";

describe("projectQuestion", () => {
  it("only enables the project question for an active project brain context", () => {
    expect(canAskProjectInventoryQuestion({ scope: "all", label: "All Brains" })).toBe(false);
    expect(canAskProjectInventoryQuestion({ scope: "brain", brain_id: "personal", label: "Personal" })).toBe(false);
    expect(canAskProjectInventoryQuestion({ scope: "brain", brain_id: "project-demo", label: "Demo", project_root: "/tmp/demo" })).toBe(true);
  });

  it("builds an answer-only prepared chat draft with folder context", () => {
    const draft = buildProjectInventoryQuestionDraft(
      { scope: "brain", brain_id: "project-demo", label: "Demo", project_root: "/tmp/demo" },
      { inventoryCount: 12, problemCount: 2 },
    );
    expect(draft.id).toBe("ask-project-inventory-summary");
    expect(draft.label).toBe("Ask Augur about this project");
    expect(draft.page).toBe("/browse");
    expect(draft.dispatch).toBe("chat");
    expect(draft.prompt).toContain(PROJECT_INVENTORY_QUESTION_PROMPT);
    expect(draft.prompt).toContain("Active folder: Demo");
    expect(draft.prompt).toContain("/tmp/demo");
    expect(draft.prompt).toContain("Inventory records visible in Browse: 12");
    expect(draft.prompt).toContain("Problem badges visible in Browse: 2");
    expect(draft.prompt).toContain("Do not save or retain");
  });

  it("sums valid visible problem badge counts", () => {
    expect(sumProjectProblemCounts([
      { metadata: { problem_count: "3" } },
      { metadata: { problem_count: 3 } },
      { metadata: { problem_count: "0" } },
      { metadata: { problem_count: "-4" } },
      { metadata: { problem_count: "not-a-number" } },
      { metadata: { problem_count: "Infinity" } },
      { metadata: {} },
      {},
    ])).toBe(6);
  });
});
