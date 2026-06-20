import { buildSelectionPrompt } from "@/lib/browse/selectionPrompt";
import type { BrowseItem } from "@/lib/browse/types";

function item(id: string, overrides: Partial<BrowseItem> = {}): BrowseItem {
  return {
    id,
    title: `Title ${id}`,
    description: "",
    hub: "workspace",
    primaryAction: { label: "Open", type: "open-file", target: `notes/${id}.md` },
    path: `notes/${id}.md`,
    ...overrides,
  };
}

describe("buildSelectionPrompt", () => {
  it("renders a numbered list with a known tab label and default intent", () => {
    const prompt = buildSelectionPrompt([item("a"), item("b")], "notes");
    expect(prompt).toContain("Selected 2 items from Browse · Notes:");
    expect(prompt).toContain('1. "Title a" — notes/a.md');
    expect(prompt).toContain('2. "Title b" — notes/b.md');
    expect(prompt.trimEnd().endsWith("<describe what you'd like to do with these>")).toBe(true);
  });

  it("uses singular wording for one item", () => {
    expect(buildSelectionPrompt([item("a")], "notes")).toContain("Selected 1 item from Browse");
  });

  it("prefers metadata source_path, then falls back to id when no path exists", () => {
    const withMeta = item("a", { path: undefined, metadata: { source_path: "/abs/a.md" } });
    const noPath = item("b", { path: undefined });
    const prompt = buildSelectionPrompt([withMeta, noPath], "documents");
    expect(prompt).toContain('1. "Title a" — /abs/a.md');
    expect(prompt).toContain('2. "Title b" — b');
  });

  it("uses a custom intent and falls back to the raw viewMode label", () => {
    const prompt = buildSelectionPrompt([item("a")], "skills", { intent: "Do the thing." });
    expect(prompt).toContain("from Browse · skills:");
    expect(prompt.trimEnd().endsWith("Do the thing.")).toBe(true);
  });

  it("collapses whitespace in titles so each item stays on one line", () => {
    const messy = item("a", { title: "Line one\nLine  two" });
    expect(buildSelectionPrompt([messy], "notes")).toContain('1. "Line one Line two" — notes/a.md');
  });
});
