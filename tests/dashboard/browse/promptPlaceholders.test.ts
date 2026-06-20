import { extractVariables, resolvePromptBody } from "@/lib/browse/promptPlaceholders";

describe("promptPlaceholders", () => {
  it("extracts {{slots}} in first-seen order, deduplicated", () => {
    expect(extractVariables("use {{goal}} then {{ctx}} then {{goal}}")).toEqual(["goal", "ctx"]);
  });

  it("returns [] when there are no slots", () => {
    expect(extractVariables("plain prompt")).toEqual([]);
  });

  it("substitutes provided values, leaving unknown slots intact", () => {
    expect(resolvePromptBody("hi {{name}} from {{place}}", { name: "Ada" }))
      .toBe("hi Ada from {{place}}");
  });

  it("produces correct results when called multiple times in succession", () => {
    // Exercises the lastIndex reset — module-level /g regex retains state
    expect(extractVariables("{{a}} {{b}}")).toEqual(["a", "b"]);
    expect(extractVariables("{{c}} {{d}}")).toEqual(["c", "d"]);
  });
});
