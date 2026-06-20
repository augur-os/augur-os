import { render, screen, act } from "@testing-library/react";
import McpStatusBanner from "@/components/McpStatusBanner";

/**
 * Component-level verification that a cold-starting MCP backend renders the
 * calm "starting" banner, NOT the red "down" alarm — the demo-visible fix.
 */
describe("McpStatusBanner", () => {
  const realFetch = global.fetch;

  afterEach(() => {
    jest.useRealTimers();
    global.fetch = realFetch;
    jest.restoreAllMocks();
  });

  it("shows the calm 'starting' banner (not 'down') while MCP is cold-starting", async () => {
    jest.useFakeTimers();
    // Cold backend: every health probe fails.
    global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));

    render(<McpStatusBanner />);

    // Fire the initial probe (2s after mount) and flush its rejection.
    await act(async () => {
      await jest.advanceTimersByTimeAsync(2_100);
    });

    expect(screen.getByText(/starting up/i)).toBeInTheDocument();
    expect(screen.queryByText(/MCP server is down/i)).not.toBeInTheDocument();
  });

  it("renders no banner once MCP is reachable", async () => {
    jest.useFakeTimers();
    global.fetch = jest.fn().mockResolvedValue({ ok: true } as Response);

    render(<McpStatusBanner />);

    await act(async () => {
      await jest.advanceTimersByTimeAsync(2_100);
    });

    expect(screen.queryByText(/starting up/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/MCP server is down/i)).not.toBeInTheDocument();
  });
});
