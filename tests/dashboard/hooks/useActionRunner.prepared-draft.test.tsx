import { act, renderHook, waitFor } from "@testing-library/react";
import { useActionRunner } from "@/hooks/useActionRunner";
import { useChatStore } from "@/lib/stores/chatStore";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("sonner", () => ({
  toast: {
    loading: jest.fn(() => "toast-id"),
    success: jest.fn(),
    error: jest.fn(),
    dismiss: jest.fn(),
    info: jest.fn(),
  },
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

jest.mock("@/lib/chat/context-envelope", () => ({
  resolveContext: jest.fn().mockResolvedValue(null),
  buildPromptFromEnvelope: jest.fn(),
}));

describe("useActionRunner prepared draft routing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    act(() => {
      useChatStore.setState({
        isOpen: false,
        chatView: "terminal",
        embeddedAction: null,
        preparedActionDraft: null,
        isEnlarged: false,
      });
    });
  });

  it("routes ide dispatch to a prepared chat draft instead of embeddedAction", async () => {
    const { result } = renderHook(() => useActionRunner());

    await act(async () => {
      await result.current.runAction({
        id: "browse.deep-search",
        label: "Ask AI",
        description: "Investigate Browse results",
        dispatch: "ide",
        page: "browse",
        tier: "deep",
        prompt: "Inspect source paths.",
      });
    });

    const state = useChatStore.getState();
    expect(state.isOpen).toBe(true);
    expect(state.chatView).toBe("terminal");
    expect(state.embeddedAction).toBeNull();
    expect(state.preparedActionDraft).toMatchObject({
      id: "browse.deep-search",
      label: "Ask AI",
      description: "Investigate Browse results",
      prompt: expect.stringContaining("Inspect source paths."),
      page: "browse",
      tier: "deep",
      dispatch: "ide",
    });
    expect(
      (mcpCall as jest.Mock).mock.calls.some(([tool]) => tool === "resolve-client"),
    ).toBe(false);
  });

  it("routes oneshot dispatch to a prepared chat draft", async () => {
    const { result } = renderHook(() => useActionRunner());

    await act(async () => {
      await result.current.runAction({
        id: "summarize",
        label: "Summarize",
        description: "Summarize selected data",
        dispatch: "oneshot",
        page: "brain",
        prompt: "Summarize this.",
      });
    });

    expect(useChatStore.getState().preparedActionDraft).toMatchObject({
      id: "summarize",
      dispatch: "oneshot",
      label: "Summarize",
    });
  });

  it("keeps fire dispatch on the direct MCP execution path", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({ success: true, message: "done" });
    const { result } = renderHook(() => useActionRunner());

    await act(async () => {
      await result.current.runAction({
        id: "browse.reindex",
        label: "Reindex",
        description: "Reindex Browse",
        dispatch: "fire",
        page: "browse",
        mcp_tools: ["reindex-browse-category"],
        args: { category: "skills" },
      });
    });

    await waitFor(() => {
      expect(mcpCall).toHaveBeenCalledWith(
        "reindex-browse-category",
        expect.objectContaining({
          category: "skills",
          context: expect.objectContaining({
            page: expect.any(String),
          }),
        }),
      );
    });
    expect(useChatStore.getState().preparedActionDraft).toBeNull();
  });
});
