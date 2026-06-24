import { runDeleteSelection } from "@/lib/browse/deleteSelection";
import type { BrowseItem } from "@/lib/browse/types";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

const items: BrowseItem[] = [
  { id: "a", path: "/docs/pages/p.html", title: "P", primaryAction: {} as any },
  { id: "b", path: "/repo/note.md", title: "N", primaryAction: {} as any },
];

describe("runDeleteSelection", () => {
  it("trashes simple items, sweeps dependency items, after confirm", async () => {
    const callTool = jest.fn()
      .mockResolvedValueOnce({ trash: ["a"], sweep: ["b"], blocked: [] }) // triage
      .mockResolvedValueOnce({ trashed: ["/docs/pages/p.html"], refused: [] }); // browse-trash
    const dispatchSweep = jest.fn().mockResolvedValue(undefined);
    const reindexCategory = jest.fn().mockResolvedValue(undefined);
    const res = await runDeleteSelection(items, "pages", {
      callTool,
      confirm: async () => true,
      reindexCategory,
      dispatchSweep,
      onInfo: () => {},
      onError: () => {},
    });
    expect(callTool).toHaveBeenNthCalledWith(1, "browse-delete-triage", { items: expect.any(Array) });
    expect(callTool).toHaveBeenNthCalledWith(2, "browse-trash", { paths: ["/docs/pages/p.html"] });
    expect(dispatchSweep).toHaveBeenCalledTimes(1);
    expect(reindexCategory).toHaveBeenCalledWith("pages");
    expect(res).toEqual({ trashed: 1, swept: 1, blocked: [] });
  });

  it("does nothing when the user cancels", async () => {
    const callTool = jest.fn().mockResolvedValueOnce({ trash: ["a"], sweep: [], blocked: [] });
    const res = await runDeleteSelection(items, "pages", {
      callTool,
      confirm: async () => false,
      reindexCategory: jest.fn(),
      dispatchSweep: jest.fn(),
      onInfo: () => {},
      onError: () => {},
    });
    expect(callTool).toHaveBeenCalledTimes(1); // triage only
    expect(res).toEqual({ trashed: 0, swept: 0, blocked: [] });
  });

  it("trashes simple items and blocks sweep items when dispatchSweep is null (wiki/archive view)", async () => {
    const callTool = jest.fn()
      .mockResolvedValueOnce({ trash: ["a"], sweep: ["b"], blocked: [] }) // triage
      .mockResolvedValueOnce({ trashed: ["/docs/pages/p.html"], refused: [] }); // browse-trash
    const onInfo = jest.fn();
    const onError = jest.fn();
    const reindexCategory = jest.fn().mockResolvedValue(undefined);
    const res = await runDeleteSelection(items, "wiki", {
      callTool,
      confirm: async () => true,
      reindexCategory,
      dispatchSweep: null,
      onInfo,
      onError,
    });
    // trash items still go through
    expect(callTool).toHaveBeenNthCalledWith(2, "browse-trash", { paths: ["/docs/pages/p.html"] });
    expect(res.trashed).toBe(1);
    // sweep items appear in blocked with a clear reason
    expect(res.blocked).toEqual([{ id: "b", reason: "no sweep available for this view" }]);
    expect(res.swept).toBe(0);
    // user gets an informational toast, nothing throws
    expect(onInfo).toHaveBeenCalledWith(expect.stringContaining("need review"));
    expect(onError).not.toHaveBeenCalled();
  });
});
