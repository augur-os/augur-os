import { fireEvent, render, waitFor } from "@testing-library/react";
import { toast } from "sonner";

import ContinueInSessionListener from "@/components/session/ContinueInSessionListener";

const mockSetState = jest.fn();
const mockSetEnlarged = jest.fn();
const mockOpenChat = jest.fn();
const mockSetSelectedCli = jest.fn();
const mockSetCliProcess = jest.fn();
const mockSetChatView = jest.fn();
const mockStore = {
  isOpen: false,
  mode: "operation",
  openChat: mockOpenChat,
  setSelectedCli: mockSetSelectedCli,
  setCliProcess: mockSetCliProcess,
  setChatView: mockSetChatView,
  setEnlarged: mockSetEnlarged,
};

jest.mock("sonner", () => ({
  toast: {
    warning: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock("@/lib/stores/chatStore", () => ({
  useChatStore: {
    getState: () => mockStore,
    setState: (...args: unknown[]) => mockSetState(...args),
  },
}));

describe("ContinueInSessionListener", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.clearAllMocks();
    mockStore.isOpen = false;
    mockStore.mode = "operation";
    global.fetch = jest.fn() as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("posts the event detail and opens IDE chat on success", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, cliId: "claude", pid: 1234 }),
    });

    render(<ContinueInSessionListener />);

    fireEvent(
      window,
      new CustomEvent("augur:continue-in-session", {
        detail: { sessionId: "session-11", answer: "Result text" },
      }),
    );

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/session/continue",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionId: "session-11",
            answer: "Result text",
            force: false,
          }),
        }),
      ),
    );

    expect(mockSetSelectedCli).toHaveBeenCalledWith("claude");
    expect(mockSetCliProcess).toHaveBeenCalledWith({
      cliId: "claude",
      status: "running",
      pid: 1234,
    });
    expect(mockSetChatView).toHaveBeenCalledWith("terminal");
    expect(mockOpenChat).toHaveBeenCalledWith({ mode: "ide" });
    expect(mockSetEnlarged).toHaveBeenCalledWith(true);
  });

  it("shows a warning toast for collisions and retries with force when requested", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ collision: true, message: "Session already active" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, cliId: "claude", pid: 4321 }),
      });

    render(<ContinueInSessionListener />);

    fireEvent(
      window,
      new CustomEvent("augur:continue-in-session", {
        detail: { sessionId: "session-12", answer: "More context" },
      }),
    );

    await waitFor(() =>
      expect(toast.warning).toHaveBeenCalledWith(
        "Session already active",
        expect.objectContaining({
          action: expect.objectContaining({ label: "View current" }),
          cancel: expect.objectContaining({ label: "Replace with new" }),
        }),
      ),
    );

    const warningArgs = (toast.warning as jest.Mock).mock.calls[0];
    const warningOptions = warningArgs[1] as {
      action?: { onClick?: () => void };
      cancel?: { onClick?: () => void };
    };

    warningOptions.action?.onClick?.({} as never);
    expect(mockOpenChat).toHaveBeenCalledWith({ mode: "ide" });
    expect(mockSetEnlarged).toHaveBeenCalledWith(true);

    warningOptions.cancel?.onClick?.({} as never);

    await waitFor(() =>
      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        "/api/session/continue",
        expect.objectContaining({
          body: JSON.stringify({
            sessionId: "session-12",
            answer: "More context",
            force: true,
          }),
        }),
      ),
    );
  });

  it("surfaces fetch failures as visible toasts", async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error("network down"));

    render(<ContinueInSessionListener />);

    fireEvent(
      window,
      new CustomEvent("augur:continue-in-session", {
        detail: { sessionId: "session-13", answer: "Context" },
      }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("network down"),
    );
  });
});
