import { runCliExecPrompt } from "@/lib/browse/cliExecClient";
import { waitFor } from "@testing-library/react";

class MockEventSource {
  static instances: MockEventSource[] = [];
  readonly url: string;
  close = jest.fn();
  private listeners: Record<string, Array<(event: MessageEvent<string>) => void>> = {};

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener];
  }

  removeEventListener() {}

  emit(type: string, payload: unknown) {
    for (const listener of this.listeners[type] ?? []) {
      listener({ data: JSON.stringify(payload) } as MessageEvent<string>);
    }
  }
}

describe("runCliExecPrompt", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    (global as typeof globalThis & { EventSource: typeof MockEventSource }).EventSource =
      MockEventSource;
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ execId: "exec-123" }),
    }) as unknown as typeof fetch;
  });

  it("posts the raw prompt and resolves the SSE done payload", async () => {
    const promise = runCliExecPrompt("Run /wiki status");

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/cli/exec",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ prompt: "Run /wiki status" }),
      }),
    );
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    expect(MockEventSource.instances[0].url).toBe(
      "/api/cli/exec/stream?id=exec-123",
    );

    MockEventSource.instances[0].emit("message", {
      type: "done",
      answer: "ok",
      sessionId: "session-1",
      cliId: "codex",
      durationMs: 42,
    });

    await expect(promise).resolves.toEqual({
      answer: "ok",
      sessionId: "session-1",
      cliId: "codex",
      durationMs: 42,
    });
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });

  it("rejects stream error payloads", async () => {
    const promise = runCliExecPrompt("bad");
    await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));
    MockEventSource.instances[0].emit("message", {
      type: "error",
      error: "failed",
    });

    await expect(promise).rejects.toThrow("failed");
  });
});
