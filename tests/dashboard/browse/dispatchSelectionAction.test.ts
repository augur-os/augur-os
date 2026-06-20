import { dispatchSelectionAction } from "@/lib/browse/dispatchSelectionAction";
import { SELECTION_ACTIONS } from "@/lib/browse/selectionActions";
import type { SelectionAction } from "@/lib/browse/selectionActions";
import type { BrowseItem } from "@/lib/browse/types";

function noteItem(id: string): BrowseItem {
  return {
    id,
    title: `Note ${id}`,
    description: "",
    hub: "workspace",
    primaryAction: { label: "Open", type: "open-file", target: `notes/${id}.md` },
    path: `notes/${id}.md`,
  };
}

const sendToChat = SELECTION_ACTIONS.find((a) => a.id === "send-to-chat")!;

function handlers() {
  return {
    onPrompt: jest.fn(),
    onInfo: jest.fn(),
    onError: jest.fn(),
    onAfterDispatch: jest.fn(),
  };
}

describe("dispatchSelectionAction", () => {
  it("dispatches the built prompt and runs the after-dispatch callback", async () => {
    const h = handlers();
    await dispatchSelectionAction(sendToChat, [noteItem("a")], "notes", h);
    expect(h.onPrompt).toHaveBeenCalledTimes(1);
    expect(h.onPrompt.mock.calls[0][0]).toContain("Selected 1 item from Browse · Notes:");
    expect(h.onAfterDispatch).toHaveBeenCalledTimes(1);
    expect(h.onError).not.toHaveBeenCalled();
  });

  it("does nothing for an empty selection", async () => {
    const h = handlers();
    await dispatchSelectionAction(sendToChat, [], "notes", h);
    expect(h.onPrompt).not.toHaveBeenCalled();
    expect(h.onAfterDispatch).not.toHaveBeenCalled();
  });

  it("reports a dropped count via onInfo", async () => {
    const h = handlers();
    const action: SelectionAction = {
      id: "x", label: "Sweep", icon: "Archive", appliesTo: () => true,
      build: () => ({ initialPrompt: "go", dropped: 2 }),
    };
    await dispatchSelectionAction(action, [noteItem("a")], "notes", h);
    expect(h.onInfo).toHaveBeenCalledWith(expect.stringContaining("2 item(s) skipped"));
    expect(h.onPrompt).toHaveBeenCalledWith("go");
  });

  it("calls onError and skips dispatch when the prompt is empty", async () => {
    const h = handlers();
    const action: SelectionAction = {
      id: "x", label: "Sweep", icon: "Archive", appliesTo: () => true,
      build: () => ({ initialPrompt: "", dropped: 1 }),
    };
    await dispatchSelectionAction(action, [noteItem("a")], "notes", h);
    expect(h.onPrompt).not.toHaveBeenCalled();
    expect(h.onError).toHaveBeenCalledWith(expect.stringContaining("Nothing to sweep"));
    expect(h.onAfterDispatch).not.toHaveBeenCalled();
  });

  it("calls onError with the thrown message when build rejects", async () => {
    const h = handlers();
    const action: SelectionAction = {
      id: "x", label: "Sweep", icon: "Archive", appliesTo: () => true,
      build: () => Promise.reject(new Error("boom")),
    };
    await dispatchSelectionAction(action, [noteItem("a")], "notes", h);
    expect(h.onError).toHaveBeenCalledWith("boom");
  });
});
