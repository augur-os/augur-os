/**
 * @jest-environment jsdom
 */
import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/components/browse/ResultCard", () => ({
  __esModule: true,
  default: ({
    result,
    onContinueInSession,
  }: {
    result: {
      promptId: string;
      input: string;
      answer: string;
      sessionId: string;
      cliId: string;
      durationMs: number;
    };
    onContinueInSession: (sessionId: string) => void;
  }) => (
    <article data-testid="result-card">
      <div>{result.promptId}</div>
      <div>{result.input}</div>
      <div>{result.answer}</div>
      <div>{result.sessionId}</div>
      <div>{result.cliId}</div>
      <div>{String(result.durationMs)}</div>
      {result.sessionId ? (
        <button
          type="button"
          onClick={() => onContinueInSession(result.sessionId)}
        >
          Continue in session
        </button>
      ) : null}
    </article>
  ),
}));

type EventListenerMap = Record<string, Array<(event: { data: string }) => void>>;

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;

  listeners: EventListenerMap = {};

  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, callback: (event: { data: string }) => void) {
    this.listeners[type] ??= [];
    this.listeners[type].push(callback);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, payload: Record<string, unknown>) {
    for (const callback of this.listeners[type] ?? []) {
      callback({ data: JSON.stringify(payload) });
    }
  }
}

const mockFetch = jest.fn();
const mockEventSource = MockEventSource as unknown as typeof EventSource & {
  instances: MockEventSource[];
};

Object.defineProperty(globalThis, "EventSource", {
  value: mockEventSource,
  configurable: true,
});

Object.defineProperty(globalThis, "fetch", {
  value: mockFetch,
  configurable: true,
  writable: true,
});

const { CommandCard } = require("@/components/browse/CommandCard") as typeof import("@/components/browse/CommandCard");

function makeResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderCommand(
  command: React.ComponentProps<typeof CommandCard>["command"],
  onResult = jest.fn(),
) {
  render(<CommandCard command={command} onResult={onResult} />);
  return onResult;
}

describe("CommandCard", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockEventSource.instances.length = 0;
  });

  it("renders label, description, command, and Run button", () => {
    renderCommand({
      id: "knowledge-refresh",
      label: "Knowledge refresh",
      description: "Refreshes knowledge sources",
      command: "/knowledge refresh",
    });

    expect(screen.getByRole("heading", { name: "Knowledge refresh" })).toBeInTheDocument();
    expect(screen.getByText("Refreshes knowledge sources")).toBeInTheDocument();
    expect(screen.getByText("/knowledge refresh")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
  });

  it("posts only the raw command prompt body", async () => {
    renderCommand({
      id: "command-body",
      label: "Command body",
      description: "Checks payload shape",
      command: "/knowledge refresh",
    });

    mockFetch.mockResolvedValueOnce(makeResponse({ execId: "exec-1" }));

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/cli/exec");
    expect(init).toMatchObject({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    const parsedBody = JSON.parse((init as RequestInit).body as string) as Record<
      string,
      unknown
    >;
    expect(parsedBody).toEqual({ prompt: "/knowledge refresh" });
    expect(Object.keys(parsedBody)).toEqual(["prompt"]);
    expect(parsedBody).not.toHaveProperty("context");
    expect(parsedBody).not.toHaveProperty("pageContext");
    expect(parsedBody).not.toHaveProperty("envelope");
  });

  it("disables Run while the exec request is running", async () => {
    let resolveFetch!: (value: Response) => void;
    mockFetch.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    renderCommand({
      id: "running",
      label: "Running",
      description: "Waits for the request",
      command: "/knowledge refresh",
    });

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();

    resolveFetch(makeResponse({ execId: "exec-running" }));
    await waitFor(() => expect(mockEventSource.instances).toHaveLength(1));
  });

  it("renders the ResultCard when the SSE done payload arrives", async () => {
    const onResult = renderCommand({
      id: "stream-done",
      label: "Stream done",
      description: "Waits for SSE completion",
      command: "/knowledge refresh",
    });

    mockFetch.mockResolvedValueOnce(makeResponse({ execId: "exec-done" }));

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => expect(mockEventSource.instances).toHaveLength(1));

    await act(async () => {
      mockEventSource.instances[0].emit("message", {
        type: "done",
        answer: "Final answer",
        sessionId: "session-123",
        cliId: "codex",
        durationMs: 1200,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("result-card")).toHaveTextContent("Final answer"),
    );

    expect(screen.getByTestId("result-card")).toHaveTextContent("/knowledge refresh");
    expect(onResult).toHaveBeenCalledWith(
      expect.objectContaining({
        promptId: "stream-done",
        input: "/knowledge refresh",
        answer: "Final answer",
        sessionId: "session-123",
        cliId: "codex",
        durationMs: 1200,
        timestamp: expect.any(Date),
      }),
    );
  });

  it("shows an inline error when the API responds with an error", async () => {
    renderCommand({
      id: "api-error",
      label: "API error",
      description: "Reports failures",
      command: "/knowledge refresh",
    });

    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: "Exec failed" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Exec failed");
    expect(screen.getByRole("button", { name: "Run" })).toBeEnabled();
  });

  it("shows an inline error when the SSE error payload arrives", async () => {
    renderCommand({
      id: "stream-error",
      label: "Stream error",
      description: "Reports SSE failures",
      command: "/knowledge refresh",
    });

    mockFetch.mockResolvedValueOnce(makeResponse({ execId: "exec-error" }));

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => expect(mockEventSource.instances).toHaveLength(1));

    await act(async () => {
      mockEventSource.instances[0].emit("message", {
        type: "error",
        error: "CLI failed",
      });
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("CLI failed");
    expect(screen.getByRole("button", { name: "Run" })).toBeEnabled();
  });

  it("dispatches augur:continue-in-session with session id and answer", async () => {
    const onContinue = jest.fn();

    const listener = (event: Event) => {
      const customEvent = event as CustomEvent<{ sessionId: string; answer: string }>;
      onContinue(customEvent.detail);
    };

    window.addEventListener("augur:continue-in-session", listener);

    renderCommand({
      id: "continue-session",
      label: "Continue session",
      description: "Open a live session",
      command: "/knowledge refresh",
    });

    mockFetch.mockResolvedValueOnce(makeResponse({ execId: "exec-continue" }));

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => expect(mockEventSource.instances).toHaveLength(1));

    await act(async () => {
      mockEventSource.instances[0].emit("message", {
        type: "done",
        answer: "Use this answer",
        sessionId: "session-999",
        cliId: "claude",
        durationMs: 900,
      });
    });

    await waitFor(() =>
      expect(screen.getByTestId("result-card")).toHaveTextContent("Use this answer"),
    );

    fireEvent.click(screen.getByRole("button", { name: "Continue in session" }));

    expect(onContinue).toHaveBeenCalledWith({
      sessionId: "session-999",
      answer: "Use this answer",
    });

    window.removeEventListener("augur:continue-in-session", listener);
  });
});
