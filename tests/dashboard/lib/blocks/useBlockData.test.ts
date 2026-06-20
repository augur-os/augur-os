import { unwrapToolData } from "@/lib/blocks/useBlockData";

describe("unwrapToolData", () => {
  it("preserves markdown document payload metadata", () => {
    const payload = {
      content: "# ADR",
      editable: false,
      generated: true,
      path: "/tmp/.codex/skills/adr/SKILL.md",
    };

    expect(unwrapToolData(payload)).toBe(payload);
  });
});
