import { transformIndexEntry } from "@/lib/browse/transforms";

describe("transformIndexEntry — prompts", () => {
  const baseEntry = {
    id: "vault/prompts/define-a-goal",
    title: "Define a Goal",
    description: "Define then act on a goal",
    source_path: "/vault/prompts/define-a-goal.md",
    source: "vault",
    metadata: { placeholders: ["goal"] },
  };

  it("carries the source badge in metadata", () => {
    const item = transformIndexEntry(baseEntry, "prompts");
    expect(item.metadata?.source).toBe("vault");
  });

  it("exposes a trigger action for prompt items", () => {
    const item = transformIndexEntry(baseEntry, "prompts");
    expect(item.actions?.some((a) => a.id.startsWith("trigger-"))).toBe(true);
  });

  it("passes the prompt body through to metadata", () => {
    const entry = {
      ...baseEntry,
      body: "State your {{goal}}.",
    };
    const item = transformIndexEntry(entry, "prompts");
    expect(item.metadata?.prompt).toBe("State your {{goal}}.");
  });
});
