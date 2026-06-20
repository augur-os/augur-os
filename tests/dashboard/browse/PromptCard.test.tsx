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

const { PromptCard } = require("@/components/browse/PromptCard") as typeof import("@/components/browse/PromptCard");

function makeResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPrompt(
  prompt: React.ComponentProps<typeof PromptCard>["prompt"],
  onResult = jest.fn(),
) {
  render(<PromptCard prompt={prompt} onResult={onResult} />);
  return onResult;
}

describe("PromptCard", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockEventSource.instances.length = 0;
  });

  it("renders label and description", () => {
    renderPrompt({
      id: "draft-summary",
      label: "Draft summary",
      description: "Summarize the current draft",
      prompt: "Summarize {{topic}}.",
    });

    expect(screen.getByText("Draft summary")).toBeInTheDocument();
    expect(screen.getByText("Summarize the current draft")).toBeInTheDocument();
  });

  it("shows a Run button and no textbox when the prompt has no variables", () => {
    renderPrompt({
      id: "one-shot",
      label: "One shot",
      description: "Run immediately",
      prompt: "Say hello.",
    });

    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("shows one input per unique variable", () => {
    renderPrompt({
      id: "multi-var",
      label: "Multi var",
      description: "Needs two values",
      prompt: "Hello {{name}}, meet {{role}}.",
    });

    expect(screen.getAllByRole("textbox")).toHaveLength(2);
    expect(screen.getByLabelText("name")).toBeInTheDocument();
    expect(screen.getByLabelText("role")).toBeInTheDocument();
  });

  it("reuses a repeated variable in the resolved prompt", async () => {
    renderPrompt({
      id: "repeat-var",
      label: "Repeat var",
      description: "Uses the same variable twice",
      prompt: "Say hi to {{name}} and {{name}}.",
    });

    fireEvent.change(screen.getByLabelText("name"), {
      target: { value: "Ada" },
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
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      prompt: "Say hi to Ada and Ada.",
    });
  });

  it("preserves literal unsupported handlebars text in the raw prompt", async () => {
    renderPrompt({
      id: "literal-handlebars",
      label: "Literal handlebars",
      description: "Keeps template examples",
      prompt: "Loop {{#each items}} and name {{name}}.",
    });

    fireEvent.change(screen.getByLabelText("name"), {
      target: { value: "Ada" },
    });

    mockFetch.mockResolvedValueOnce(makeResponse({ execId: "exec-literal" }));

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      prompt: "Loop {{#each items}} and name Ada.",
    });
  });

  it("posts only the resolved prompt body", async () => {
    renderPrompt({
      id: "payload-check",
      label: "Payload check",
      description: "Checks request shape",
      prompt: "Plan for {{topic}}.",
    });

    fireEvent.change(screen.getByLabelText("topic"), {
      target: { value: "shipping" },
    });

    mockFetch.mockResolvedValueOnce(makeResponse({ execId: "exec-2" }));

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
    expect(parsedBody).toEqual({ prompt: "Plan for shipping." });
    expect(Object.keys(parsedBody)).toEqual(["prompt"]);
    expect(parsedBody).not.toHaveProperty("context");
    expect(parsedBody).not.toHaveProperty("pageContext");
    expect(parsedBody).not.toHaveProperty("envelope");
  });

  it("disables controls while the exec request is running", async () => {
    let resolveFetch!: (value: Response) => void;
    mockFetch.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    renderPrompt({
      id: "disable-state",
      label: "Disable state",
      description: "Waits for the request",
      prompt: "Run {{topic}}.",
    });

    fireEvent.change(screen.getByLabelText("topic"), {
      target: { value: "checks" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
    expect(screen.getByLabelText("topic")).toBeDisabled();

    resolveFetch(makeResponse({ execId: "exec-3" }));
    await waitFor(() => expect(mockEventSource.instances).toHaveLength(1));
  });

  it("renders the ResultCard and calls onResult when the SSE done payload arrives", async () => {
    const onResult = renderPrompt({
      id: "stream-done",
      label: "Stream done",
      description: "Waits for SSE completion",
      prompt: "Summarize {{topic}}.",
    });

    fireEvent.change(screen.getByLabelText("topic"), {
      target: { value: "release notes" },
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

    expect(onResult).toHaveBeenCalledWith(
      expect.objectContaining({
        promptId: "stream-done",
        input: "Summarize release notes.",
        answer: "Final answer",
        sessionId: "session-123",
        cliId: "codex",
        durationMs: 1200,
        timestamp: expect.any(Date),
      }),
    );
  });

  it("shows an inline error and re-enables Run when the SSE error payload arrives", async () => {
    renderPrompt({
      id: "stream-error",
      label: "Stream error",
      description: "Reports failures",
      prompt: "Summarize {{topic}}.",
    });

    fireEvent.change(screen.getByLabelText("topic"), {
      target: { value: "release notes" },
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

  it("dispatches augur:continue-in-session with the session id and answer", async () => {
    const onContinue = jest.fn();
    const listener = jest.fn((event: Event) => {
      const customEvent = event as CustomEvent<{ sessionId: string; answer: string }>;
      onContinue(customEvent.detail);
    });

    window.addEventListener("augur:continue-in-session", listener);

    renderPrompt({
      id: "continue-session",
      label: "Continue session",
      description: "Open a live session",
      prompt: "Answer {{topic}}.",
    });

    fireEvent.change(screen.getByLabelText("topic"), {
      target: { value: "the question" },
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

  it("does not open a stale stream after unmount during exec request", async () => {
    let resolveFetch!: (value: Response) => void;
    mockFetch.mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const { unmount } = render(
      <PromptCard
        prompt={{
          id: "stale-request",
          label: "Stale request",
          description: "Unmounts before fetch completes",
          prompt: "Run immediately.",
        }}
        onResult={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(mockFetch).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      resolveFetch(makeResponse({ execId: "stale-exec" }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockEventSource.instances).toHaveLength(0);
  });
});
