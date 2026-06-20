/**
 * @jest-environment jsdom
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { renderToString } from "react-dom/server";

const mockInvalidateQueries = jest.fn();
const mockUseMcpQuery = jest.fn();
const mockFetch = jest.fn();

jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
  }),
}));

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

import { useAirplaneModeStore } from "@/lib/stores/airplaneModeStore";

function AirplaneReadyProbe() {
  const { airplaneMode, airplaneModeReady } = useAirplaneModeStore();
  return (
    <span>
      {airplaneModeReady ? "ready" : "loading"}:
      {airplaneMode ? "on" : "off"}
    </span>
  );
}

describe("useAirplaneModeStore", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
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
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: jest.fn().mockResolvedValue(""),
    });
    global.fetch = mockFetch as unknown as typeof fetch;
  });

  it("reads canonical airplane status from MCP and writes through /api/airplane", async () => {
    const localStorageSet = jest.spyOn(Storage.prototype, "setItem");

    const { result } = renderHook(() => useAirplaneModeStore());

    await waitFor(() => expect(result.current.airplaneModeReady).toBe(true));
    expect(result.current.airplaneMode).toBe(true);
    expect(result.current.airplaneBackendReady).toBe(true);
    expect(result.current.airplaneModeError).toBeNull();
    expect(mockUseMcpQuery).toHaveBeenCalledWith(
      "airplane-status",
      "get-local-backend-status",
      "static",
      { refetchInterval: 5000 },
    );

    await act(async () => {
      await result.current.setAirplaneMode(false);
    });

    expect(mockFetch).toHaveBeenCalledWith("/api/airplane", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "off" }),
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["airplane-status"],
    });
    expect(localStorageSet).not.toHaveBeenCalled();
  });

  it("does not report ready during server render even when canonical data is available", () => {
    const html = renderToString(<AirplaneReadyProbe />);

    expect(html).toContain("loading");
    expect(html).toContain("on");
  });

  it("reports not ready while canonical airplane status is still loading", () => {
    mockUseMcpQuery.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: jest.fn(),
    });

    const { result } = renderHook(() => useAirplaneModeStore());

    expect(result.current.airplaneMode).toBe(false);
    expect(result.current.airplaneModeReady).toBe(false);
    expect(result.current.airplaneBackendReady).toBe(false);
    expect(result.current.airplaneModeError).toBeNull();
  });

  it("surfaces MCP read errors and keeps airplane status not ready", () => {
    mockUseMcpQuery.mockReturnValue({
      data: null,
      loading: false,
      error: "Failed to read preferences.yaml",
      refetch: jest.fn(),
    });

    const { result } = renderHook(() => useAirplaneModeStore());

    expect(result.current.airplaneMode).toBe(false);
    expect(result.current.airplaneModeReady).toBe(false);
    expect(result.current.airplaneBackendReady).toBe(false);
    expect(result.current.airplaneModeError).toBe("Failed to read preferences.yaml");
  });

  it("reports backend not ready when Ollama status is unavailable", () => {
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

    const { result } = renderHook(() => useAirplaneModeStore());

    expect(result.current.airplaneMode).toBe(true);
    expect(result.current.airplaneModeReady).toBe(true);
    expect(result.current.airplaneBackendReady).toBe(false);
  });

  it("reports backend not ready when configured Ollama model is missing", () => {
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

    const { result } = renderHook(() => useAirplaneModeStore());

    expect(result.current.airplaneMode).toBe(true);
    expect(result.current.airplaneModeReady).toBe(true);
    expect(result.current.airplaneBackendReady).toBe(false);
  });

  it("throws an actionable error when /api/airplane fails", async () => {
    mockUseMcpQuery.mockReturnValue({
      data: { airplane_mode: { enabled: false } },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: jest.fn().mockResolvedValue("preferences.yaml is unwritable"),
    });

    const { result } = renderHook(() => useAirplaneModeStore());

    await expect(result.current.toggleAirplaneMode()).rejects.toThrow(
      "Failed to update airplane mode via /api/airplane: preferences.yaml is unwritable",
    );
    expect(mockInvalidateQueries).not.toHaveBeenCalled();
  });
});
