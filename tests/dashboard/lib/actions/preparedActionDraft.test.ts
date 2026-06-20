import {
  composePreparedActionPrompt,
  isPreparedActionDispatch,
  type PreparedActionDraft,
} from "@/lib/actions/preparedActionDraft";

const draft: PreparedActionDraft = {
  id: "browse.deep-search",
  label: "Ask AI",
  description: "Investigate Browse results",
  prompt: "Inspect the selected sources before answering.",
  page: "browse",
  tier: "deep",
  dispatch: "ide",
  createdAt: "2026-05-24T00:00:00.000Z",
};

describe("preparedActionDraft helpers", () => {
  it("returns the preserved prompt exactly when user remarks are empty", () => {
    expect(composePreparedActionPrompt(draft, "   ")).toBe(
      "Inspect the selected sources before answering.",
    );
  });

  it("prepends user remarks with a stable system prompt separator", () => {
    expect(composePreparedActionPrompt(draft, "Use the newest deck.")).toBe(
      [
        "Use the newest deck.",
        "",
        "--- SYSTEM PROMPT ---",
        "",
        "Inspect the selected sources before answering.",
      ].join("\n"),
    );
  });

  it("classifies AI dispatch modes as prepared action dispatches", () => {
    expect(isPreparedActionDispatch("ide")).toBe(true);
    expect(isPreparedActionDispatch("chat")).toBe(true);
    expect(isPreparedActionDispatch("oneshot")).toBe(true);
    expect(isPreparedActionDispatch("auto")).toBe(true);
    expect(isPreparedActionDispatch("fire")).toBe(false);
    expect(isPreparedActionDispatch("modal")).toBe(false);
    expect(isPreparedActionDispatch("api")).toBe(false);
  });
});
