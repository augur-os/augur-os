import { act, renderHook, waitFor } from "@testing-library/react";
import { useXtermTerminal } from "@/features/hooks/useXtermTerminal";

const terminalMock = {
  write: jest.fn(),
  open: jest.fn(),
  loadAddon: jest.fn(),
  clear: jest.fn(),
  reset: jest.fn(),
  dispose: jest.fn(),
  focus: jest.fn(),
  onData: jest.fn(() => ({ dispose: jest.fn() })),
  attachCustomKeyEventHandler: jest.fn(),
  options: {},
  cols: 80,
  rows: 24,
};

const fitAddonMock = {
  fit: jest.fn(),
};

jest.mock("@xterm/xterm", () => ({
  Terminal: jest.fn(() => terminalMock),
}));

jest.mock("@xterm/addon-fit", () => ({
  FitAddon: jest.fn(() => fitAddonMock),
}));

jest.mock("@xterm/addon-web-links", () => ({
  WebLinksAddon: jest.fn(() => ({})),
}));

jest.mock("@xterm/xterm/css/xterm.css", () => ({}), { virtual: true });

function makeSseResponse(lines: string[]): Response {
  const stream = new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(new TextEncoder().encode(line));
      }
      controller.close();
    },
  });

  return {
    ok: true,
    body: stream,
  } as Response;
}

describe("useXtermTerminal", () => {
  const originalFetch = global.fetch;
  const originalRaf = global.requestAnimationFrame;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    global.requestAnimationFrame = ((cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    }) as typeof requestAnimationFrame;
  });

  afterEach(() => {
    jest.useRealTimers();
    global.fetch = originalFetch;
    global.requestAnimationFrame = originalRaf;
  });

  it("requests only unseen PTY output after a reconnect", async () => {
    const fetchMock = jest
      .fn()
      .mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ status: "running" }),
        }),
      )
      .mockImplementationOnce(() =>
        Promise.resolve(
          makeSseResponse([
            `data: ${JSON.stringify({ raw: Buffer.from("hello", "utf-8").toString("base64"), cursor: 1 })}\n\n`,
          ]),
        ),
      )
      .mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ status: "running" }),
        }),
      )
      .mockImplementationOnce(() =>
        Promise.resolve(makeSseResponse([])),
      );

    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() =>
      useXtermTerminal({
        cliId: "codex",
        isRunning: true,
      }),
    );

    await act(async () => {
      result.current.terminalContainerRef(document.createElement("div"));
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/cli?cliId=codex&stream=true&format=raw",
        expect.anything(),
      );
    });

    await act(async () => {
      jest.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/cli?cliId=codex&stream=true&format=raw&cursor=1",
        expect.anything(),
      );
    });
  });

  it("wipes the terminal when the CLI session exits", async () => {
    const onExit = jest.fn();
    const fetchMock = jest
      .fn()
      .mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ status: "running" }),
        }),
      )
      .mockImplementationOnce(() =>
        Promise.resolve(
          makeSseResponse([
            `data: ${JSON.stringify({ event: "exit", code: 0 })}\n\n`,
          ]),
        ),
      );

    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() =>
      useXtermTerminal({
        cliId: "codex",
        isRunning: true,
        onExit,
      }),
    );

    await act(async () => {
      result.current.terminalContainerRef(document.createElement("div"));
      await Promise.resolve();
    });

    // The exit event must both notify the parent and clear the stale session
    // scrollback so the ended session doesn't linger or stack under the next.
    await waitFor(() => {
      expect(onExit).toHaveBeenCalledWith(0);
    });
    expect(terminalMock.reset).toHaveBeenCalled();
  });
});
