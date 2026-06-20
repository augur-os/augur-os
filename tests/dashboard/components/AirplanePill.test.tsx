/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockUseMcpQuery = jest.fn();
const mockInvalidateQueries = jest.fn();
const mockFetch = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
  }),
}));

import AirplanePill from "@/components/shared/AirplanePill";

describe("AirplanePill", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: jest.fn().mockResolvedValue(""),
    });
    global.fetch = mockFetch as unknown as typeof fetch;
  });

  it("renders OFF state from canonical MCP status", () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        airplane_mode: { enabled: false },
        ollama: {
          ready: true,
          has_configured_model: true,
          configured_model: "qwen3.5:9b",
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<AirplanePill />);

    expect(screen.getByRole("button", { name: /airplane mode is off/i }))
      .toBeInTheDocument();
    expect(screen.getByText(/off/i)).toBeInTheDocument();
    expect(mockUseMcpQuery).toHaveBeenCalledWith(
      "airplane-status",
      "get-local-backend-status",
      "static",
      { refetchInterval: 5000 },
    );
  });

  it("renders ON-ready state with configured model name", () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        airplane_mode: { enabled: true },
        ollama: {
          ready: true,
          has_configured_model: true,
          configured_model: "qwen3.5:9b",
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<AirplanePill />);

    expect(screen.getByRole("button", { name: /airplane mode is on/i }))
      .toBeInTheDocument();
    expect(screen.getByText(/qwen3\.5:9b/i)).toBeInTheDocument();
  });

  it("renders setup-needed when airplane mode is on but the local server is not ready", () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        airplane_mode: { enabled: true },
        ollama: {
          ready: false,
          has_configured_model: true,
          configured_model: "qwen3.5:9b",
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<AirplanePill />);

    expect(screen.getByText(/setup needed/i)).toBeInTheDocument();
  });

  it("renders setup-needed when airplane mode is on but the configured model is missing", () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        airplane_mode: { enabled: true },
        ollama: {
          ready: true,
          has_configured_model: false,
          configured_model: "qwen3.5:9b",
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<AirplanePill />);

    expect(screen.getByText(/setup needed/i)).toBeInTheDocument();
  });

  it("renders a neutral loading state instead of a false OFF state", () => {
    mockUseMcpQuery.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: jest.fn(),
    });

    render(<AirplanePill />);

    expect(screen.getByRole("button", { name: /checking airplane mode/i }))
      .toBeInTheDocument();
    expect(screen.queryByText(/off/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/setup needed/i)).not.toBeInTheDocument();
  });

  it("renders a status-read error instead of loading or false OFF", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: null,
      loading: false,
      error: "Failed to read preferences.yaml",
      refetch: jest.fn(),
    });

    render(<AirplanePill />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Failed to read preferences.yaml",
    );
    expect(
      screen.getByRole("button", { name: /retry airplane mode status/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/checking airplane mode/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/off/i)).not.toBeInTheDocument();
  });

  it("clicking POSTs toggle to /api/airplane and invalidates airplane-status", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        airplane_mode: { enabled: false },
        ollama: {
          ready: true,
          has_configured_model: true,
          configured_model: "qwen3.5:9b",
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<AirplanePill />);
    fireEvent.click(screen.getByRole("button", { name: /airplane mode is off/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/airplane", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "toggle" }),
      });
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ["airplane-status"],
      });
    });
  });

  it("surfaces failed toggle POSTs without invalidating cached status", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        airplane_mode: { enabled: false },
        ollama: {
          ready: true,
          has_configured_model: true,
          configured_model: "qwen3.5:9b",
        },
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: jest.fn().mockResolvedValue(
        JSON.stringify({ error: "permission denied" }),
      ),
    });

    render(<AirplanePill />);
    fireEvent.click(screen.getByRole("button", { name: /airplane mode is off/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("permission denied");
    expect(alert).not.toHaveTextContent('{"error":"permission denied"}');
    expect(mockInvalidateQueries).not.toHaveBeenCalled();
  });
});
