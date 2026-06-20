/**
 * @jest-environment jsdom
 */
import { act, renderHook, waitFor } from "@testing-library/react";

jest.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

jest.mock("@/lib/chat/context-envelope", () => ({
  resolveContext: jest.fn(() => ({})),
}));

let mockAirplaneState = {
  airplaneMode: false,
  airplaneModeReady: true,
  airplaneBackendReady: false,
  airplaneLocalModel: null as string | null,
  airplaneModeError: null as string | null,
};

jest.mock("@/lib/stores/airplaneModeStore", () => ({
  useAirplaneModeStore: () => mockAirplaneState,
}));

const setCliProcess = jest.fn();
const chatStoreState = {
  selectedCli: "claude",
  cliProcess: { cliId: "claude", status: "running", pid: 123 },
  attachedFiles: [],
  sessionId: "session-1",
  setSelectedCli: jest.fn(),
  setCliProcess,
  addAttachedFile: jest.fn(),
  removeAttachedFile: jest.fn(),
  clearAttachedFiles: jest.fn(),
};

jest.mock("@/lib/stores/chatStore", () => ({
  useChatStore: () => chatStoreState,
}));

import { useCliChat } from "@/features/hooks/useCliChat";

describe("useCliChat airplane transitions", () => {
  const originalFetch = global.fetch;
  const originalCrypto = global.crypto;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    mockAirplaneState = {
      airplaneMode: false,
      airplaneModeReady: true,
      airplaneBackendReady: false,
      airplaneLocalModel: null,
      airplaneModeError: null,
    };
    chatStoreState.cliProcess = { cliId: "claude", status: "running", pid: 123 };
    chatStoreState.sessionId = "session-1";
    global.crypto = {
      ...originalCrypto,
      randomUUID: jest.fn(() => "message-id"),
    } as Crypto;
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === "/api/cli/configs") {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ configs: [], default_cli: "claude" }),
        } as Response);
      }
      if (String(input).startsWith("/api/chat/messages?")) {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ messages: [] }),
        } as Response);
      }
      if (input === "/api/chat/messages") {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({}),
        } as Response);
      }
      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    global.crypto = originalCrypto;
  });

  it("does not append an airplane transition message on initial load", async () => {
    renderHook(() => useCliChat());

    await act(async () => {
      await Promise.resolve();
    });

    expect(
      (global.fetch as jest.Mock).mock.calls.filter(
        ([input]) => input === "/api/chat/messages",
      ),
    ).toHaveLength(0);
  });

  it("appends and persists exactly one transition message when airplane mode changes during a running CLI session", async () => {
    const { result, rerender } = renderHook(() => useCliChat());

    await act(async () => {
      await Promise.resolve();
    });

    mockAirplaneState = {
      ...mockAirplaneState,
      airplaneMode: true,
      airplaneBackendReady: true,
      airplaneLocalModel: "qwen3.5:9b",
    };

    rerender();

    await waitFor(() => {
      expect(result.current.messages).toEqual([
        expect.objectContaining({
          role: "system",
          content:
            "Airplane mode ON \u2014 new chats will use local model (qwen3.5:9b). This chat keeps its current backend; restart it (Stop then Start) to apply.",
        }),
      ]);
    });

    const persisted = (global.fetch as jest.Mock).mock.calls.filter(
      ([input]) => input === "/api/chat/messages",
    );
    expect(persisted).toHaveLength(1);
    expect(JSON.parse(persisted[0][1].body)).toEqual(
      expect.objectContaining({
        sessionId: "session-1",
        message: expect.objectContaining({
          role: "system",
          content:
            "Airplane mode ON \u2014 new chats will use local model (qwen3.5:9b). This chat keeps its current backend; restart it (Stop then Start) to apply.",
        }),
      }),
    );
  });

  it("appends an OFF transition message when airplane mode turns off during a running CLI session", async () => {
    mockAirplaneState = {
      ...mockAirplaneState,
      airplaneMode: true,
      airplaneBackendReady: true,
      airplaneLocalModel: "qwen3.5:9b",
    };
    const { result, rerender } = renderHook(() => useCliChat());

    await act(async () => {
      await Promise.resolve();
    });

    mockAirplaneState = {
      ...mockAirplaneState,
      airplaneMode: false,
      airplaneBackendReady: false,
      airplaneLocalModel: null,
    };

    rerender();

    await waitFor(() => {
      expect(result.current.messages).toEqual([
        expect.objectContaining({
          role: "system",
          content:
            "Airplane mode OFF \u2014 new chats will use cloud. This chat keeps its current backend; restart it (Stop then Start) to apply.",
        }),
      ]);
    });
  });

  it("does not append a transition message when no CLI is running", async () => {
    chatStoreState.cliProcess = null;
    const { result, rerender } = renderHook(() => useCliChat());

    await act(async () => {
      await Promise.resolve();
    });

    mockAirplaneState = {
      ...mockAirplaneState,
      airplaneMode: true,
      airplaneBackendReady: true,
      airplaneLocalModel: "qwen3.5:9b",
    };
    rerender();

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.messages).toEqual([]);
  });

  it("appends a transition message when the configured local model changes during a running airplane session", async () => {
    mockAirplaneState = {
      ...mockAirplaneState,
      airplaneMode: true,
      airplaneBackendReady: true,
      airplaneLocalModel: "qwen3.5:9b",
    };
    const { result, rerender } = renderHook(() => useCliChat());

    await act(async () => {
      await Promise.resolve();
    });

    mockAirplaneState = {
      ...mockAirplaneState,
      airplaneLocalModel: "llama3.2:3b",
    };

    rerender();

    await waitFor(() => {
      expect(result.current.messages).toEqual([
        expect.objectContaining({
          role: "system",
          content:
            "Airplane local model preference set to llama3.2:3b. This chat keeps its current backend \u2014 restart it (Stop then Start) to apply.",
        }),
      ]);
    });

    const persisted = (global.fetch as jest.Mock).mock.calls.filter(
      ([input]) => input === "/api/chat/messages",
    );
    expect(persisted).toHaveLength(1);
    expect(JSON.parse(persisted[0][1].body)).toEqual(
      expect.objectContaining({
        sessionId: "session-1",
        message: expect.objectContaining({
          role: "system",
          content:
            "Airplane local model preference set to llama3.2:3b. This chat keeps its current backend \u2014 restart it (Stop then Start) to apply.",
        }),
      }),
    );
  });

  it("adds a fenced setup hint system message for 409 CLI startup failures", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      if (input === "/api/cli/configs") {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ configs: [], default_cli: "claude" }),
        } as Response);
      }
      if (String(input).startsWith("/api/chat/messages?")) {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ messages: [] }),
        } as Response);
      }
      if (input === "/api/cli") {
        return Promise.resolve({
          ok: false,
          status: 409,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({
            error: "Local launch is not ready",
            setup_hint: "Pull the model: ollama pull qwen3.5:9b",
            reason: "model_missing",
          }),
        } as Response);
      }
      if (input === "/api/chat/messages") {
        return Promise.resolve({
          ok: true,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({}),
        } as Response);
      }
      return Promise.reject(new Error(`Unexpected fetch: ${String(input)}`));
    }) as unknown as typeof fetch;

    chatStoreState.cliProcess = null;
    const { result } = renderHook(() => useCliChat());

    await act(async () => {
      await result.current.startCli("claude", { airplaneMode: true });
    });

    expect(result.current.messages).toEqual([
      expect.objectContaining({
        role: "system",
        content:
          "Failed to start claude: Local launch is not ready\n\nSetup hint:\n```bash\nPull the model: ollama pull qwen3.5:9b\n```",
      }),
    ]);
    expect(setCliProcess).toHaveBeenCalledWith({ cliId: "claude", status: "error" });
  });
});
