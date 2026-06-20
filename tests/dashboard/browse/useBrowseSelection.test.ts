import { act, renderHook } from "@testing-library/react";
import { useBrowseSelection } from "@/lib/browse/useBrowseSelection";
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

describe("useBrowseSelection", () => {
  beforeEach(() => {
    act(() => useBrowseSelection.getState().reset());
  });

  it("enters and exits select mode, clearing on exit", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.enter());
    act(() => result.current.toggle(item("a")));
    expect(result.current.selectionMode).toBe(true);
    expect(result.current.selected.size).toBe(1);
    act(() => result.current.exit());
    expect(result.current.selectionMode).toBe(false);
    expect(result.current.selected.size).toBe(0);
  });

  it("toggle adds then removes an item by id", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.toggle(item("a")));
    expect(result.current.isSelected("a")).toBe(true);
    act(() => result.current.toggle(item("a")));
    expect(result.current.isSelected("a")).toBe(false);
  });

  it("selectAllVisible merges without duplicating", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.toggle(item("a")));
    act(() => result.current.selectAllVisible([item("a"), item("b"), item("c")]));
    expect(result.current.selected.size).toBe(3);
    expect(result.current.selectedItemList().map((i) => i.id).sort()).toEqual(["a", "b", "c"]);
  });

  it("clear empties selection but keeps select mode; reset clears both", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.enter());
    act(() => result.current.selectAllVisible([item("a"), item("b")]));
    act(() => result.current.clear());
    expect(result.current.selected.size).toBe(0);
    expect(result.current.selectionMode).toBe(true);
    act(() => result.current.toggle(item("a")));
    act(() => result.current.reset());
    expect(result.current.selected.size).toBe(0);
    expect(result.current.selectionMode).toBe(false);
  });

  it("toggleSelectionMode turns on, then off and clears", () => {
    const { result } = renderHook(() => useBrowseSelection());
    act(() => result.current.toggleSelectionMode());
    expect(result.current.selectionMode).toBe(true);
    act(() => result.current.toggle(item("a")));
    act(() => result.current.toggleSelectionMode());
    expect(result.current.selectionMode).toBe(false);
    expect(result.current.selected.size).toBe(0);
  });
});
